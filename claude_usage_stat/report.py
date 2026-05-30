"""终端报告渲染 —— 带 ANSI 颜色和块字符图表。"""
import shutil
from collections import defaultdict
from datetime import datetime

_USE_COLOR = True

BLUE = "38;5;39"      # 输入
ORANGE = "38;5;215"   # 输出
GREEN = "38;5;78"     # 缓存读
PURPLE = "38;5;141"   # 缓存写
DIM = "38;5;244"
BOLD = "1"
CYAN = "38;5;80"
TRACK = "38;5;238"
RED = "38;5;203"

PALETTE = {"输入": BLUE, "输出": ORANGE, "缓存读": GREEN, "缓存写": PURPLE}


def c(code: str, s: str) -> str:
    return f"\x1b[{code}m{s}\x1b[0m" if _USE_COLOR else s


def fmt(n: float) -> str:
    n = float(n)
    if n >= 1e9:
        return f"{n / 1e9:.2f}B"
    if n >= 1e6:
        return f"{n / 1e6:.2f}M"
    if n >= 1e3:
        return f"{n / 1e3:.1f}k"
    return str(int(n))


def usd(n: float) -> str:
    return f"${n:,.2f}" if n < 100 else f"${n:,.0f}"


def _wide(ch: str) -> bool:
    o = ord(ch)
    return (
        0x1100 <= o <= 0x115F or 0x2E80 <= o <= 0x303E or 0x3041 <= o <= 0x33FF
        or 0x3400 <= o <= 0x4DBF or 0x4E00 <= o <= 0x9FFF or 0xA000 <= o <= 0xA4CF
        or 0xAC00 <= o <= 0xD7A3 or 0xF900 <= o <= 0xFAFF or 0xFE30 <= o <= 0xFE4F
        or 0xFF00 <= o <= 0xFF60 or 0xFFE0 <= o <= 0xFFE6
    )


def disp_width(s: str) -> int:
    return sum(2 if _wide(ch) else 1 for ch in s)


def pad(s: str, width: int) -> str:
    return s + " " * max(0, width - disp_width(s))


def trunc(s: str, width: int) -> str:
    if disp_width(s) <= width:
        return s
    out = ""
    w = 0
    for ch in s:
        cw = 2 if _wide(ch) else 1
        if w + cw > width - 1:
            break
        out += ch
        w += cw
    return out + "…"


def bar(value: float, vmax: float, width: int, color: str) -> str:
    filled = round(value / vmax * width) if vmax > 0 else 0
    filled = max(0, min(width, filled))
    return c(color, "█" * filled) + c(TRACK, "░" * (width - filled))


def render(sessions, daily, *, d_from, d_to, top, use_color, monthly_budget=None):
    """渲染一份终端报告字符串。"""
    global _USE_COLOR
    _USE_COLOR = use_color

    W = min(shutil.get_terminal_size((92, 24)).columns, 100)
    rows = [r for r in daily if d_from <= r["d"] <= d_to]

    if not rows:
        return f"\n  {d_from} ~ {d_to} 区间内没有用量数据。\n"

    I = O = CR = CW = 0
    COST = 0.0
    by_day = defaultdict(lambda: {"tok": 0, "cost": 0.0})
    by_proj = defaultdict(lambda: {"tok": 0, "cost": 0.0, "sids": set()})
    by_sess = defaultdict(lambda: {"tok": 0, "cost": 0.0})
    for r in rows:
        tok = r["i"] + r["o"] + r["cr"] + r["cw"]
        I += r["i"]; O += r["o"]; CR += r["cr"]; CW += r["cw"]; COST += r["cost"]
        by_day[r["d"]]["tok"] += tok
        by_day[r["d"]]["cost"] += r["cost"]
        proj = sessions.get(r["sid"], {}).get("proj", "(未知)")
        by_proj[proj]["tok"] += tok
        by_proj[proj]["cost"] += r["cost"]
        by_proj[proj]["sids"].add(r["sid"])
        by_sess[r["sid"]]["tok"] += tok
        by_sess[r["sid"]]["cost"] += r["cost"]
    TOTAL = I + O + CR + CW
    n_days = len(by_day)

    out = []

    # 标题框
    title = " Claude Code 用量统计 "
    info = f" {d_from} ~ {d_to}  ·  活跃 {n_days} 天  ·  {len(by_sess)} 个 session "
    inner = W - 2
    out.append(c(CYAN, "╭─" + title + "─" * (inner - disp_width(title) - 1) + "╮"))
    out.append(c(CYAN, "│") + c(DIM, pad(info, inner)) + c(CYAN, "│"))
    out.append(c(CYAN, "╰" + "─" * inner + "╯"))
    out.append("")

    # 月度预算(可选)
    if monthly_budget and monthly_budget > 0:
        month = datetime.now().strftime("%Y-%m")
        mcost = sum(r["cost"] for r in daily if r["d"][:7] == month)
        pct = mcost / monthly_budget * 100
        col = RED if pct >= 100 else (ORANGE if pct >= 80 else GREEN)
        out.append(
            "  " + c(DIM, "本月预算") + " "
            + bar(mcost, monthly_budget, W - 34, col)
            + f"  {usd(mcost)} / {usd(monthly_budget)}  " + c(col, f"{pct:.0f}%")
        )
        out.append("")

    # 概览
    cells = [
        ("总 Token", fmt(TOTAL)),
        ("净 Token", fmt(I + O + CW)),
        ("花费(估)", usd(COST)),
        ("日均 Token", fmt(round(TOTAL / max(1, n_days)))),
        ("项目数", str(len(by_proj))),
        ("Session", str(len(by_sess))),
    ]
    cw = W // len(cells)
    off = len(c(BOLD, "")) if _USE_COLOR else 0
    out.append("".join(pad("  " + k, cw) for k, _ in cells))
    out.append("".join(pad("  " + c(BOLD, v), cw + off) for _, v in cells))
    out.append(c(DIM, "  净 Token = 输入+输出+缓存写,不含缓存读(对齐 Claude Code 界面)"))
    out.append("")

    # Token 构成
    out.append(c(BOLD, "Token 构成"))
    bw = W - 26
    for name, val in (("输入", I), ("输出", O), ("缓存读", CR), ("缓存写", CW)):
        pct = (val / TOTAL * 100) if TOTAL else 0
        out.append(
            "  " + pad(name, 8) + bar(val, TOTAL, bw, PALETTE[name])
            + "  " + pad(fmt(val), 8) + c(DIM, f"{pct:5.1f}%")
        )
    out.append("")

    # 每日用量(最近 30 天)
    out.append(c(BOLD, "每日用量"))
    days = sorted(by_day)
    shown = days[-30:]
    day_max = max(by_day[d]["tok"] for d in shown)
    if len(days) > 30:
        out.append(c(DIM, f"  (共 {len(days)} 天,仅显示最近 30 天)"))
    dbw = W - 34
    for d in shown:
        o = by_day[d]
        out.append(
            "  " + c(DIM, d) + "  " + bar(o["tok"], day_max, dbw, CYAN)
            + "  " + pad(fmt(o["tok"]), 8) + c(DIM, pad(usd(o["cost"]), 9))
        )
    out.append("")

    # 项目排行
    out.append(c(BOLD, "消耗最多的项目"))
    proj_arr = sorted(by_proj.items(), key=lambda kv: kv[1]["tok"], reverse=True)
    pmax = proj_arr[0][1]["tok"] if proj_arr else 1
    name_w = 18
    pbw = W - name_w - 32
    for name, o in proj_arr[:top]:
        pct = (o["tok"] / TOTAL * 100) if TOTAL else 0
        out.append(
            "  " + pad(trunc(name, name_w), name_w) + " "
            + bar(o["tok"], pmax, pbw, GREEN)
            + " " + pad(fmt(o["tok"]), 8) + pad(usd(o["cost"]), 9)
            + c(DIM, f"{len(o['sids']):>3} sess  {pct:4.1f}%")
        )
    out.append("")

    # Session 排行
    out.append(c(BOLD, "消耗最多的 Session"))
    sess_arr = sorted(by_sess.items(), key=lambda kv: kv[1]["tok"], reverse=True)
    title_w = W - 32
    for sid, o in sess_arr[:top]:
        meta = sessions.get(sid, {})
        out.append(
            "  " + pad(trunc(meta.get("title", "(无标题)"), title_w), title_w) + "  "
            + pad(fmt(o["tok"]), 9) + pad(usd(o["cost"]), 9)
        )
        out.append("  " + c(DIM, f"{sid[:8]} · {meta.get('proj', '?')}"))
    out.append("")
    out.append(c(DIM, "  花费为按官方 API 标准价的等价估算,非订阅实际计费。"))
    out.append("")

    return "\n".join(out)
