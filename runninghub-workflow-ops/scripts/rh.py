#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rh.py — RunningHub 工作流操作 CLI（零第三方依赖）

子命令：
  search   检索 RH 工作流库（服务端关键词）/ RHTV 画布技能库（本地过滤）
  json     取工作流的 ComfyUI API 格式 JSON（可归档）
  inputs   打印该工作流里「人可改」的节点与字段（用于构造 nodeInfoList）
  app      查 AI 应用详情和 inputNodes
  coins    查 RH 币余额
  run      提交任务（**默认 dry-run**，必须显式 --confirm 才真提交，且会花币）
  query    查任务并可选下载结果

API Key：环境变量 RUNNINGHUB_API_KEY
官方端点真值与坑：见 references/endpoints.md

示例：
  python3 rh.py search "首尾帧" --size 15
  python3 rh.py search "多视角" --type skill
  python3 rh.py json <workflowId> --save ./rh_workflows
  python3 rh.py inputs <workflowId>
  python3 rh.py app <webappId>
  python3 rh.py coins
  python3 rh.py query <taskId> --download ./out --tag shot01
"""
import argparse
import json
import mimetypes
import os
import sys
import time
import urllib.error
import urllib.request
from collections import Counter

SITE = "https://www.runninghub.cn"
RHTV = "https://rhtv.runninghub.cn"
V2 = SITE + "/openapi/v2"


# ---------------------------------------------------------------- 基础
def api_key(required=False):
    k = os.environ.get("RUNNINGHUB_API_KEY", "").strip()
    if not k and required:
        sys.exit("❌ 环境变量 RUNNINGHUB_API_KEY 未设置")
    return k


def post(url, payload=None, timeout=60, bearer=False, raw=None, ctype=None):
    headers = {}
    if bearer:
        headers["Authorization"] = f"Bearer {api_key(True)}"
    if raw is not None:
        body = raw
        headers["Content-Type"] = ctype or "application/octet-stream"
    elif payload is not None:
        body = json.dumps(payload).encode()
        headers["Content-Type"] = "application/json"
    else:
        body = None
    req = urllib.request.Request(url, data=body, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8", "ignore"))
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode("utf-8", "ignore"))
        except Exception:
            return {"code": f"HTTP{e.code}", "msg": "非 JSON 响应"}
    except Exception as e:
        return {"code": "ERR", "msg": str(e)[:200]}


def clip(s, n=52):
    s = " ".join(str(s).split())
    return s if len(s) <= n else s[: n - 1] + "…"


def die(res, what):
    print(f"❌ {what}失败：code={res.get('code')} msg={clip(res.get('msg') or res, 200)}")
    sys.exit(2)


# ---------------------------------------------------------------- search
def cmd_search(a):
    if a.type == "skill":
        recs, total = [], None
        page = 1
        while True:
            r = post(f"{RHTV}/canvas/skill/list",
                     {"page": page, "size": 200, "category": "CANVAS_AGENT", "type": "COMMON"}, 40)
            if r.get("code") not in (0, "0", None):
                die(r, "RHTV 技能列表")
            d = r.get("data") or {}
            batch = d.get("records") if isinstance(d, dict) else d
            total = d.get("total") if isinstance(d, dict) else total
            if not batch:
                break
            recs += batch
            if total and len(recs) >= int(total):
                break
            page += 1
            if page > 10:
                break
        if a.kw:
            kw = a.kw.lower()
            recs = [x for x in recs
                    if kw in (str(x.get("name", "")) + str(x.get("intro", "")) +
                              str(x.get("useScenario", "")) + str(x.get("presetPrompt", ""))).lower()]
        recs.sort(key=lambda x: -(x.get("useCount") or 0))
        if a.json:
            print(json.dumps(recs, ensure_ascii=False, indent=1))
            return
        print(f"# RHTV 画布技能库 ｜ 命中 {len(recs)} 条（全库 {total}）｜ 按用量降序")
        print(f"{'skillId':<21}{'用量':>6}{'收藏':>6}  {'类型':<6}名称 / 简介")
        for x in recs[: a.size]:
            print(f"{x.get('skillId',''):<21}{x.get('useCount',0):>6}{x.get('collectCount',0):>6}  "
                  f"{str(x.get('outputType','')):<6}{clip(x.get('name'), 26)} / {clip(x.get('intro'), 46)}")
        if len(recs) > a.size:
            print(f"… 另有 {len(recs)-a.size} 条，用 --size 扩大")
        return

    # 工作流库：服务端关键词
    if not a.kw:
        sys.exit("❌ 工作流库检索必须给关键词（服务端只认 search 字段）")
    r = post(f"{SITE}/api/search/workflow", {"search": a.kw, "page": a.page, "size": a.size}, 40)
    if r.get("code") not in (0, "0", None):
        die(r, "工作流检索")
    d = r.get("data") or {}
    recs = d.get("records") or []
    if a.json:
        print(json.dumps(recs, ensure_ascii=False, indent=1))
        return
    print(f"# RH 工作流库 ｜ 关键词「{a.kw}」命中 total={d.get('total')} ｜ 第 {a.page+1}/{d.get('pages')} 页")
    print(f"{'workflowId':<21}{'用量':>7}{'收藏':>6}  名称 / 作者 / 标签")
    for x in recs:
        st = x.get("statisticsInfo") or {}
        owner = (x.get("owner") or {}).get("nickName") or (x.get("owner") or {}).get("name") or "-"
        tags = ",".join(t.get("name", "") for t in (x.get("tags") or [])[:3])
        print(f"{x.get('id',''):<21}{st.get('useCount','0'):>7}{st.get('collectCount','0'):>6}  "
              f"{clip(x.get('name'), 34)} / {clip(owner, 12)} / {tags}")
    if d.get("hasNext"):
        print(f"→ 下一页：--page {a.page+1}")


# ---------------------------------------------------------------- json / inputs
INTEREST = {
    "LoadImage", "LoadImageMask", "LoadVideo", "VHS_LoadVideo", "VHS_LoadImages",
    "CLIPTextEncode", "TextEncodeQwenImageEdit", "TextEncodeQwenImageEditPlus",
    "EmptyLatentImage", "EmptySD3LatentImage", "EmptyHunyuanLatentVideo",
    "WanImageToVideo", "WanFirstLastFrameToVideo", "WanFunInpaintToVideo",
    "WanVaceToVideo", "LTXVAddGuide", "KSampler", "KSamplerAdvanced",
    "LoraLoader", "LoraLoaderModelOnly", "UNETLoader", "UnetLoaderGGUF",
    "CheckpointLoaderSimple", "CLIPLoader", "VAELoader", "CLIPVisionLoader",
    "CreateVideo", "SaveVideo", "SaveImage", "VHS_VideoCombine",
}


def load_prompt(workflow_id):
    r = post(f"{SITE}/api/openapi/getJsonApiFormat",
             {"apiKey": api_key(True), "workflowId": str(workflow_id)}, 120)
    if r.get("code") not in (0, "0", None):
        die(r, "取工作流 JSON（确认 id 是 workflowId，不是 /ai-detail/ 的 id）")
    d = r.get("data")
    pr = d.get("prompt") if isinstance(d, dict) else d
    if isinstance(pr, str):                      # data.prompt 是二次编码的字符串
        pr = json.loads(pr)
    if not isinstance(pr, dict):
        die({"code": "PARSE", "msg": "data.prompt 结构异常"}, "解析工作流 JSON")
    return r, pr


def cmd_json(a):
    raw, pr = load_prompt(a.id)
    types = Counter(v.get("class_type") for v in pr.values() if isinstance(v, dict))
    print(f"# workflowId={a.id} ｜ 节点数 {len(pr)}")
    print("# 节点类型：" + ", ".join(f"{k}×{v}" for k, v in types.most_common(12)))
    if a.save:
        os.makedirs(a.save, exist_ok=True)
        label = a.name or "workflow"
        p = os.path.join(a.save, f"{label}_{a.id}.json")
        with open(p, "w", encoding="utf-8") as f:
            json.dump(raw, f, ensure_ascii=False, indent=1)
        print(f"[saved] → {p}")
    if a.dump:
        print(json.dumps(pr, ensure_ascii=False, indent=1))


def cmd_inputs(a):
    _, pr = load_prompt(a.id)
    rows = []
    for nid, node in pr.items():
        if not isinstance(node, dict):
            continue
        ct = node.get("class_type", "")
        ins = node.get("inputs") or {}
        hit = ct in INTEREST or any(
            isinstance(v, str) and len(v) > 60 for v in ins.values())
        if not hit:
            continue
        parts = []
        for k, v in ins.items():
            if isinstance(v, list):
                parts.append(f"{k}=<link {v[0]}>")
            elif isinstance(v, str):
                parts.append(f"{k}=" + (json.dumps(clip(v, 46), ensure_ascii=False) if len(v) > 46
                                        else json.dumps(v, ensure_ascii=False)))
            else:
                parts.append(f"{k}={v}")
        rows.append((ct, nid, " ".join(parts)))
    rows.sort()
    print(f"# workflowId={a.id} ｜ 可改节点 {len(rows)} 个（nodeInfoList 的 nodeId 就是左列第二栏）")
    for ct, nid, txt in rows:
        print(f"\n[{ct}] nodeId={nid}\n  {txt}")
    print("\n# 提交时形如：--param 470.image=@/path/a.png --param 516.value=\"提示词\"")


# ---------------------------------------------------------------- app / coins
def cmd_app(a):
    r = post(f"{SITE}/api/webapp/detail", {"webappId": str(a.id)}, 40)
    if r.get("code") not in (0, "0", None):
        die(r, "查 AI 应用详情")
    d = r.get("data") or {}
    st = d.get("statisticsInfo") or {}
    print(f"# {d.get('name')} ｜ webappId={a.id} ｜ workflowId={d.get('workflowId')}")
    owner = d.get("owner") or {}
    print(f"# 作者={owner.get('nickName') or owner.get('name') or '-'} 用量={st.get('useCount')} "
          f"收藏={st.get('collectCount')} 平均耗时={d.get('avgRunningSeconds')}s "
          f"成功率={d.get('runningSuccessRate')}")
    nodes = d.get("inputNodes") or []
    print(f"{'nodeId':<8}{'fieldName':<18}{'描述':<16}默认值")
    for n in nodes:
        print(f"{str(n.get('nodeId','')):<8}{str(n.get('fieldName','')):<18}"
              f"{clip(n.get('descriptionCn') or n.get('description') or '', 14):<16}"
              f"{clip(str(n.get('fieldValue')), 40)}")
    if a.save:
        os.makedirs(a.save, exist_ok=True)
        p = os.path.join(a.save, f"app_{a.id}_detail.json")
        with open(p, "w", encoding="utf-8") as f:
            json.dump(r, f, ensure_ascii=False, indent=1)
        print(f"[saved] → {p}")


def cmd_coins(a):
    r = post(f"{SITE}/uc/openapi/accountStatus", {"apiKey": api_key(True)}, 30)
    if r.get("code") not in (0, "0", None):
        die(r, "查余额")
    d = r.get("data") or {}
    print(f"RH 币余额={d.get('remainCoins')} ｜ 进行中任务={d.get('currentTaskCounts')} ｜ 账户类型={d.get('apiType')}")


# ---------------------------------------------------------------- run / query
def upload(path):
    boundary = "----rh" + str(int(time.time() * 1000))
    fn = os.path.basename(path)
    mime = mimetypes.guess_type(fn)[0] or "application/octet-stream"
    with open(path, "rb") as f:
        content = f.read()
    body = b"".join([
        f"--{boundary}\r\n".encode(),
        f'Content-Disposition: form-data; name="file"; filename="{fn}"\r\n'
        f"Content-Type: {mime}\r\n\r\n".encode(),
        content,
        f"\r\n--{boundary}--\r\n".encode(),
    ])
    r = post(f"{V2}/media/upload/binary", raw=body, bearer=True,
             ctype=f"multipart/form-data; boundary={boundary}", timeout=300)
    if r.get("code") != 0:
        die(r, "上传")
    name = (r.get("data") or {}).get("fileName")
    print(f"[upload] ✅ {fn} ({len(content)/1048576:.2f} MB) → {name}")
    return name


def parse_params(pairs):
    out = []
    for p in pairs or []:
        if "=" not in p or "." not in p.split("=", 1)[0]:
            sys.exit(f"❌ --param 格式应为 NODE.FIELD=VALUE，收到：{p}")
        lhs, val = p.split("=", 1)
        nid, field = lhs.split(".", 1)
        if val.startswith("@"):
            val = upload(os.path.expanduser(val[1:]))
        out.append({"nodeId": nid, "fieldName": field, "fieldValue": val, "description": ""})
    return out


def cmd_run(a):
    if bool(a.workflow) == bool(a.app):
        sys.exit("❌ --workflow 与 --app 二选一")
    target = f"/run/workflow/{a.workflow}" if a.workflow else f"/run/ai-app/{a.app}"
    body = {"nodeInfoList": parse_params(a.param), "instanceType": a.instance,
            "usePersonalQueue": "false"}
    if a.webhook:
        body["webhookUrl"] = a.webhook

    before = post(f"{SITE}/uc/openapi/accountStatus", {"apiKey": api_key(True)}, 30)
    coins = (before.get("data") or {}).get("remainCoins")
    print(f"[coins] 提交前余额={coins}")
    print(f"[POST] {V2}{target}")
    print("[body] " + json.dumps(body, ensure_ascii=False, indent=1))

    if not a.confirm:
        print("\n⚠️ dry-run：未提交。核对上面的 body 与余额后再加 --confirm（提交会消耗 RH 币）。")
        return

    r = post(V2 + target, body, bearer=True, timeout=120)
    tid = r.get("taskId")
    if not tid:
        die(r, "提交任务")
    print(f"[submit] taskId={tid} status={r.get('status')}")

    t0 = time.time()
    while True:
        time.sleep(8)
        q = post(f"{V2}/query", {"taskId": tid}, bearer=True, timeout=60)
        st = q.get("status")
        if st in ("SUCCESS", "FAILED"):
            print(f"[query] status={st} 用时 {(time.time()-t0)/60:.1f} 分钟")
            if st == "FAILED":
                print(json.dumps(q, ensure_ascii=False)[:800])
                sys.exit(2)
            fetch_results(q, a.download, a.tag)
            return
        if time.time() - t0 > a.timeout:
            sys.exit(f"⏰ 超时（{a.timeout}s），taskId={tid}，稍后用 query 查")
        print(f"[query] {st} {time.time()-t0:.0f}s", flush=True)


def fetch_results(q, outdir, tag):
    files = []
    for i, item in enumerate(q.get("results") or []):
        u = item.get("url")
        if not u:
            if item.get("text"):
                print("[text]", str(item["text"])[:400])
            continue
        if not outdir:
            print("[result]", u)
            continue
        os.makedirs(outdir, exist_ok=True)
        ext = os.path.splitext(u.split("?")[0])[1] or ".png"
        p = os.path.join(outdir, f"{tag}{'' if i == 0 else f'_{i+1}'}{ext}")
        urllib.request.urlretrieve(u, p)
        files.append(p)
        print("[saved] →", p)
    usage = q.get("usage") or {}
    if usage:
        print(f"[usage] 耗时={usage.get('taskCostTime')}s RH币={usage.get('consumeCoins')} "
              f"金额={usage.get('consumeMoney')}")
    return files


def cmd_query(a):
    r = post(f"{V2}/query", {"taskId": a.task}, bearer=True, timeout=60)
    st = r.get("status")
    print(f"status={st} errorCode={r.get('errorCode')} {clip(r.get('errorMessage') or '', 120)}")
    if st == "SUCCESS":
        fetch_results(r, a.download, a.tag)
    else:
        print(json.dumps(r, ensure_ascii=False)[:800])


# ---------------------------------------------------------------- CLI
def main():
    ap = argparse.ArgumentParser(description="RunningHub 工作流操作 CLI")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("search", help="检索工作流库 / RHTV 技能库")
    s.add_argument("kw", nargs="?", help="关键词")
    s.add_argument("--type", default="workflow", choices=["workflow", "skill"])
    s.add_argument("--page", type=int, default=0)
    s.add_argument("--size", type=int, default=20)
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_search)

    j = sub.add_parser("json", help="取 API 格式 JSON")
    j.add_argument("id")
    j.add_argument("--save", help="存档目录")
    j.add_argument("--name", help="文件名前缀（建议：名称_作者）")
    j.add_argument("--dump", action="store_true", help="同时打印完整节点 JSON")
    j.set_defaults(func=cmd_json)

    i = sub.add_parser("inputs", help="列出可改节点与字段")
    i.add_argument("id")
    i.set_defaults(func=cmd_inputs)

    p = sub.add_parser("app", help="查 AI 应用详情和 inputNodes")
    p.add_argument("id")
    p.add_argument("--save")
    p.set_defaults(func=cmd_app)

    c = sub.add_parser("coins", help="查余额")
    c.set_defaults(func=cmd_coins)

    r = sub.add_parser("run", help="提交任务（默认 dry-run）")
    r.add_argument("--workflow")
    r.add_argument("--app")
    r.add_argument("--param", action="append", metavar="NODE.FIELD=VALUE",
                   help="VALUE 以 @ 开头表示本地文件，会自动上传")
    r.add_argument("--instance", default="default", choices=["default", "plus", "ultra"])
    r.add_argument("--webhook")
    r.add_argument("--timeout", type=int, default=3600)
    r.add_argument("--download", help="结果下载目录")
    r.add_argument("--tag", default="rh")
    r.add_argument("--confirm", action="store_true", help="真正提交（会花币）")
    r.set_defaults(func=cmd_run)

    q = sub.add_parser("query", help="查任务 / 下载结果")
    q.add_argument("task")
    q.add_argument("--download")
    q.add_argument("--tag", default="rh")
    q.set_defaults(func=cmd_query)

    a = ap.parse_args()
    a.func(a)


if __name__ == "__main__":
    main()
