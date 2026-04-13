# 网关（Gateway）

接收 **聚宽或任意 HTTP 客户端** 的下单意图（`POST /v1/intents`），校验后 **HTTP 转发** 到 Windows 上的 **Agent**（`POST /internal/execute`）。

同一套代码可在 **本机 Windows** 联调，也可复制到 **南京 Ubuntu** 上对公网暴露（再加 TLS / 防火墙即可）。

## 依赖

```powershell
cd gateway
py -3.11 -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
```

## 环境变量

见 `.env.example`。

| 变量 | 说明 |
|------|------|
| `GATEWAY_BIND_HOST` / `GATEWAY_BIND_PORT` | 网关监听，默认 `0.0.0.0:9090` |
| `GATEWAY_API_KEY` | 非空时，请求须带 `X-API-Key` |
| `AGENT_BASE_URL` | Agent 根地址，默认 `http://127.0.0.1:9780` |
| `INTERNAL_API_KEY` | 与 `windows` Agent 的 `INTERNAL_API_KEY` 相同；转发时带 `X-Internal-Key` |
| `GATEWAY_IDEM_TTL_SEC` | 网关侧按 `intent_id` 缓存响应的秒数，`0` 关闭 |

## 单机联调（两台进程）

1. **先起 Agent**（`windows/` README）：`QMT_*`、`INTERNAL_API_KEY` 配好，`python -m app.main` → 默认 `:9780`。
2. **再起网关**：

```powershell
cd gateway
$env:GATEWAY_API_KEY = "gw-dev"
$env:INTERNAL_API_KEY = "与 Agent 相同"
.\.venv\Scripts\python.exe -m app.main
```

3. **本机试请求**（勿在生产环境用弱密钥）：

```powershell
curl.exe -s -H "X-API-Key: gw-dev" -H "Content-Type: application/json" `
  -d "{\"intent_id\":\"local-test-1\",\"symbol\":\"600000.SH\",\"side\":\"buy\",\"volume\":100,\"price_type\":\"limit\",\"price\":10.0}" `
  http://127.0.0.1:9090/v1/intents
```

`GET /health` 可查看是否配置了 `GATEWAY_API_KEY`、`AGENT_BASE_URL`。

## 接口

- `GET /health` — 无需 `X-API-Key`。
- `POST /v1/intents` — Body 字段与 `windows` Agent 的 JSON 一致（`intent_id`、`symbol`、`side`、`volume` 等）。

聚宽策略里把原来的下单逻辑改成 `requests.post("https://你的域名/v1/intents", headers={"X-API-Key": "..."}, json={...})` 即可（南京上线后换 URL）。
