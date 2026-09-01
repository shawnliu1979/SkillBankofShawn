# 代码评审报告

## 0. 评分

**7/10**

评分依据：存在 P3 级分层与可维护性问题。Controller 同时承担接口适配、业务规则、数据访问与安全处理职责，当前不会直接导致编译或数据丢失问题，但会显著提高变更和测试风险。

## 1. 总体结论

- 当前状态：分层不合理。`UserController#createUser` 除了 HTTP 请求处理外，还承载参数验证、用户查重、密码加密和持久化等业务编排。
- 风险等级：中。
- 建议优先级：尽快将注册用例抽取至 Service；Controller 保持薄层，Repository 与密码加密组件由 Service 协调。

## 2. 问题列表（按严重程度）

### Controller 承担多个业务职责

- 严重级别：P3。
- 代码引用或者对应行号：第 5 行，`createUser` 方法中的验证、查重、加密和持久化逻辑。
- 现象：接口层同时处理 HTTP 协议适配、输入验证、用户唯一性规则、密码处理及数据库写入。后续增加注册渠道、邀请关系、审计、欢迎通知或不同返回格式时，方法会持续膨胀。
- 影响：Controller 难以阅读和维护；业务规则被绑定到 HTTP 入口，复用至消息消费、批量导入或后台任务时容易复制代码；单元测试需引入 Web 层依赖，测试成本上升。
- 触发条件：新增注册规则、支持多个注册入口、替换密码算法或增加注册后流程时。
- 修复建议：Controller 仅负责请求 DTO 的接收、基础格式校验、调用 Application Service 和映射 HTTP 响应。将注册业务编排移至 `UserService`；由 Service 协调查重、密码编码和 Repository 持久化。
- 示例代码：

```java
@RestController
@RequestMapping("/users")
public class UserController {
  private final UserService userService;

  @PostMapping
  public ResponseEntity<UserResponse> createUser(@Valid @RequestBody CreateUserRequest request) {
    User user = userService.register(request);
    return ResponseEntity.status(HttpStatus.CREATED).body(UserResponse.from(user));
  }
}

@Service
public class UserService {
  @Transactional
  public User register(CreateUserRequest request) {
    if (userRepository.existsByEmail(request.email())) {
      throw new DuplicateUserException(request.email());
    }

    User user = new User(request.email(), passwordEncoder.encode(request.password()));
    return userRepository.save(user);
  }
}
```

- 原因分析：Controller 属于入站适配层，应依赖应用层用例；应用 Service 负责业务流程和事务边界；Repository 只负责数据访问。职责分离后，注册用例可以脱离 MVC 框架进行测试和复用。

### 密码加密逻辑放在接口层会扩大安全变更范围

- 严重级别：P3。
- 代码引用或者对应行号：第 5 行，密码加密逻辑。
- 现象：密码编码规则若散落在 Controller，其他创建或重置密码入口可能遗漏加密，或使用不同算法参数。明文密码也更容易在接口层日志、异常信息或 DTO 映射中暴露。
- 影响：密码存储策略不一致，安全升级和审计难度增加；遗漏加密时可能造成严重安全事故。
- 触发条件：增加管理员创建用户、批量导入、密码重置等入口；升级 `PasswordEncoder` 参数或替换算法时。
- 修复建议：通过 Spring Security 的 `PasswordEncoder` 注入 Service 或专职凭据组件，所有密码写入统一经过该组件。禁止记录包含明文密码的 DTO，并用独立请求类型承载密码字段。
- 示例代码：

```java
@Service
public class UserService {
  private final PasswordEncoder passwordEncoder;

  public UserService(PasswordEncoder passwordEncoder) {
    this.passwordEncoder = passwordEncoder;
  }

  public String encodePassword(String rawPassword) {
    return passwordEncoder.encode(rawPassword);
  }
}
```

- 原因分析：密码编码是安全域规则，而不是 HTTP 展示逻辑。将其集中到应用层或安全组件，可统一算法、参数、审计和测试策略。

### 用户查重需要数据库唯一约束兜底

- 严重级别：P2。
- 代码引用或者对应行号：第 5 行，用户查重与持久化逻辑。
- 现象：即使将查重迁移至 Service，单独执行“先查询是否存在、再插入”在并发注册时仍有竞争窗口。两个请求都可能认为邮箱未被使用，随后同时尝试创建用户。
- 影响：没有唯一约束时会创建重复账号；有唯一约束但未统一转换异常时，调用方可能收到不稳定的数据库异常响应。
- 触发条件：两个或更多请求并发注册同一个唯一标识，例如邮箱、手机号或用户名。
- 修复建议：在数据库为业务唯一字段创建唯一索引；Service 可提前通过 `existsByEmail` 提供友好反馈，但必须捕获并转换数据库唯一约束冲突，作为并发条件下的最终保障。
- 示例代码：

```java
@Table(
    name = "users",
    uniqueConstraints = @UniqueConstraint(name = "uk_users_email", columnNames = "email"))
@Entity
public class User {
  // fields omitted
}

@Transactional
public User register(CreateUserRequest request) {
  try {
    return userRepository.saveAndFlush(toUser(request));
  } catch (DataIntegrityViolationException exception) {
    throw new DuplicateUserException(request.email(), exception);
  }
}
```

- 原因分析：应用层预查只能改善常规请求的提示，不能提供并发唯一性保证；数据库唯一约束才是最终一致的裁决点。

### `ResponseEntity<?>` 弱化接口契约

- 严重级别：P4。
- 代码引用或者对应行号：第 5 行，返回类型 `ResponseEntity<?>`。
- 现象：通配符隐藏了成功响应的具体结构，使调用方、API 文档和测试难以明确依赖返回字段。
- 影响：接口演进时更易发生不兼容变更，生成 OpenAPI 文档与客户端代码的准确性下降。
- 触发条件：增加统一错误响应、多个成功状态或第三方系统调用该接口时。
- 修复建议：成功路径使用具体响应 DTO，例如 `ResponseEntity<UserResponse>`；错误统一由 `@RestControllerAdvice` 映射为结构稳定的错误响应。
- 示例代码：

```java
@PostMapping
public ResponseEntity<UserResponse> createUser(
    @Valid @RequestBody CreateUserRequest request) {
  User user = userService.register(request);
  return ResponseEntity.status(HttpStatus.CREATED).body(UserResponse.from(user));
}
```

## 3. 快速修复任务清单

- [ ] 新建 `UserService#register`，把查重、密码编码与用户保存移出 Controller。
- [ ] 在 Service 方法定义事务边界，并明确重复用户和参数无效等业务异常。
- [ ] 使用 `PasswordEncoder` 统一密码写入逻辑，确认日志和异常中不含明文密码。
- [ ] 为邮箱、手机号或用户名等业务唯一字段添加数据库唯一约束，并转换唯一约束冲突异常。
- [ ] 为 Controller 固定成功响应 DTO，并使用全局异常处理器返回统一错误结构。
- [ ] 补充 Service 单元测试与 Controller Web 测试：注册成功、重复用户、非法入参、密码已编码和并发重复注册。