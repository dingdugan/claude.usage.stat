# Implementation Checklist

## v0.2 — 历史归档(2026-05-21)

> 背景:Claude Code 每隔一段会清理 `~/.claude/projects` 里大约 30 天前的 session 文件。
> 直接扫源数据会丢历史。改成:每次跑工具自动把(session × 日期)聚合 upsert 进本地 SQLite,源被删也不影响。

- [x] 新增 `claude_usage_stat/archive.py`:SQLite 存储 + `archive_now()` + `read_archive()` + `db_stats()`
- [x] `cli.py` 加 `archive` 子命令:扫一遍 + upsert,打印新增/累计统计
- [x] `cli.py` 的 `_load_data` 改成:先 `archive_now()`,再 `read_archive()`,不再直接吐 scan 结果
- [x] `cli.py` 加 `schedule` 子命令:在 `~/Library/LaunchAgents/` 装一个 launchd plist,每天 03:00 自动 archive(macOS);Linux 提示 cron 写法
- [x] 版本号 `0.1.0` → `0.2.0`(`__init__.py` + `pyproject.toml`)
- [x] README 加 `archive` / `schedule` 节
- [x] 本机安装 + 验证:`archive`、`report`(读 db)、`schedule install`(launchctl 真的加载了)、db 文件确实有数据

## v0.2.x — 概览口径对齐(2026-05-30)

> 背景:Claude Code 自带的 "What's up next" 界面 Total tokens 不含缓存读,我们的"总 Token"四类全加,差约 45×。

- [x] `report.py` 概览加 "净 Token" 单元格(= 输入+输出+缓存写,不含缓存读),并加一行 DIM 说明
  证据: claude_usage_stat/report.py:135 + report.py:144;`report --from 2000-01-01 --no-color` 输出概览行含 `净 Token 183.97M`
- [x] `html.py` 概览卡片加 "净 Token"(带 title 悬停说明,对齐 Claude Code 界面)
  证据: claude_usage_stat/html.py:169 + html.py:175;`html --no-open -o /tmp/cus_test.html` 生成文件 grep 到 `净 Token` 卡片
