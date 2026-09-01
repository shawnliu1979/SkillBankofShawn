# 代码评审报告

## 0. 评分

**6/10**

评分依据：当前工程的 Spring Boot 3.5.8、Java 17 和系统 Gradle 8.14.2 可以正常构建，但存在一个 P2 级异常处理风险：AOP 环绕通知吞掉 Controller 抛出的所有异常。该行为会改变接口的响应语义并掩盖真实故障。

## 1. 总体结论

- 当前状态：基础工程可运行且构建正常，但日志切面需要修复后才适合作为业务接口的通用横切组件。
- 风险等级：中。
- 建议优先级：首先修正环绕通知的异常传播；随后收窄切点、提交 Gradle Wrapper 并补充 Web 层测试。
- 验证结果：在工程目录执行 `gradle test --no-daemon` 成功，耗时约 5 秒。当前未发现测试源文件，因此该命令仅验证了构建与测试任务可以执行，尚未验证首页和异常响应的运行时行为。

## 2. 问题列表（按严重程度）

### 环绕通知吞掉 Controller 异常并返回 `null`

- 严重级别：P2。
- 代码引用或者对应行号：[DemoInvocation.java](sample-4_tartgetSource/src/main/java/com/example/demo/DemoInvocation.java) 的 `writeLog` 方法，`catch (Throwable t)` 分支。
- 现象：Controller 方法或其后续业务逻辑抛出异常时，切面仅记录日志而不重新抛出，随后返回初始值 `null`。Spring MVC 无法按原有异常类型进入 `@ExceptionHandler`、错误页面或默认的 500 响应处理流程。
- 影响：接口可能返回与真实错误不一致的响应，排障时丢失异常语义；事务或安全框架依赖异常传播的场景也可能受到影响。
- 触发条件：任意命中切点的 Controller 方法抛出运行时异常、受检异常或 `Error`。
- 修复建议：记录异常后原样抛出，不应在日志切面中消费业务异常。将方法签名声明为 `throws Throwable`，让 Spring 的全局异常处理机制决定最终响应。
- 示例代码：

```java
@Around("execution(* com.example.demo..*Controller.*(..))")
public Object writeLog(ProceedingJoinPoint joinPoint) throws Throwable {
  String signature = joinPoint.getSignature().toShortString();
  log.debug("controller started: {}", signature);
  try {
    Object result = joinPoint.proceed();
    log.debug("controller completed: {}", signature);
    return result;
  } catch (Throwable throwable) {
    log.error("controller failed: {}", signature, throwable);
    throw throwable;
  }
}
```

- 原因分析：`@Around` 是 Controller 调用链的一部分。捕获异常后正常返回等同于改变了原方法的控制流；返回 `null` 并不能表达原始失败原因。

### 同一请求被三个通知重复记录，且失败请求会输出“结束”日志

- 严重级别：P3。
- 代码引用或者对应行号：[DemoInvocation.java](sample-4_tartgetSource/src/main/java/com/example/demo/DemoInvocation.java) 的 `startLog`、`endLog`、`writeLog` 方法。
- 现象：同一个切点同时配置了 `@Before`、`@After` 和 `@Around`，一次成功请求会产生三组开始/结束日志。`@After` 对正常返回和异常退出都会执行，因此异常请求也会记录看似成功的结束日志。
- 影响：日志噪声增加，调用链难以阅读；基于日志统计成功率或耗时的监控可能失真，增加存储和检索成本。
- 触发条件：所有命中 `com.example.demo.*Controller.*(..)` 的 Controller 调用，尤其是发生异常时。
- 修复建议：只保留一个 `@Around` 通知，统一记录开始、成功结束和异常结束；若需要耗时指标，在该通知中计算并使用结构化字段输出。
- 示例代码：

```java
long startedAt = System.nanoTime();
try {
  return joinPoint.proceed();
} finally {
  long elapsedMs = (System.nanoTime() - startedAt) / 1_000_000;
  log.debug("controller completed in {} ms: {}", elapsedMs, signature);
}
```

- 原因分析：环绕通知本身覆盖前置和后置的能力。多种通知重叠时，日志语义不再一一对应于业务调用状态。

### 切点只匹配当前包的一层 Controller 类

- 严重级别：P3。
- 代码引用或者对应行号：[DemoInvocation.java](sample-4_tartgetSource/src/main/java/com/example/demo/DemoInvocation.java) 的三个 `execution(* com.example.demo.*Controller.*(..))` 表达式。
- 现象：`com.example.demo.*Controller` 只匹配 `com.example.demo` 包下、类名以 `Controller` 结尾的类型。若后续按常见方式将 Controller 放入 `com.example.demo.web` 或 `com.example.demo.user` 等子包，切面将静默失效。
- 影响：日志覆盖不完整，新增接口没有调用审计信息，团队容易误以为所有 Controller 都受统一日志策略保护。
- 触发条件：新增子包中的 Controller，或重命名 Controller 为 `*Resource`、`*Endpoint` 等其他约定。
- 修复建议：按架构边界定义切点，例如统一放在 `..web..` 包并使用 `within`；若确实以命名作为规范，则使用 `..*Controller` 覆盖子包。为切面添加集成测试，确保新增包结构时可发现失效。
- 示例代码：

```java
@Around("within(com.example.demo..*Controller)")
public Object writeLog(ProceedingJoinPoint joinPoint) throws Throwable {
  return joinPoint.proceed();
}
```

### 缺少 Gradle Wrapper 和自动化行为测试

- 严重级别：P3。
- 代码引用或者对应行号：[build.gradle](sample-4_tartgetSource/build.gradle)；工程根目录未包含 `gradlew`、`gradlew.bat` 或 `gradle/wrapper`。
- 现象：工程依赖机器上预装的 Gradle；当前构建虽在 Gradle 8.14.2 上通过，但其他开发者或 CI 使用不同版本时无法得到可复现的构建结果。项目没有 `src/test`，首页渲染和 AOP 异常传播都没有回归保护。
- 影响：依赖或插件升级后可能在不同环境中失败；日志切面这类横切逻辑发生回归时无法自动发现。
- 触发条件：新成员搭建环境、CI 使用不同 Gradle 版本，或 Controller、模板、切面被修改时。
- 修复建议：生成并提交与 Spring Boot 3.5.8 兼容的 Gradle Wrapper；添加 `@WebMvcTest` 覆盖 `/` 返回 `index`，并增加一个会抛异常的测试 Controller，断言异常仍被 Spring MVC 正确处理。
- 示例代码：

```bash
gradle wrapper --gradle-version 8.14.2
./gradlew test
```

```java
@WebMvcTest(DemoController.class)
class DemoControllerTest {
  @Autowired
  private MockMvc mockMvc;

  @Test
  void indexRendersTheIndexView() throws Exception {
    mockMvc.perform(get("/"))
        .andExpect(status().isOk())
        .andExpect(view().name("index"));
  }
}
```

### 日志文件配置使用旧属性名，且硬编码 Windows 路径

- 严重级别：P4。
- 代码引用或者对应行号：[application.properties](sample-4_tartgetSource/src/main/resources/application.properties) 的 `logging.file`。
- 现象：`logging.file` 是旧版本属性名；当前 Spring Boot 使用 `logging.file.name` 或 `logging.file.path`。值 `C:/work/logs/demo.log` 绑定 Windows 目录，在 macOS、Linux 和容器环境中不可移植。
- 影响：预期的文件日志可能未按配置写入，或跨环境启动时发生路径问题；本机路径被固化在应用包内。
- 触发条件：部署到非 Windows 环境，或需要依赖该配置排查生产问题时。
- 修复建议：使用当前属性名，并通过环境变量或部署配置提供日志路径；容器部署优先输出到标准输出并由平台收集。
- 示例代码：

```properties
logging.file.name=${LOG_FILE:logs/demo.log}
```

## 3. 快速修复任务清单

- [ ] 修改 `writeLog`：记录异常后重新抛出，禁止返回 `null` 掩盖 Controller 失败。
- [ ] 删除重叠的 `@Before` 和 `@After` 通知，仅保留包含成功、失败和耗时信息的 `@Around` 通知。
- [ ] 将切点调整为能覆盖预期子包的架构表达式，并增加切面覆盖测试。
- [ ] 生成并提交 Gradle Wrapper，在本地与 CI 统一执行 `./gradlew test`。
- [ ] 添加首页渲染和异常传播的 MockMvc 测试。
- [ ] 将 `logging.file` 更新为 `logging.file.name`，从环境变量读取可部署的日志路径。