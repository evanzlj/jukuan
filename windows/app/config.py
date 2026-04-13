"""
从环境变量读取配置。请在 Windows 上自行设置，勿把账号路径提交到 Git。
"""

from __future__ import annotations

import os


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw, 10)
    except ValueError:
        return default


def _env_bool(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip().lower() in {"1", "true", "yes", "on"}


# QMT 安装目录下的 bin.x64，用于把 xtquant 加入 sys.path（与 qmt_data_server 一致）
QMT_BIN_DIR = os.getenv("QMT_BIN_DIR", "").strip()

# miniQMT 用户数据目录：XtQuantTrader 第一个参数，一般为 userdata_mini 路径（见券商说明）
QMT_USERDATA_MINI = os.getenv("QMT_USERDATA_MINI", "").strip()

# 资金账号
QMT_ACCOUNT_ID = os.getenv("QMT_ACCOUNT_ID", "").strip()

# XtQuantTrader 会话号，多实例时不要冲突
QMT_SESSION_ID = _env_int("QMT_SESSION_ID", 135791)

# 监听地址：仅 Tailscale 访问时可设为 Tailscale IP；默认 0.0.0.0 配合本机防火墙收窄
AGENT_BIND_HOST = os.getenv("AGENT_BIND_HOST", "0.0.0.0")
AGENT_BIND_PORT = _env_int("AGENT_BIND_PORT", 9780)

# 非空时，请求须带 X-Internal-Key: <值>（南京网关转发时附加）
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY", "").strip()

# 策略名写入委托备注体系（券商界面可见）
DEFAULT_STRATEGY_NAME = os.getenv("DEFAULT_STRATEGY_NAME", "jq_relay").strip() or "jq_relay"

# 是否在启动时预连接 QMT（False 则首次下单时再连）
CONNECT_ON_STARTUP = _env_bool("CONNECT_ON_STARTUP", default=False)
