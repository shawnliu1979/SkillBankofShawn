---
name: runninghub-workflow-ops
description: 使用 RunningHub 检索 ComfyUI 工作流和 RHTV 画布技能，查看节点和应用输入、查询余额、提交并查询云端任务。用户需要操作 RunningHub、RH 工作流、workflowId、webappId 或 RHTV 技能时使用。
---

# RunningHub 工作流操作

RunningHub 提供云端 ComfyUI 工作流。本 skill 用 `scripts/rh.py` 检索工作流和画布技能、查看节点与应用输入、提交任务并查询结果。脚本不依赖第三方 Python 包，API Key 从环境变量 `RUNNINGHUB_API_KEY` 读取。

## 一、使用前确认

1. `search / json / inputs / app / coins` 不会提交任务。`run` 默认不提交任务；添加 `--confirm` 才会提交并消耗 RH 币。`--param NODE.FIELD=@路径` 会上传文件，即使没有添加 `--confirm`。提交前先取得用户确认。
2. 区分以下 ID：
   - `workflowId`＝工作流库检索返回的 `id`（取 JSON、跑工作流用）
   - `webappId`＝`/ai-detail/<id>` 页面上的 id（查应用面板用）
   - `skillId`＝RHTV 画布技能（rhtv 域名用）
   混用会报 `WORKFLOW_NOT_EXISTS` 或 `code:380`。
3. RH 页面是 SPA，网页抓取通常拿不到工作流数据；`/api/workflow/*` 需要登录态，会返回 `403 TOKEN_MISSION`。使用下文列出的接口。
4. Key 从环境变量 `RUNNINGHUB_API_KEY` 读取。不要把 Key 写入命令、日志或归档文件。

## 二、检索入口

| 想找什么 | 通道 | 命令 |
|---|---|---|
| ComfyUI 工作流（有节点结构、可提交运行） | `POST /api/search/workflow`，关键词字段 **`search`** | `rh.py search "首尾帧" --size 15` |
| AI 应用面板（`/ai-detail/` 页面） | **没有关键词检索**；已知 webappId 才能查 | `rh.py app <webappId>` |
| RHTV 画布技能（成片级 Agent Skill，非 ComfyUI 工作流） | `POST rhtv.runninghub.cn/canvas/skill/list`，本地关键词过滤 | `rh.py search "视角" --type skill` |

> 工作流检索的关键词字段必须是 `search`。使用 `keyword` 或 `searchKey` 会被忽略，可能返回全站结果。若 `total` 达到数万，先检查请求字段。搜索接口不支持排序参数；需要按用量筛选时，可在本地排序。

## 三、查看工作流结构和输入节点

```bash
rh.py json <workflowId> --save ./rh_workflows --name "名称_作者"
rh.py inputs <workflowId>
```

- `data.prompt` 是**二次编码的 JSON 字符串**（`json.loads` 两次），脚本已处理。
- `inputs` 输出可修改节点及字段现值（nodeId、class_type），可用于构造 `nodeInfoList`。
- 字段显示为 `<link N>` 时，值来自节点 N。例如 `steps=<link 164>` 表示应覆盖上游 PrimitiveInt 节点：`--param 164.value=20`。宽高常见字段为 `160.value` / `161.value`，LoRA 强度字段为 `LoraLoaderModelOnly.strength_model`。
- `nodeInfoList` 只能修改字段值，不能替换或删除节点。需要更换 LoRA 时，选择包含目标 LoRA 的其他工作流。

## 四、查看应用面板

```bash
rh.py app <webappId>
```
输出：name / workflowId / owner / 用量 / **inputNodes（nodeId + fieldName + 描述 + 默认值）**。
该接口可免登录查看应用公开的输入项。工作流详情接口需要登录态；工作流的可修改字段可通过 `inputs` 从节点图中查看。

## 五、余额

```bash
rh.py coins        # → remainCoins / currentTaskCounts / apiType
```
`run` 在提交前会自动打印一次余额，便于记账。

## 六、提交与查询

```bash
# 1) 预览请求：打印 body 和余额，不提交（默认行为）
rh.py run --workflow <workflowId> \
    --param 163.text="a slow dolly-in down a foggy street" \
    --param 110.image=@/path/first.png \
    --param 112.image=@/path/last.png \
    --param 164.value=20

# 2) 确认后提交，并轮询任务、下载结果
rh.py run --workflow <workflowId> ... --confirm --download ./out --tag shot01

# 3) 查询任务
rh.py query <taskId> --download ./out --tag shot01
```
- `--param NODE.FIELD=VALUE`；VALUE 以 `@` 开头＝本地文件，自动上传换 `fileName`。
- `--app <webappId>` 与 `--workflow <workflowId>` 二选一（分别调用 `/run/ai-app/` 和 `/run/workflow/`）。
- 结果里 `usage.consumeCoins` / `taskCostTime` 是记账凭据，脚本会打印。

## 七、保存结果

- 工作流 JSON 存自建目录，命名 `<名称>_<作者>_<workflowId>.json`。
- 应用详情存 `app_<webappId>_detail.json`。
- 检索记录可保存为 `<主题>_检索记录_YYYY-MM-DD.md`，注明关键词和命中的 ID，便于之后复查。

## 八、尚未验证

- `POST /openapi/v2/run/workflow/{workflowId}`（工作流级提交）：脚本支持但尚未实测。首次使用时请留意费用，并检查返回的 `promptTips.node_errors`。
- 公开工作流是否允许 nodeInfoList 覆盖任意字段：取决于该字段是否 `<link>`，逐条按 `inputs` 确认，不要假设。
- RHTV 技能库只读（list/detail），无提交能力。

## 九、相关文件

- `scripts/rh.py` — 全部子命令：`search / json / inputs / app / coins / run / query`
- `references/endpoints.md` — 接口说明、请求/响应字段和测试日期
