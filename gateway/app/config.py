"""网关环境变量（与部署位置无关，Windows / Ubuntu 均可）。"""

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


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


# 监听（单机验证：127.0.0.1:8080 只本机访问）
GATEWAY_BIND_HOST = os.getenv("GATEWAY_BIND_HOST", "0.0.0.0").strip()
GATEWAY_BIND_PORT = _env_int("GATEWAY_BIND_PORT", 8080)

# 聚宽 / 公网客户端调用网关时携带；非空则要求 X-API-Key
GATEWAY_API_KEY = os.getenv("GATEWAY_API_KEY", "").strip()

# Windows Agent 根 URL，无尾部斜杠
AGENT_BASE_URL = os.getenv("AGENT_BASE_URL", "http://127.0.0.1:9780").strip().rstrip("/")

# 转发给 Agent 时的 X-Internal-Key，须与 Agent 的 INTERNAL_API_KEY 一致
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY", "").strip()

# 网关侧幂等缓存秒数（0 表示关闭，每次都会转发 Agent；Agent 仍有自己的幂等）
GATEWAY_IDEM_TTL_SEC = _env_int("GATEWAY_IDEM_TTL_SEC", 86400)

# 调用 Agent 的超时秒数
AGENT_HTTP_TIMEOUT_SEC = _env_float("AGENT_HTTP_TIMEOUT_SEC", 30.0)
