"""配置管理 —— 首次运行自动在 ~/.config/claude-usage-stat/config.json 写入默认配置。"""
import copy
import json
import os

from .pricing import DEFAULT_PRICING

CONFIG_DIR = os.path.expanduser("~/.config/claude-usage-stat")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")

DEFAULT_CONFIG = {
    # Claude Code 存放 session 记录的目录
    "projects_dir": "~/.claude/projects",
    # 不带子命令直接运行时的默认动作: "report" 或 "html"
    "default_command": "report",
    # 排行榜默认显示条数
    "default_top": 10,
    # 可选:设月度花费预算(美元)。设了之后报告会显示本月花费占预算的百分比。null = 不显示。
    "monthly_budget_usd": None,
    # 可选:覆盖某个模型的价格档,例如 {"opus": {"out": 80.0}}。留空用内置标准价。
    "pricing": {},
}


def load_config() -> dict:
    """读配置;文件不存在则创建默认配置后返回。"""
    if not os.path.exists(CONFIG_PATH):
        save_config(DEFAULT_CONFIG)
        return copy.deepcopy(DEFAULT_CONFIG)
    try:
        with open(CONFIG_PATH, encoding="utf-8") as fh:
            user = json.load(fh)
    except Exception:
        user = {}
    cfg = copy.deepcopy(DEFAULT_CONFIG)
    if isinstance(user, dict):
        for k, v in user.items():
            if k in DEFAULT_CONFIG:
                cfg[k] = v
    return cfg


def save_config(cfg: dict) -> None:
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def effective_pricing(cfg: dict) -> dict:
    """把配置里的 pricing 覆盖项合并到内置标准价上。"""
    p = copy.deepcopy(DEFAULT_PRICING)
    for model, fields in (cfg.get("pricing") or {}).items():
        if not isinstance(fields, dict):
            continue
        if model in p:
            p[model].update(fields)
        else:
            p[model] = fields
    return p
