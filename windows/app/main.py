"""
下单代理 HTTP 服务：供南京网关经 Tailscale 调用。

启动（在 windows 目录下）：
  set QMT_BIN_DIR=D:\\...\\bin.x64
  set QMT_USERDATA_MINI=D:\\...\\userdata_mini
  set QMT_ACCOUNT_ID=你的资金账号
  set INTERNAL_API_KEY=与网关约定的密钥
  python -m app.main
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from app import config
from app import trader_service


def _verify_internal_key(x_internal_key: Annotated[str | None, Header()] = None) -> None:
    if not config.INTERNAL_API_KEY:
        return
    if x_internal_key != config.INTERNAL_API_KEY:
        raise HTTPException(status_code=401, detail="invalid or missing X-Internal-Key")


class ExecuteRequest(BaseModel):
    intent_id: str = Field(min_length=1, description="幂等键，同一 intent_id 重复请求不会重复下单")
    strategy_id: str | None = Field(default=None, description="聚宽侧策略标识，仅用于备注")
    symbol: str = Field(description="QMT 代码，如 600000.SH")
    side: str = Field(description="buy 或 sell")
    volume: int = Field(gt=0, description="股数，须为 100 的整数倍")
    price_type: str = Field(default="limit", description="limit 限价；latest 最新价/市价类（依券商支持）")
    price: float = Field(default=0.0, description="限价时填写；latest 时可为 0")
    strategy_name: str | None = Field(default=None, description="写入 QMT 的策略名")
    order_remark: str | None = Field(default=None, description="委托备注")


class ExecuteResponse(BaseModel):
    ok: bool
    order_id: int | None = None
    error: str | None = None


class HealthResponse(BaseModel):
    status: str
    trader_ready: bool = False
    import_error: str | None = None
    connect_error: str | None = None


@asynccontextmanager
async def lifespan(_app: FastAPI):
    from app.xtquant_bootstrap import init_xtquant_path

    init_xtquant_path()
    if config.CONNECT_ON_STARTUP:
        try:
            trader_service.connect()
        except Exception:
            pass
    yield
    trader_service.disconnect()


app = FastAPI(
    title="JQ Relay Windows Agent",
    description="聚宽链路 Windows 执行端：接收内网转发并调用 XtQuantTrader 下单。",
    lifespan=lifespan,
)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        trader_ready=trader_service.trader_ready(),
        import_error=trader_service.get_import_error(),
        connect_error=trader_service.get_connect_error(),
    )


@app.post(
    "/internal/execute",
    response_model=ExecuteResponse,
    dependencies=[Depends(_verify_internal_key)],
)
def post_internal_execute(body: ExecuteRequest) -> ExecuteResponse:
    remark = body.order_remark
    if body.strategy_id and not remark:
        remark = f"strategy_id={body.strategy_id}"
    elif body.strategy_id and remark:
        remark = f"{remark}|strategy_id={body.strategy_id}"

    try:
        result = trader_service.place_stock_order(
            intent_id=body.intent_id.strip(),
            symbol=body.symbol.strip(),
            side=body.side.strip(),
            volume=int(body.volume),
            price_type=body.price_type.strip(),
            price=float(body.price),
            strategy_name=body.strategy_name,
            order_remark=remark,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(
            status_code=503,
            detail=str(e),
        ) from e

    return ExecuteResponse(
        ok=bool(result.get("ok")),
        order_id=result.get("order_id"),
        error=result.get("error"),
    )


def main() -> None:
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=config.AGENT_BIND_HOST,
        port=config.AGENT_BIND_PORT,
        reload=False,
    )


if __name__ == "__main__":
    main()