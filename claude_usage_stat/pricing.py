"""模型价格表 —— 等价 API 标准价,单位:美元 / 百万 token。

仅用于花费估算参考,并非 Claude 订阅套餐的实际计费。
命中 1M 长上下文时实际更贵,这里按标准价估算。
可在配置文件里用 pricing 字段覆盖。
"""

DEFAULT_PRICING = {
    # cw5 = 5 分钟缓存写, cw1h = 1 小时缓存写, cr = 缓存读
    "opus":   {"in": 15.0, "out": 75.0, "cw5": 18.75, "cw1h": 30.0, "cr": 1.5},
    "sonnet": {"in": 3.0,  "out": 15.0, "cw5": 3.75,  "cw1h": 6.0,  "cr": 0.3},
    "haiku":  {"in": 1.0,  "out": 5.0,  "cw5": 1.25,  "cw1h": 2.0,  "cr": 0.1},
}


def price_for(model: str, pricing: dict) -> dict:
    """按模型名匹配价格档,匹配不到时按 opus 估算。"""
    m = (model or "").lower()
    for key in ("opus", "sonnet", "haiku"):
        if key in m:
            return pricing.get(key, DEFAULT_PRICING[key])
    return pricing.get("opus", DEFAULT_PRICING["opus"])
