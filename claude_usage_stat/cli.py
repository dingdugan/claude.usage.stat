"""命令行入口 —— 子命令: report (默认) / html / archive / schedule / config。"""
import argparse
import os
import subprocess
import sys
import webbrowser
from datetime import datetime, timedelta

from . import __version__, archive as archive_mod, html as html_mod, report as report_mod
from .config import CONFIG_PATH, effective_pricing, load_config

SUBCOMMANDS = {"report", "html", "archive", "schedule", "config"}
DEFAULT_HTML_PATH = "~/.cache/claude-usage-stat/usage_report.html"
LAUNCHD_LABEL = "local.claude-usage-stat.archive"
LAUNCHD_PLIST = os.path.expanduser(f"~/Library/LaunchAgents/{LAUNCHD_LABEL}.plist")
LAUNCHD_LOG = os.path.expanduser("~/.local/share/claude-usage-stat/archive.log")


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="claude-usage-stat",
        description="查看 Claude Code 的 token 用量与等价花费估算。",
    )
    p.add_argument("-V", "--version", action="version",
                   version=f"claude-usage-stat {__version__}")
    sub = p.add_subparsers(dest="command")

    rp = sub.add_parser("report", help="终端报告(默认)")
    rp.add_argument("--days", type=int, metavar="N", help="最近 N 天(1=今天)")
    rp.add_argument("--from", dest="dfrom", metavar="YYYY-MM-DD", help="起始日期")
    rp.add_argument("--to", dest="dto", metavar="YYYY-MM-DD", help="结束日期")
    rp.add_argument("--top", type=int, metavar="N", help="排行榜条数")
    rp.add_argument("--dir", metavar="PATH", help="自定义 projects 目录")
    rp.add_argument("--no-color", action="store_true", help="关闭颜色输出")

    hp = sub.add_parser("html", help="生成并打开 HTML 仪表盘")
    hp.add_argument("--dir", metavar="PATH", help="自定义 projects 目录")
    hp.add_argument("-o", "--output", metavar="PATH", help="HTML 输出路径")
    hp.add_argument("--no-open", action="store_true", help="只生成不打开浏览器")

    ap = sub.add_parser("archive",
                        help="把当前 ~/.claude/projects 增量归档到本地 SQLite")
    ap.add_argument("--dir", metavar="PATH", help="自定义 projects 目录")
    ap.add_argument("--quiet", action="store_true", help="只在出错时输出")

    sp = sub.add_parser("schedule",
                        help="装/卸/查每天自动 archive 的定时任务 (macOS launchd)")
    sp.add_argument("action", choices=["install", "uninstall", "status"])

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


def _refresh_and_load(cfg, dir_override):
    """跑 archive_now() 把最新源数据写进归档,然后从归档读 (sessions, daily)。

    archive 失败不致命 —— 仍然用归档里已有的数据出报告。
    """
    projects_dir = os.path.expanduser(dir_override or cfg["projects_dir"])
    pricing = effective_pricing(cfg)
    if os.path.isdir(projects_dir):
        try:
            archive_mod.archive_now(projects_dir, pricing)
        except Exception as e:
            print(f"warning: archive 失败,用历史归档出报告: {e}", file=sys.stderr)
    else:
        print(f"warning: projects 目录不存在: {projects_dir} (用历史归档)",
              file=sys.stderr)
    sessions, daily = archive_mod.read_archive()
    if not daily:
        print("没有任何用量数据(归档为空,且未找到当前 session)。",
              file=sys.stderr)
        sys.exit(1)
    return sessions, daily


def _cmd_report(args, cfg) -> int:
    sessions, daily = _refresh_and_load(cfg, args.dir)
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
    sessions, daily = _refresh_and_load(cfg, args.dir)
    out_path = html_mod.generate(
        sessions, daily, args.output or DEFAULT_HTML_PATH)
    print(f"已生成: {out_path}")
    if not args.no_open:
        webbrowser.open("file://" + out_path)
    return 0


def _cmd_archive(args, cfg) -> int:
    projects_dir = os.path.expanduser(args.dir or cfg["projects_dir"])
    if not os.path.isdir(projects_dir):
        print(f"错误: projects 目录不存在: {projects_dir}", file=sys.stderr)
        return 1
    pricing = effective_pricing(cfg)
    n_sess, n_rows = archive_mod.archive_now(projects_dir, pricing)
    ns_total, nd_total, size, path = archive_mod.db_stats()
    if not args.quiet:
        print(f"✓ 已扫描 ~/.claude/projects: {n_sess} 个 session, {n_rows} 条日聚合(已 upsert)")
        print(f"  归档累计:  {ns_total} 个 session, {nd_total} 条日记录")
        print(f"  数据库:    {path}  ({size / 1024:.1f} KB)")
    return 0


def _cmd_schedule(args) -> int:
    if sys.platform != "darwin":
        print("schedule 子命令目前只支持 macOS。", file=sys.stderr)
        print("Linux 用 cron,在 crontab -e 加一行:", file=sys.stderr)
        print("  0 3 * * *  $(which claude-usage-stat) archive --quiet", file=sys.stderr)
        return 1

    if args.action == "install":
        launcher = (
            subprocess.run(["which", "claude-usage-stat"], capture_output=True, text=True)
            .stdout.strip()
            or os.path.expanduser("~/.local/bin/claude-usage-stat")
        )
        os.makedirs(os.path.dirname(LAUNCHD_LOG), exist_ok=True)
        # 触发策略:
        #   RunAtLoad = true   登录时跑一次(笔记本早上开盖就归档)
        #   StartInterval 6h   机器醒着每 6 小时跑一次;睡眠时跳过,唤醒后会补跑一次
        # 这两个一起覆盖了"机器关机/睡眠时错过定时"的洞。
        plist = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
            '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
            '<plist version="1.0"><dict>\n'
            f'  <key>Label</key><string>{LAUNCHD_LABEL}</string>\n'
            '  <key>ProgramArguments</key><array>\n'
            f'    <string>{launcher}</string><string>archive</string><string>--quiet</string>\n'
            '  </array>\n'
            '  <key>RunAtLoad</key><true/>\n'
            '  <key>StartInterval</key><integer>21600</integer>\n'
            f'  <key>StandardOutPath</key><string>{LAUNCHD_LOG}</string>\n'
            f'  <key>StandardErrorPath</key><string>{LAUNCHD_LOG}</string>\n'
            '</dict></plist>\n'
        )
        os.makedirs(os.path.dirname(LAUNCHD_PLIST), exist_ok=True)
        with open(LAUNCHD_PLIST, "w") as fh:
            fh.write(plist)
        subprocess.run(["launchctl", "unload", LAUNCHD_PLIST],
                       stderr=subprocess.DEVNULL)
        r = subprocess.run(["launchctl", "load", LAUNCHD_PLIST])
        if r.returncode != 0:
            print("⚠ launchctl load 失败,plist 已写入但未加载。", file=sys.stderr)
            return 1
        print("✓ 已安装定时任务:登录时 + 每 6 小时自动 archive(覆盖关机/睡眠)")
        print(f"  plist:  {LAUNCHD_PLIST}")
        print(f"  log:    {LAUNCHD_LOG}")
        print(f"  查看状态:  claude-usage-stat schedule status")
        return 0

    if args.action == "uninstall":
        if os.path.exists(LAUNCHD_PLIST):
            subprocess.run(["launchctl", "unload", LAUNCHD_PLIST],
                           stderr=subprocess.DEVNULL)
            os.remove(LAUNCHD_PLIST)
            print("✓ 定时任务已卸载")
        else:
            print("(未安装,无需卸载)")
        return 0

    # status
    if not os.path.exists(LAUNCHD_PLIST):
        print("(未安装)运行 `claude-usage-stat schedule install` 来安装。")
        return 0
    print(f"plist:  {LAUNCHD_PLIST}")
    r = subprocess.run(["launchctl", "list", LAUNCHD_LABEL],
                       capture_output=True, text=True)
    print("已加载 (launchctl)" if r.returncode == 0 else "未加载 (launchctl)")
    print(f"log:    {LAUNCHD_LOG}")
    return 0


def _cmd_config(args) -> int:
    if args.action == "path":
        print(CONFIG_PATH)
        return 0
    load_config()
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
    if args.command == "schedule":
        return _cmd_schedule(args)

    cfg = load_config()
    if args.command == "html":
        return _cmd_html(args, cfg)
    if args.command == "archive":
        return _cmd_archive(args, cfg)
    return _cmd_report(args, cfg)


if __name__ == "__main__":
    sys.exit(main())
