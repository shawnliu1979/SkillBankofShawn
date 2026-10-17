# RunningHub 接口参考

> 除标注为历史的内容外，接口于 **2026-10-17** 测试。域名：`www.runninghub.cn`（RH 站）、`rhtv.runninghub.cn`（RHTV 画布）。这里只记录免登录或支持 API Key 的接口；需要登录态的接口会返回 `TOKEN_MISSION`。

## 0. 认证与区域

| 项 | 值 |
|---|---|
| API Key 来源 | 环境变量 `RUNNINGHUB_API_KEY`（自行放进 shell 启动文件或密钥管理器） |
| OpenAPI 认证头 | `Authorization: Bearer <key>` |
| 站点内部接口（search / webapp / getJsonApiFormat） | **免鉴权**；`getJsonApiFormat` 需在 body 里带 `apiKey` |
| 需登录态 | `/api/workflow/*` 全部 → `403 TOKEN_MISSION`；RHTV `/api/...` 同 |

## 1. 检索工作流（核心）

```
POST https://www.runninghub.cn/api/search/workflow
body: {"search": "<关键词>", "page": 0, "size": 20}
```

- **关键词字段必须叫 `search`**。`keyword` / `searchKey` 被静默忽略 → 返回全站（历史 90849 条）。
- 排序参数无效（`sort` / `orderBy` / `sortType` 都试过，被忽略）。
- `page` 从 **0** 开始。

响应：
```json
{"code":0,"msg":"success","data":{
  "records":[{
    "id":"<workflowId>",                 // ← 这就是 workflowId，取 JSON / 提交都用它
    "name":"示例工作流名",
    "desc":"...", "publishTime":"2025-03-06T14:50:39.000+00:00",
    "owner":{"id":"...","avatar":"...","name":"作者名"},
    "statisticsInfo":{"useCount":"6683","collectCount":"189","likeCount":"32","pv":"0"},
    "tags":[{"id":"...","name":"视频"}], "labels":"RECOMMEND",
    "preview":{"url":"..."}, "covers":[{"url":"..."}]
  }],
  "total":2335,"pages":390,"current":1,"size":10,"hasNext":true}}
```

实测样例（2026-10-17，关键词「首尾帧」）：`total=2335`；`pages=390`；`hasNext=true`。
**判据：`total` 上万基本等于关键词没生效（被当全站查询）。**

## 2. 取工作流 API 格式 JSON

```
POST https://www.runninghub.cn/api/openapi/getJsonApiFormat
body: {"apiKey": "<RUNNINGHUB_API_KEY>", "workflowId": "<第1步的 id>"}
```

- 返回 `data.prompt`：**JSON 字符串（二次编码）**，需再 `json.loads` 一次 → `{nodeId: {class_type, inputs}}`。
- `workflowId` 必须是工作流库 id；传 `/ai-detail/` 的 id 会 `WORKFLOW_NOT_EXISTS`（历史还出现过 `code:380`）。
- 只要该工作流存在即可读，**不需要**它是你自己保存的。

## 3. AI 应用详情

```
POST https://www.runninghub.cn/api/webapp/detail
body: {"webappId": "<应用页 id>"}
```
响应 `data` 关键字段：

| 字段 | 含义 |
|---|---|
| `name` | 应用名 |
| `workflowId` | 底层 ComfyUI 工作流 id → 可直接喂给第 2 步和 `/run/workflow/` |
| `owner.name` | 作者 |
| `inputNodes[]` | `{nodeId, fieldName, descriptionCn, fieldValue}` ← 面板输入项 |
| `statisticsInfo` | useCount / collectCount |
| `avgRunningSeconds` / `runningSuccessRate` | 平均耗时 / 成功率（新应用常为 null） |
| `curl` | 官方给的单条调用示例 |

- 应用页 id 只能从站内搜索或人工拿到，**没有**关键词接口（`/api/search/webapp|app|ai-app`、`/api/webapp/search` 均 404）。
- `/api/workflow/detail`、`/api/openapi/workflow/detail`、`/api/workflow/node/list` → 403 TOKEN_MISSION（需要登录态）。

## 4. RHTV 画布技能库

```
POST https://rhtv.runninghub.cn/canvas/skill/list
body: {"page":1,"size":200,"category":"CANVAS_AGENT","type":"COMMON"}

POST https://rhtv.runninghub.cn/canvas/skill/detail
body: {"skillId":"<skillId>"}
```
- 免鉴权；`page` 从 **1** 开始；不支持关键词。
- 实测 2026-10-17：`total=164`（2026-10-14 为 163），输出类型 VIDEO/IMAGE/TEXT。
- 记录字段：`skillId / name / intro / useScenario / useGuide / outputContentDesc / presetPrompt / outputType / nickName / useCount / collectCount`。
- 是"画布 Agent 行业 Skill"（成片级），不是 ComfyUI 工作流，**不能提交运行**。
- `rhtv.runninghub.cn/api/...` 需要登录态；`www` 的 `getJsonApiFormat` 不能用于 `skillId`，会返回 `WORKFLOW_NOT_EXISTS`。

## 5. 余额

```
POST https://www.runninghub.cn/uc/openapi/accountStatus
body: {"apiKey": "<key>"}
→ data: {remainCoins:"…", currentTaskCounts:"0", apiType:"NORMAL"}
```
- 实测 2026-10-17 可用。`/openapi/v2/account/status` 报 `1602 HEADER_API_KEY_NOT_FOUND`（v2 风格需 Bearer 头 + 别的路径，未通）。

## 6. 提交 / 查询 / 上传（OpenAPI v2，花币）

```
POST https://www.runninghub.cn/openapi/v2/run/ai-app/<webappId>
POST https://www.runninghub.cn/openapi/v2/run/workflow/<workflowId>   ← 本 skill 支持，但未实测
body: {"nodeInfoList":[{"nodeId":"163","fieldName":"text","fieldValue":"…"}],
       "instanceType":"default", "usePersonalQueue":"false"}
→ {"taskId":"…","status":"…","promptTips":"…"}

POST https://www.runninghub.cn/openapi/v2/query
body: {"taskId":"…"}  → status SUCCESS/FAILED, results[{url,nodeId,text}], usage{taskCostTime,consumeCoins,consumeMoney}

POST https://www.runninghub.cn/openapi/v2/media/upload/binary   （multipart，字段名 file）
→ data.fileName = "openapi/xxxx.png"
```
- 提交前务必看 `promptTips` 里有没有非空 `node_errors`。
- `instanceType` 可选 `default / plus / ultra`，价格与排队速度不同。

## 7. 常见问题

| 现象 | 原因 | 正解 |
|---|---|---|
| 返回几万条、像全站 | 关键词字段写成 keyword/searchKey | 字段名用 `search` |
| `WORKFLOW_NOT_EXISTS` / `code:380` | 拿 `/ai-detail/` 的 id 当 workflowId | 用检索返回的 `id` |
| `403 TOKEN_MISSION` | 走了站内需登录的 `/api/workflow/*` | 只能走 2/3 节接口 |
| WebFetch 只拿到几百字节 | SPA 空壳 | 不要抓页面 |
| `steps` 改了不生效 | 字段是 `<link N>`，值来自上游 PrimitiveInt | 覆盖 `N.value` |
| 排序参数没反应 | 接口不支持 sort | 本地排序 |
| 应用搜不到 | RH 没有应用检索接口 | 先用工作流检索，再人工确认对应 app |
