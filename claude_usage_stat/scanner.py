"""扫描 Claude Code 的 session JSONL,聚合 token 用量与等价花费。"""
import glob
import json
import os
from collections import defaultdict
from datetime import datetime

from .pricing import price_for


def local_date(ts: str) -> str:
    """ISO 时间戳 -> 本地时区的 YYYY-MM-DD。"""
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.astimezone().strftime("%Y-%m-%d")
    except Exception:
        return ""


def project_root(cwd: str) -> str:
    """把 worktree 路径归并回主项目根。"""
    if not cwd:
        return ""
    marker = "/.claude/worktrees/"
    if marker in cwd:
        return cwd.split(marker)[0]
    return cwd


def extract_text(content) -> str:
    """user message 的 content 可能是 str 或 list,取首段纯文本。"""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        for blk in content:
            if isinstance(blk, dict):
                if blk.get("type") == "text" and blk.get("text"):
                    return blk["text"]
                if blk.get("type") == "tool_result":
                    return ""
    return ""


def scan(projects_dir: str, pricing: dict):
    """返回 (sessions, daily)。

    sessions: {sid: {proj, projPath, title, branch}}
    daily:    [{d, sid, i, o, cr, cw, cost}]  —— 按 (session, 日期) 聚合
    """
    files = glob.glob(os.path.join(projects_dir, "*", "*.jsonl"))
    sessions = {}
    daily = []
    seen = set()  # 去重 (requestId:message.id)

    for fp in files:
        sid = os.path.splitext(os.path.basename(fp))[0]
        folder = os.path.basename(os.path.dirname(fp))
        cwd = ""
        title = ""
        branch = ""
        agg = defaultdict(lambda: {"i": 0, "o": 0, "cr": 0, "cw": 0, "cost": 0.0})

        try:
            with open(fp, "r", encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except Exception:
                        continue

                    if not cwd and rec.get("cwd"):
                        cwd = rec["cwd"]
                    if not branch and rec.get("gitBranch"):
                        branch = rec["gitBranch"]

                    rtype = rec.get("type")

                    if not title and rtype == "user":
                        txt = extract_text(rec.get("message", {}).get("content")).strip()
                        if txt and not txt.startswith("<") and "tool_result" not in txt[:40]:
                            title = txt.replace("\n", " ")[:90]

                    if rtype != "assistant":
                        continue
                    msg = rec.get("message", {})
                    usage = msg.get("usage")
                    if not usage:
                        continue

                    key = f"{rec.get('requestId', '')}:{msg.get('id', '')}"
                    if key in seen:
                        continue
                    seen.add(key)

                    model = msg.get("model") or rec.get("model") or ""
                    p = price_for(model, pricing)

                    inp = usage.get("input_tokens", 0) or 0
                    out = usage.get("output_tokens", 0) or 0
                    cr = usage.get("cache_read_input_tokens", 0) or 0
                    cc = usage.get("cache_creation", {}) or {}
                    cw5 = cc.get("ephemeral_5m_input_tokens", 0) or 0
                    cw1h = cc.get("ephemeral_1h_input_tokens", 0) or 0
                    if not (cw5 or cw1h):
                        cw5 = usage.get("cache_creation_input_tokens", 0) or 0
                    cw = cw5 + cw1h

                    cost = (inp * p["in"] + out * p["out"] + cr * p["cr"]
                            + cw5 * p["cw5"] + cw1h * p["cw1h"]) / 1e6

                    d = local_date(rec.get("timestamp", ""))
                    if not d:
                        continue
                    b = agg[d]
                    b["i"] += inp
                    b["o"] += out
                    b["cr"] += cr
                    b["cw"] += cw
                    b["cost"] += cost
        except Exception:
            continue

        if not agg:
            continue

        root = project_root(cwd)
        proj_name = os.path.basename(root) if root else folder
        sessions[sid] = {
            "proj": proj_name or folder,
            "projPath": root or folder,
            "title": title or "(无标题)",
            "branch": branch,
        }
        for d, b in agg.items():
            daily.append({
                "d": d, "sid": sid,
                "i": b["i"], "o": b["o"], "cr": b["cr"], "cw": b["cw"],
                "cost": round(b["cost"], 4),
            })

    return sessions, daily
