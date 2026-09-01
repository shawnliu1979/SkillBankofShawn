# 代码评审报告

## 0. 评分

**5/10**

评分依据：存在一个 P2 级并发安全问题。库存扣减采用“读取实体 -> 内存校验 -> 修改实体 -> 保存”的非原子读改写流程，在并发请求下可能超卖或产生丢失更新。

## 1. 总体结论

- 当前状态：不安全。代码没有使用数据库锁、版本控制或带库存条件的原子更新语句，无法保证库存判断与扣减操作在并发条件下的一致性。
- 风险等级：高。
- 建议优先级：立即修复库存更新方式，并补充并发集成测试后再用于秒杀、抢购等高并发链路。

## 2. 问题列表（按严重程度）

### 读取、库存校验和保存不是原子操作

- 严重级别：P2。
- 代码引用或者对应行号：第 2 行 `findById`，第 3 行库存校验，第 4 至 5 行修改并保存。
- 现象：多个请求可同时读取同一个库存值，随后分别通过库存校验并保存各自计算出的结果。最终库存值可能只减少一次，或者多个请求都被判定为成功但实际库存不足。
- 影响：秒杀、下单、购物车结算和库存管理链路可能超卖；订单数量与实际可售库存不一致，后续需要人工或补偿流程处理。
- 触发条件：至少两个请求同时扣减同一商品，且它们的 `findById` 都发生在任一请求 `save` 提交之前。库存接近扣减量时最容易观察到超卖。
- 修复建议：优先使用带库存下限条件的单条 SQL 更新，将“库存充足判断”和“扣减”交由数据库在同一原子操作中完成。根据受影响行数判断成功与否；不要仅通过给当前方法添加 `@Transactional` 修复，因为默认事务隔离级别下它仍不能避免两个事务同时读取旧库存。
- 示例代码：

```java
public interface ProductRepository extends JpaRepository<Product, Long> {
  @Modifying
  @Query("""
      update Product product
      set product.stock = product.stock - :quantity
      where product.id = :productId
        and product.stock >= :quantity
      """)
  int deductIfEnough(Long productId, int quantity);
}

@Service
public class InventoryService {
  @Transactional
  public void deductStock(Long productId, int quantity) {
    if (quantity <= 0) {
      throw new IllegalArgumentException("quantity must be positive");
    }

    int updatedRows = productRepo.deductIfEnough(productId, quantity);
    if (updatedRows == 0) {
      throw new InsufficientStockException(productId);
    }
  }
}
```

- 原因分析：应用层的 `getStock` 校验与后续 `save` 是两次独立数据库交互，中间存在并发窗口。数据库执行 `stock >= :quantity` 条件更新时，会在更新过程中保证条件判断和写入的原子性。

### 实体保存可能覆盖其他请求已经提交的库存修改

- 严重级别：P2。
- 代码引用或者对应行号：第 4 至 5 行，`setStock` 与 `save`。
- 现象：两个事务先后读取库存 10，并各自扣减 2，二者都可能将库存保存为 8。虽然两个扣减请求都返回成功，库存实际只减少 2，产生丢失更新。
- 影响：库存账实不符，后续每次销售都会放大误差；即使初始库存很高，也会持续损害库存准确性。
- 触发条件：并发事务读取同一实体，并在第一个事务提交后由第二个事务保存其过期实体状态。
- 修复建议：若业务必须先加载实体并执行复杂计算，为 `Product` 增加 `@Version` 乐观锁字段，并在发生 `OptimisticLockingFailureException` 时有限次数重试或返回库存变动提示。对于简单扣减，仍优先采用上一项的原子条件更新。
- 示例代码：

```java
@Entity
public class Product {
  @Id
  private Long id;

  private int stock;

  @Version
  private long version;
}

@Transactional
public void deductStock(Long productId, int quantity) {
  Product product = productRepo.findById(productId).orElseThrow();
  if (product.getStock() < quantity) {
    throw new InsufficientStockException(productId);
  }
  product.setStock(product.getStock() - quantity);
  // JPA flush 时会校验 version；冲突时抛出乐观锁异常。
}
```

- 原因分析：无版本字段时，ORM 通常依据主键更新实体，无法识别该实体是否已经被其他事务修改。`@Version` 会把版本号加入更新条件，使过期写入失败而不是静默覆盖。

### 缺少数量参数的边界校验

- 严重级别：P3。
- 代码引用或者对应行号：第 1 行，`quantity` 参数。
- 现象：当 `quantity` 为 0 或负数时，现有判断不会拒绝请求；负数会使 `stock - quantity` 增加库存。
- 影响：调用方传参错误或恶意请求可导致库存被错误增加，影响库存数据可信度。
- 触发条件：传入 `quantity <= 0`。
- 修复建议：在进入库存操作前校验 `quantity > 0`；同时在接口参数层增加 Bean Validation，并视数据库能力增加非负库存约束。
- 示例代码：

```java
if (quantity <= 0) {
  throw new IllegalArgumentException("quantity must be positive");
}
```

## 3. 快速修复任务清单

- [ ] 将库存扣减改为 `stock >= quantity` 的原子条件更新，并按受影响行数判定库存是否充足。
- [ ] 为复杂实体更新场景增加 `@Version` 乐观锁和明确的冲突处理策略。
- [ ] 校验 `quantity > 0`，并在 API 层和数据库层补充对应约束。
- [ ] 编写并发集成测试：初始库存为 1 时并发执行两次扣减 1，断言仅一个请求成功且最终库存为 0。
- [ ] 编写丢失更新测试：初始库存为 10 时并发执行两次扣减 2，断言两个请求成功时最终库存必须为 6。
- [ ] 对高并发商品执行压测，持续核对成功订单数、库存变动和失败请求数的一致性。