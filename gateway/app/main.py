"""
网关：接收聚宽（或本机 curl）的 HTTPS/HTTP 请求，校验后转发到 Windows Agent。

单机验证（两个终端）：
  终端1 — Agent：cd windows && set INTERNAL_API_KEY=dev && python -m app.main
  终端2 — 网关：cd gateway && set GATEWAY_API_KEY=gw && set INTERNAL_API_KEY=dev && python -m app.main
  curl -H \"X-API-Key: gw\" -H \"Content-Type: application/json\" ^
    -d \"{\\\"intent_id\\\":\\\"t1\\\",\\\"symbol\\\":\\\"600000.SH\\\",\\\"side\\\":\\\"buy\\\",\\\"volume\\\":100,\\\"price_type\\\":\\\"limit\\\",\\\"price\\\":10.0}\" ^
    http://127.0.0.1:8080/v1/intents
"""

from __future__ import annotations

import asyncio
import time
from contextlib import asynccontextmanager
from typing import Annotated, Any

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, Field

from app import config


def _verify_gateway_key(x_api_key: Annotated[str | None, Header()] = None) -> None:
    if not config.GATEWAY_API_KEY:
        return
    if x_api_key != config.GATEWAY_API_KEY:
        raise HTTPException(status_code=401, detail="invalid or missing X-API-Key")


class IntentRequest(BaseModel):
    """与 Windows Agent 的 ExecuteRequest 字段一致，便于原样转发。"""

    intent_id: str = Field(min_length=1)
    strategy_id: str | None = None
    symbol: str = Field(min_length=1)
    side: str = Field(min_length=1)
    volume: int = Field(gt=0)
    price_type: str = Field(default="limit")
    price: float = Field(default=0.0)
    strategy_name: str | None = None
    order_remark: str | None = None


class IntentResponse(BaseModel):
    ok: bool
    order_id: int | None = None
    error: str | None = None


class HealthResponse(BaseModel):
    status: str
    agent_base_url: str
    gateway_api_key_set: bool
    internal_api_key_set: bool


_idem_lock = asyncio.Lock()
_idem_cache: dict[str, tuple[float, dict[str, Any]]] = {}
_IDEM_MAX = 5000


def _prune_idem(now: float) -> None:
    if len(_idem_cache) <= _IDEM_MAX:
        return
    ttl = float(config.GATEWAY_IDEM_TTL_SEC)
    dead = [k for k, (ts, _) in _idem_cache.items() if now - ts > ttl]
    for k in dead:
        _idem_cache.pop(k, None)
    while len(_idem_cache) > _IDEM_MAX:
        oldest = min(_idem_cache.items(), key=lambda kv: kv[1][0])
        _idem_cache.pop(oldest[0], None)


@asynccontextmanager
async def lifespan(app: FastAPI):
    timeout = httpx.Timeout(config.AGENT_HTTP_TIMEOUT_SEC)
    async with httpx.AsyncClient(timeout=timeout) as client:
        app.state.http = client
        yield


app = FastAPI(
    title="JQ Relay Gateway",
    description="公网/本机入口：校验后转发至 Windows Agent /internal/execute。",
    lifespan=lifespan,
)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        agent_base_url=config.AGENT_BASE_URL,
        gateway_api_key_set=bool(config.GATEWAY_API_KEY),
        internal_api_key_set=bool(config.INTERNAL_API_KEY),
    )


@app.post(
    "/v1/intents",
    response_model=IntentResponse,
    dependencies=[Depends(_verify_gateway_key)],
)
async def post_v1_intents(request: Request, body: IntentRequest) -> IntentResponse:
    now = time.time()
    ttl = float(config.GATEWAY_IDEM_TTL_SEC)

    if ttl > 0:
        async with _idem_lock:
            _prune_idem(now)
            hit = _idem_cache.get(body.intent_id)
            if hit and now - hit[0] <= ttl:
                d = hit[1]
                return IntentResponse(
                    ok=bool(d.get("ok")),
                    order_id=d.get("order_id"),
                    error=d.get("error"),
                )

    url = f"{config.AGENT_BASE_URL}/internal/execute"
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if config.INTERNAL_API_KEY:
        headers["X-Internal-Key"] = config.INTERNAL_API_KEY

    payload = body.model_dump(exclude_none=True)

    client: httpx.AsyncClient = request.app.state.http
    try:
        r = await client.post(url, json=payload, headers=headers)
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=502,
            detail=f"无法连接 Agent ({url}): {e!s}",
        ) from e

    if r.status_code >= 400:
        raise HTTPException(
            status_code=502,
            detail=f"Agent 返回 HTTP {r.status_code}: {r.text[:2000]}",
        )

    try:
        data = r.json()
    except Exception as e:  # noqa: BLE001
        raise HTTPException(
            status_code=502,
            detail=f"Agent 响应非 JSON: {r.text[:500]}",
        ) from e

    out = IntentResponse(
        ok=bool(data.get("ok")),
        order_id=data.get("order_id"),
        error=data.get("error"),
    )

    if ttl > 0:
        async with _idem_lock:
            _idem_cache[body.intent_id] = (
                now,
                {"ok": out.ok, "order_id": out.order_id, "error": out.error},
            )

    return out


def main() -> None:
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=config.GATEWAY_BIND_HOST,
        port=config.GATEWAY_BIND_PORT,
        reload=False,
    )


if __name__ == "__main__":
    main()
