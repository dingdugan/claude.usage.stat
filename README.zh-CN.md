# claude-usage-stat

[English](README.md) · **简体中文**

查看 Claude Code 的 token 用量和等价花费估算。Claude Code 本身不展示具体用量,这个工具读取本地的 session 记录(`~/.claude/projects`),按天 / 项目 / session 给出统计。

提供两种界面:终端报告,和一个可交互(带日期筛选)的 HTML 仪表盘。纯 Python 标准库,零第三方依赖。

> 花费是按官方 API 标准价折算的*等价估算*,不是订阅套餐的实际计费。

## 安装

需要 Python 3.8+。

```sh
git clone https://github.com/dingdugan/claude.usage.stat.git
cd claude.usage.stat
./install.sh
```

或者用 pipx:

```sh
pipx install git+https://github.com/dingdugan/claude.usage.stat.git
```

> `install.sh` 是把代码**拷贝**进 `~/.local/share/claude-usage-stat/`(不是 editable 安装)。之后拉了新代码,要重跑一次 `./install.sh` 覆盖已安装副本才会生效。

## 使用

```sh
claude-usage-stat              # 终端报告,全部历史
claude-usage-stat --days 1     # 只看今天
claude-usage-stat --days 7     # 近 7 天
claude-usage-stat html         # 生成并打开 HTML 仪表盘
claude-usage-stat config edit  # 编辑配置
```

不带参数直接运行即终端报告。配置文件首次运行时自动生成。

## 总 Token 与 净 Token

概览里有两个 token 数字:

- **总 Token** —— 四类全加:输入 + 输出 + 缓存写 + **缓存读**。
- **净 Token** —— 输入 + 输出 + 缓存写,**不含缓存读**。

缓存读(每一轮从 prompt cache 复用的历史上下文)通常占原始 token 数的 **95% 以上**,所以"总 Token"会比你直觉大几十倍。**净 Token 和 Claude Code 自带用量界面里的 "Total tokens" 同口径**(那个界面也不含缓存读)。两个都留着:净 Token 直觉感受工作量,总 Token 用来估花费(计费按四类分别计,缓存读单价低得多)。

## 长期历史归档

Claude Code 会定期清理 `~/.claude/projects` 里大约 30 天前的 session 文件,直接扫源数据会丢历史。本工具自动把(session × 日期)聚合 upsert 进本地 SQLite(`~/.local/share/claude-usage-stat/history.db`),源被删后历史依然存在。只存数字聚合,不存对话内容 —— 一年的归档不到 1 MB。

```sh
claude-usage-stat archive          # 手动跑一次归档(report/html 也会自动跑)
claude-usage-stat schedule install # macOS:装 launchd 任务(登录时 + 每 6 小时跑一次)
claude-usage-stat schedule status  # 查看定时任务状态
claude-usage-stat schedule uninstall
```

Linux 用 cron,`crontab -e` 加一行(每 6 小时跑一次):
```
0 */6 * * *  $(which claude-usage-stat) archive --quiet
```

## License

MIT
