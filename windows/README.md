# Windows 下单代理（Agent）

供 **南京网关经 Tailscale** 调用的本机 HTTP 服务：将 JSON 意图转为 **miniQMT / XtQuantTrader** 委托。

## 环境要求

- Windows，已安装券商 QMT，**miniQMT 已登录**
- **64 位 Python 3.10 或 3.11**（与 `xtquant` 扩展一致，勿用 3.12+ 除非已验证）
- 与 `qmt_data_server` 相同：`QMT_BIN_DIR` 指向 **`bin.x64` 根目录**；本仓库会在其下自动解析 **`Lib\site-packages`** 再 `import xtquant`（华鑫等发行版均为此结构）。Windows 下还会为 `bin.x64` 注册 `add_dll_directory`，避免 `.pyd` 找不到 DLL。

**华鑫 QMT 实盘（你本机路径形态）**

- `...\华鑫证券QMT实盘\bin.x64\Lib\site-packages\xtquant\` — 行情/交易 Python 包  
- `...\华鑫证券QMT实盘\userdata_mini\` — `XtQuantTrader(path, …)` 文档所述的 **userdata** 目录；`path` 填 **`userdata_mini` 的绝对路径**（与 `bin.x64` 同级、在安装根下）

`xttrader.py` 中说明：`path` 为「mini 版客户端安装路径下的 **userdata 文件夹具体路径**」。

## 安装

```powershell
cd windows
py -3.11 -m venv .venv
.\.venv\Scripts\pip install -U pip
.\.venv\Scripts\pip install -r requirements.txt
```

## 环境变量

见仓库内 `.env.example`。至少配置：

| 变量 | 说明 |
|------|------|
| `QMT_BIN_DIR` | QMT 的 `bin.x64` 绝对路径 |
| `QMT_USERDATA_MINI` | `userdata_mini` 绝对路径（以迅投/券商说明为准） |
| `QMT_ACCOUNT_ID` | 资金账号 |
| `INTERNAL_API_KEY` | 非空时，所有 `/internal/*` 请求须带请求头 `X-Internal-Key` |

可选：`AGENT_BIND_HOST`、`AGENT_BIND_PORT`、`QMT_SESSION_ID`、`DEFAULT_STRATEGY_NAME`、`CONNECT_ON_STARTUP`。

## 启动

在 `windows` 目录下：

```powershell
$env:QMT_BIN_DIR = "D:\你的路径\bin.x64"
$env:QMT_USERDATA_MINI = "D:\你的路径\userdata_mini"
$env:QMT_ACCOUNT_ID = "你的资金账号"
$env:INTERNAL_API_KEY = "与南京网关一致的长随机串"
.\.venv\Scripts\python.exe -m app.main
```

默认监听 `http://0.0.0.0:9780`。建议在 **Windows 防火墙** 中限制仅 **Tailscale 虚拟网卡对应网段** 可访问该端口。

## HTTP 接口

### `GET /health`

无需 `X-Internal-Key`。返回 `trader_ready`、`import_error`、`connect_error` 等，便于排查。

### `GET /internal/ping`

需鉴权（若配置了 `INTERNAL_API_KEY`）：请求头 `X-Internal-Key`。不下单，仅返回 `{"ok":true,"service":"jq-relay-agent"}`，供网关 `GET /v1/chain-check` 做全链路探测。

### `POST /internal/execute`

需鉴权（若配置了 `INTERNAL_API_KEY`）：请求头 `X-Internal-Key: <密钥>`。

**JSON 示例：**

```json
{
  "intent_id": "20260413-001-600000.SH-buy",
  "strategy_id": "my_jq_strategy",
  "symbol": "600000.SH",
  "side": "buy",
  "volume": 100,
  "price_type": "limit",
  "price": 10.55,
  "strategy_name": "jq_relay",
  "order_remark": "bar_time=2026-04-13"
}
```

- `side`：`buy` / `sell`
- `price_type`：`limit`（限价）或 `latest`（最新价类，是否支持以券商为准）
- `volume`：正整数，且为 **100 的整数倍**
- `intent_id`：**幂等键**；相同 `intent_id` 在 Agent 进程内 **24h 内** 重复提交将直接返回首次结果，不重复下单

**响应：** `ok`、`order_id`、`error`。

## 与南京网关的约定

- 网关将聚宽 payload 校验后，向本机 `POST /internal/execute`（经 Tailscale IP + 端口），并附带相同 `X-Internal-Key`。
- 代码、数量、价格等业务规则以网关与聚宽侧为准；Agent 仅做基础校验与调用 `order_stock`。

## 常见问题

1. **`import_error` 非空**：检查 `QMT_BIN_DIR`、Python 版本/位数。
2. **`connect` 失败**：确认 miniQMT 已登录、`QMT_USERDATA_MINI` 路径正确。
3. **下单返回失败**：查阅迅投 `xtconstant` 与券商对市价/限价的支持说明。
