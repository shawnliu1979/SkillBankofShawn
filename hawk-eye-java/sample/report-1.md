# 代码评审报告

## 0. 评分

**6/10**

评分依据：存在一个 P2 级事务边界问题。数据库订单和库存写入可在同一事务中保持原子性，但外部邮件调用被包含在事务内，无法与数据库提交形成原子操作，且会拉长事务持锁时间。

## 1. 总体结论

- 当前状态：订单创建与库存扣减在默认 `REQUIRED` 传播行为下会加入 `createOrder` 的同一事务，订单或库存操作失败时两者都会回滚。该边界对两项本地数据库写入是合理的。
- 风险等级：高。
- 建议优先级：优先将邮件通知移出事务主路径，并明确库存扣减的事务传播契约和失败语义。

## 2. 问题列表（按严重程度）

### 外部邮件调用处于数据库事务内

- 严重级别：P2。
- 代码引用或者对应行号：第 7 行，`notificationService.sendEmail(order.getId())`。
- 现象：邮件服务是不可由数据库事务回滚的外部副作用。若邮件发送成功后外层事务因提交失败、库存扣减异常或超时而回滚，用户仍会收到“订单已创建”的邮件，但订单和库存变更并未生效。反过来，邮件调用超时也会使数据库事务持续占用连接和锁。
- 影响：订单、库存和通知的一致性；高并发时还会增加锁等待、连接池耗尽及创建订单接口超时的风险。
- 触发条件：邮件已被外部服务接收后，后续数据库操作或事务提交失败；或邮件服务网络抖动、延迟、重试。
- 修复建议：事务内仅完成订单和库存等本地状态变更。使用事务事件的 `AFTER_COMMIT` 阶段触发通知；对可靠投递要求较高时，采用 Outbox 表加异步消费者，并为邮件发送实现幂等和重试。
- 示例代码：

```java
@Service
public class OrderService {
  private final ApplicationEventPublisher eventPublisher;

  @Transactional
  public void createOrder(OrderDTO dto) {
    Order order = orderRepo.save(toEntity(dto));
    inventoryService.deduct(dto.getProductId(), dto.getQuantity());
    eventPublisher.publishEvent(new OrderCreatedEvent(order.getId()));
  }
}

@Component
public class OrderNotificationListener {
  @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
  public void onOrderCreated(OrderCreatedEvent event) {
    notificationService.sendEmail(event.orderId());
  }
}
```

- 原因分析：Spring 的数据库事务只能协调受同一事务管理器控制的资源；普通 HTTP、SMTP 或第三方 SDK 调用不会随数据库回滚。`AFTER_COMMIT` 可保证仅在订单事务已提交后才尝试发送，但它不保证邮件最终必达，必达需求应由 Outbox 等持久化消息方案承担。

### 库存扣减的传播行为依赖未明确的实现契约

- 严重级别：P3。
- 代码引用或者对应行号：第 6 行，`inventoryService.deduct(...)`。
- 现象：若 `inventoryService` 是另一个 Spring Bean，且 `deduct` 使用默认 `@Transactional(propagation = REQUIRED)`，它会加入外层订单事务，这是当前场景的合理默认值。若其实际配置为 `REQUIRES_NEW`、`NOT_SUPPORTED`，或因同类自调用未经过 Spring 代理，订单与库存就不再具有预期的原子性或事务增强可能失效。
- 影响：订单和库存的一致性，以及库存失败时的回滚语义。
- 触发条件：库存服务显式改变传播级别；库存服务被同类方法直接调用；库存操作跨数据源、跨服务，或内部吞掉异常后继续返回。
- 修复建议：将库存扣减的契约明确为“参加订单事务，扣减失败抛出运行时业务异常”。确认它通过 Spring 代理调用；若库存为独立服务，不要依赖本地 `@Transactional` 保证跨服务原子性，应采用预占、补偿或 Saga 等一致性方案。
- 示例代码：

```java
@Service
public class InventoryService {
  @Transactional(propagation = Propagation.MANDATORY)
  public void deduct(Long productId, int quantity) {
    // 原子条件更新；库存不足时抛出运行时异常
    int updatedRows = inventoryRepository.deductIfEnough(productId, quantity);
    if (updatedRows == 0) {
      throw new InsufficientStockException(productId);
    }
  }
}
```

- 原因分析：`MANDATORY` 可将“必须由订单事务调用”的设计意图变为可验证的运行时约束。若库存扣减也需要作为独立入口使用，则保留 `REQUIRED`，并通过集成测试验证其在订单创建调用链中加入同一事务。

## 3. 快速修复任务清单

- [ ] 将 `notificationService.sendEmail` 替换为 `AFTER_COMMIT` 事务事件；需要可靠投递时落地 Outbox 和消费者重试。
- [ ] 审核 `inventoryService.deduct` 的传播级别、异常类型及是否经 Spring 代理调用。
- [ ] 补充回滚测试：库存不足或订单保存失败时，断言订单和库存均未提交且未发送邮件。
- [ ] 补充提交后测试：订单和库存提交成功后才发送邮件；模拟邮件失败时，不影响已提交订单，并验证重试或告警行为。
- [ ] 完成并发与超时回归验证，确认慢邮件服务不会延长订单数据库事务。