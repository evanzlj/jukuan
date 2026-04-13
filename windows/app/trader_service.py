"""
XtQuantTrader 封装：连接 miniQMT、同步下单。

说明：不同券商 / xtquant 版本行为可能略有差异，下单失败时请根据返回码查阅迅投文档。
"""

from __future__ import annotations

import os
import threading
import time
from typing import Any

from app import config
from app.xtquant_bootstrap import init_xtquant_path

_lock = threading.Lock()
_trader: Any = None
_account: Any = None
_connect_error: str | None = None
_import_error: str | None = None

# 本地幂等：intent_id -> { "ts": float, "body": dict }
_idem_cache: dict[str, dict[str, Any]] = {}
_IDEM_TTL_SEC = 86400.0
_IDEM_MAX = 5000


def _prune_idem() -> None:
    now = time.time()
    if len(_idem_cache) <= _IDEM_MAX:
        return
    dead = [k for k, v in _idem_cache.items() if now - float(v.get("ts", 0)) > _IDEM_TTL_SEC]
    for k in dead:
        _idem_cache.pop(k, None)
    while len(_idem_cache) > _IDEM_MAX:
        oldest = min(_idem_cache.items(), key=lambda kv: kv[1].get("ts", 0))
        _idem_cache.pop(oldest[0], None)


def get_import_error() -> str | None:
    return _import_error


def get_connect_error() -> str | None:
    return _connect_error


def trader_ready() -> bool:
    return _trader is not None and _account is not None and _import_error is None


def _ensure_xtquant_imported() -> tuple[Any, Any, Any]:
    global _import_error
    if _import_error:
        raise RuntimeError(_import_error)
    init_xtquant_path()
    try:
        from xtquant import xtconstant  # type: ignore
        from xtquant.xttrader import XtQuantTrader  # type: ignore
        from xtquant.xttype import StockAccount  # type: ignore
    except Exception as e:  # noqa: BLE001
        _import_error = f"无法 import xtquant: {e}（请检查 QMT_BIN_DIR 与 Python 位数/版本）"
        raise RuntimeError(_import_error) from e
    return xtconstant, XtQuantTrader, StockAccount


def connect() -> None:
    """建立与 miniQMT 的连接；线程安全，可重复调用（已连接则跳过）。"""
    global _trader, _account, _connect_error
    with _lock:
        _connect_error = None
        if _trader is not None and _account is not None:
            return
        if not config.QMT_USERDATA_MINI:
            _connect_error = "未设置环境变量 QMT_USERDATA_MINI（miniQMT userdata_mini 路径）"
            raise RuntimeError(_connect_error)
        if not config.QMT_ACCOUNT_ID:
            _connect_error = "未设置环境变量 QMT_ACCOUNT_ID"
            raise RuntimeError(_connect_error)

        xtconstant, XtQuantTrader, StockAccount = _ensure_xtquant_imported()

        userdata = os.path.abspath(config.QMT_USERDATA_MINI)
        if not os.path.isdir(userdata):
            _connect_error = f"QMT_USERDATA_MINI 不是有效目录: {userdata}"
            raise RuntimeError(_connect_error)

        t = XtQuantTrader(userdata, config.QMT_SESSION_ID)
        t.start()
        rc = t.connect()
        if rc != 0:
            _connect_error = f"XtQuantTrader.connect() 返回 {rc}（请确认 miniQMT 已登录）"
            raise RuntimeError(_connect_error)

        acc = StockAccount(config.QMT_ACCOUNT_ID)
        t.subscribe(acc)
        _trader = t
        _account = acc


def disconnect() -> None:
    global _trader, _account, _connect_error
    with _lock:
        if _trader is not None:
            try:
                _trader.stop()
            except Exception:
                pass
        _trader = None
        _account = None
        _connect_error = None


def place_stock_order(
    *,
    intent_id: str,
    symbol: str,
    side: str,
    volume: int,
    price_type: str,
    price: float,
    strategy_name: str | None,
    order_remark: str | None,
) -> dict[str, Any]:
    """
    同步下单。side: buy / sell；price_type: limit / latest（市价类，具体以券商支持为准）。
    """
    _prune_idem()
    now = time.time()
    if intent_id:
        hit = _idem_cache.get(intent_id)
        if hit and now - float(hit["ts"]) <= _IDEM_TTL_SEC:
            return dict(hit["body"])

    xtconstant, _, _ = _ensure_xtquant_imported()
    connect()

    with _lock:
        if _trader is None or _account is None:
            raise RuntimeError("交易端未连接")

        side_l = side.strip().lower()
        if side_l == "buy":
            order_type = xtconstant.STOCK_BUY
        elif side_l == "sell":
            order_type = xtconstant.STOCK_SELL
        else:
            raise ValueError(f"无效 side: {side}")

        pt = price_type.strip().lower()
        if pt == "limit":
            xt_price_type = xtconstant.FIX_PRICE
            order_price = float(price)
        elif pt == "latest":
            xt_price_type = xtconstant.LATEST_PRICE
            order_price = 0.0
        else:
            raise ValueError(f"无效 price_type: {price_type}")

        if volume <= 0 or volume % 100 != 0:
            raise ValueError("A 股数量须为正整数且为 100 股的整数倍")

        strat = (strategy_name or config.DEFAULT_STRATEGY_NAME).strip()
        remark = (order_remark or intent_id or "").strip()

        oid = _trader.order_stock(
            _account,
            symbol.strip(),
            order_type,
            int(volume),
            xt_price_type,
            float(order_price),
            strat,
            remark,
        )

    ok = oid is not None and oid != -1
    body: dict[str, Any] = {
        "ok": ok,
        "order_id": oid if ok else None,
        "error": None if ok else (f"order_stock 失败，返回值: {oid}" if oid is not None else "order_stock 返回 None"),
    }
    if intent_id:
        _idem_cache[intent_id] = {"ts": now, "body": dict(body)}
    return body
