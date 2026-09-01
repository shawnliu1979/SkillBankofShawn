## 使用实例

### 实例 1：事务边界问题

**触发场景**：订单创建接口偶发数据不一致，怀疑事务范围有问题。

**调用方式**：
```
请用 /hawk-eye-java 检查以下 Service 方法的事务边界是否正确：

@Service
public class OrderService {
  @Transactional
  public void createOrder(OrderDTO dto) {
    Order order = orderRepo.save(toEntity(dto));
    inventoryService.deduct(dto.getProductId(), dto.getQuantity()); // 内部调用另一个 @Transactional 方法
    notificationService.sendEmail(order.getId()); // 调用外部接口
  }
}
```

---

### 实例 2：并发安全审查

**触发场景**：秒杀活动中库存扣减出现超卖，需要定位并发安全问题。

**调用方式**：
```
请用 /hawk-eye-java 审查这段库存扣减逻辑，判断是否存在并发安全问题：

public void deductStock(Long productId, int quantity) {
  Product product = productRepo.findById(productId).orElseThrow();
  if (product.getStock() < quantity) throw new InsufficientStockException();
  product.setStock(product.getStock() - quantity);
  productRepo.save(product);
}
```

---

### 实例 3：分层设计评审

**触发场景**：新加入项目，发现 Controller 层有大量业务逻辑，想评估是否需要重构。

**调用方式**：
```
请用 /hawk-eye-java 评审这个 Controller，判断分层是否合理，给出重构建议：

@RestController
public class UserController {
  @PostMapping("/users")
  public ResponseEntity<?> createUser(@RequestBody UserDTO dto) {
    // 直接在 Controller 中写了 30 行业务逻辑：验证、查重、加密、持久化...
  }
}
```

---

### 实例 4：工程总体代码评审

**触发场景**：对一个完整的工程代码，评估是否需要改进。

**调用方式**：
```
请用 /hawk-eye-java 评审给出的工程，评估是否需要改进：
./sample-4_tartgetSource
```
