# claude-usage-stat

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

## 使用

```sh
claude-usage-stat              # 终端报告,全部历史
claude-usage-stat --days 1     # 只看今天
claude-usage-stat --days 7     # 近 7 天
claude-usage-stat html         # 生成并打开 HTML 仪表盘
claude-usage-stat config edit  # 编辑配置
```

不带参数直接运行即终端报告。配置文件首次运行时自动生成。

## License

MIT
