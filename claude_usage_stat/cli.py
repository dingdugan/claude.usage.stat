"""命令行入口 —— 子命令: report (默认) / html / config。"""
import argparse
import os
import subprocess
import sys
import webbrowser
from datetime import datetime, timedelta

from . import __version__, html as html_mod, report as report_mod
from .config import CONFIG_PATH, effective_pricing, load_config
from .scanner import scan

SUBCOMMANDS = {"report", "html", "config"}
DEFAULT_HTML_PATH = "~/.cache/claude-usage-stat/usage_report.html"


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="claude-usage-stat",
        description="查看 Claude Code 的 token 用量与等价花费估算。",
    )
    p.add_argument("-V", "--version", action="version",
                   version=f"claude-usage-stat {__version__}")
    sub = p.add_subparsers(dest="command")

    rp = sub.add_parser("report", help="终端报告(默认)")
    for sp in (rp,):
        sp.add_argument("--days", type=int, metavar="N", help="最近 N 天(1=今天)")
        sp.add_argument("--from", dest="dfrom", metavar="YYYY-MM-DD", help="起始日期")
        sp.add_argument("--to", dest="dto", metavar="YYYY-MM-DD", help="结束日期")
        sp.add_argument("--top", type=int, metavar="N", help="排行榜条数")
        sp.add_argument("--dir", metavar="PATH", help="自定义 projects 目录")
    rp.add_argument("--no-color", action="store_true", help="关闭颜色输出")

    hp = sub.add_parser("html", help="生成并打开 HTML 仪表盘")
    hp.add_argument("--dir", metavar="PATH", help="自定义 projects 目录")
    hp.add_argument("-o", "--output", metavar="PATH", help="HTML 输出路径")
    hp.add_argument("--no-open", action="store_true", help="只生成不打开浏览器")

    cp = sub.add_parser("config", help="查看 / 编辑配置")
    cp.add_argument("action", nargs="?", default="show",
                    choices=["show", "path", "edit"], help="show(默认) / path / edit")

    return p


def _resolve_range(daily, days, dfrom, dto):
    all_dates = sorted({r["d"] for r in daily})
    d_from, d_to = all_dates[0], all_dates[-1]
    if days:
        end = datetime.strptime(d_to, "%Y-%m-%d")
        d_from = (end - timedelta(days=days - 1)).strftime("%Y-%m-%d")
    if dfrom:
        d_from = dfrom
    if dto:
        d_to = dto
    return d_from, d_to


def _load_data(cfg, dir_override):
    projects_dir = os.path.expanduser(dir_override or cfg["projects_dir"])
    if not os.path.isdir(projects_dir):
        print(f"找不到 Claude Code 项目目录: {projects_dir}", file=sys.stderr)
        print("用 `claude-usage-stat config edit` 修改 projects_dir。", file=sys.stderr)
        sys.exit(1)
    sessions, daily = scan(projects_dir, effective_pricing(cfg))
    if not daily:
        print("没有发现任何用量数据。", file=sys.stderr)
        sys.exit(1)
    return sessions, daily


def _cmd_report(args, cfg) -> int:
    sessions, daily = _load_data(cfg, args.dir)
    d_from, d_to = _resolve_range(daily, args.days, args.dfrom, args.dto)
    use_color = (not args.no_color) and sys.stdout.isatty()
    text = report_mod.render(
        sessions, daily,
        d_from=d_from, d_to=d_to,
        top=args.top or cfg["default_top"],
        use_color=use_color,
        monthly_budget=cfg.get("monthly_budget_usd"),
    )
    print(text)
    return 0


def _cmd_html(args, cfg) -> int:
    sessions, daily = _load_data(cfg, args.dir)
    out_path = html_mod.generate(
        sessions, daily, args.output or DEFAULT_HTML_PATH)
    print(f"已生成: {out_path}")
    if not args.no_open:
        webbrowser.open("file://" + out_path)
    return 0


def _cmd_config(args) -> int:
    if args.action == "path":
        print(CONFIG_PATH)
        return 0
    load_config()  # 确保文件存在
    if args.action == "edit":
        editor = os.environ.get("EDITOR")
        if not editor:
            editor = "open" if sys.platform == "darwin" else "nano"
        subprocess.call([editor, CONFIG_PATH])
        return 0
    print(f"配置文件: {CONFIG_PATH}\n")
    with open(CONFIG_PATH, encoding="utf-8") as fh:
        print(fh.read().rstrip())
    return 0


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    # 没给子命令时:有参数 -> 当作 report;无参数 -> 用配置里的 default_command
    if not argv:
        argv = [load_config().get("default_command", "report")]
    elif argv[0] not in SUBCOMMANDS and argv[0] not in ("-h", "--help", "-V", "--version"):
        argv = ["report"] + argv

    args = _build_parser().parse_args(argv)

    if args.command == "config":
        return _cmd_config(args)

    cfg = load_config()
    if args.command == "html":
        return _cmd_html(args, cfg)
    return _cmd_report(args, cfg)


if __name__ == "__main__":
    sys.exit(main())
