# runninghub-workflow-ops

用于操作 RunningHub（RH）云端 ComfyUI 工作流的命令行工具，可检索工作流、查看节点和应用输入、提交任务并查询结果。

本目录也包含 Agent Skill 说明，可与命令行工具配合使用。

## 注意事项

工作流检索关键词字段使用 `search`；`keyword` 和 `searchKey` 会被忽略。`workflowId`、`webappId` 和 RHTV 的 `skillId` 用途不同，不能互换。若节点字段显示为 `<link N>`，需要修改上游节点的对应字段，例如 `164.value`。

## 安装

### 作为 Agent Skill

#### WorkBuddy

```bash
cp -R runninghub-workflow-ops ~/.workbuddy/skills/
chmod +x ~/.workbuddy/skills/runninghub-workflow-ops/scripts/rh.py
```

#### GitHub Copilot

用户级安装：

```bash
mkdir -p ~/.copilot/skills
cp -R runninghub-workflow-ops ~/.copilot/skills/
```

也可将 Skill 放在当前仓库的 `.github/skills/` 下，供该仓库中的 Copilot 使用：

```bash
mkdir -p .github/skills
cp -R runninghub-workflow-ops .github/skills/
```

脚本也可直接通过 Python 运行；复制到其他目录后，请按实际路径调整命令。

### 作为命令行工具

```bash
cd runninghub-workflow-ops
export RUNNINGHUB_API_KEY="你的 API Key"
python3 scripts/rh.py coins
```

需要 Python 3.8+，不依赖第三方 Python 包。

## 用法

```bash
rh.py search "首尾帧" --size 15          # 检索工作流库（服务端关键词）
rh.py search "视角" --type skill          # 检索 RHTV 画布技能库（本地过滤）
rh.py json <workflowId> --save ./rh_workflows --name "名称_作者"
rh.py inputs <workflowId>                 # 列出人可改节点，专为构造 nodeInfoList
rh.py app <webappId>                      # 查看应用输入面板
rh.py coins                               # RH 币余额
rh.py run --workflow <id> --param 163.text="..." --param 110.image=@./a.png   # 默认 dry-run
rh.py run --workflow <id> ... --confirm --download ./out --tag shot01         # 确认后提交
rh.py query <taskId> --download ./out
```

| 子命令 | 作用 | 花钱 |
|---|---|---|
| `search` | 工作流库 / RHTV 技能库检索 | 否 |
| `json` | 取工作流 API 格式 JSON（可归档） | 否 |
| `inputs` | 打印可改节点与字段现值 | 否 |
| `app` | AI 应用详情 + 输入面板 | 否 |
| `coins` | 余额 / 进行中任务 | 否 |
| `run` | 提交任务（**默认 dry-run**，`--confirm` 才真提交） | **是** |
| `query` | 查任务状态、下载结果 | 否 |

## 密钥与提交

- `run` 默认不提交任务；添加 `--confirm` 后才会提交任务并消耗 RH 币。使用 `--param NODE.FIELD=@路径` 时，文件会在组装请求时上传，即使没有添加 `--confirm`。
- API Key 从环境变量 `RUNNINGHUB_API_KEY` 读取。
- 只有 `--param NODE.FIELD=@路径` 会上传本地文件。

## 接口速查

| 能力 | 端点 |
|---|---|
| 工作流检索 | `POST /api/search/workflow` `{"search","page","size"}` |
| 取 API JSON | `POST /api/openapi/getJsonApiFormat` `{"apiKey","workflowId"}` |
| 应用详情 | `POST /api/webapp/detail` `{"webappId"}` |
| RHTV 技能库 | `POST rhtv.runninghub.cn/canvas/skill/list` |
| 余额 | `POST /uc/openapi/accountStatus` `{"apiKey"}` |
| 提交 / 查询 | `POST /openapi/v2/run/{ai-app|workflow}/<id>`、`POST /openapi/v2/query` |

接口字段及已知限制见 [`references/endpoints.md`](references/endpoints.md)。

## 已知限制

- `POST /openapi/v2/run/workflow/{workflowId}` 已实现但尚未实测。首次使用时请留意费用，并检查返回的 `promptTips.node_errors`。
- nodeInfoList 只能改字段**值**，不能增删节点/更换 LoRA；想换 LoRA 只能挑另一条工作流。
- RHTV 技能库只读，不能提交运行。
