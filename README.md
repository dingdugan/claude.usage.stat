# claude-usage-stat

**English** · [简体中文](README.zh-CN.md)

See your Claude Code token usage and an equivalent cost estimate. Claude Code doesn't surface detailed usage itself, so this tool reads your local session logs (`~/.claude/projects`) and breaks usage down by day, project, and session.

Two views: a terminal report, and an interactive HTML dashboard with date filtering. Pure Python standard library — zero third-party dependencies.

> Cost is an *equivalent estimate* at official API list prices, not your actual subscription billing.

## Install

Requires Python 3.8+.

```sh
git clone https://github.com/dingdugan/claude.usage.stat.git
cd claude.usage.stat
./install.sh
```

Or with pipx:

```sh
pipx install git+https://github.com/dingdugan/claude.usage.stat.git
```

> `install.sh` **copies** the package into `~/.local/share/claude-usage-stat/` (it is not an editable install). If you pull new code, re-run `./install.sh` to refresh the installed copy.

## Usage

```sh
claude-usage-stat              # terminal report, all history
claude-usage-stat --days 1     # today only
claude-usage-stat --days 7     # last 7 days
claude-usage-stat html         # generate and open the HTML dashboard
claude-usage-stat config edit  # edit config
```

Running with no arguments prints the terminal report. The config file is created on first run.

## Total tokens vs. Net tokens

The overview shows two token figures:

- **Total tokens** — sums all four token classes: input + output + cache-write + **cache-read**.
- **Net tokens** — input + output + cache-write, **excluding cache reads**.

Cache reads (context replayed from the prompt cache on every turn) typically make up **~95%+** of the raw token count, so Total tokens can be tens of times larger than what you'd intuitively expect. **Net tokens** matches the "Total tokens" figure shown in Claude Code's own usage screen, which excludes cache reads. Keep both: Net tokens for an intuitive sense of work done, Total tokens for cost estimation (billing meters each class separately, cache reads at a much lower rate).

## Long-term history archive

Claude Code periodically deletes session files older than ~30 days from `~/.claude/projects`, so scanning the source alone loses history. This tool automatically upserts per-(session × day) aggregates into a local SQLite database (`~/.local/share/claude-usage-stat/history.db`), so history survives even after the source is cleaned up. Only numeric aggregates are stored — no conversation content — so a year of archive is under 1 MB.

```sh
claude-usage-stat archive          # run one archive pass manually (report/html also run it)
claude-usage-stat schedule install # macOS: install a launchd job (at login + every 6 hours)
claude-usage-stat schedule status  # check the scheduled job
claude-usage-stat schedule uninstall
```

On Linux use cron — add a line with `crontab -e` (every 6 hours):
```
0 */6 * * *  $(which claude-usage-stat) archive --quiet
```

## License

MIT
