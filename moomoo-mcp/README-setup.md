# moomoo OpenAPI + MCP 接入指南（只读行情/持仓）

用途：只查行情、账户资产、持仓。不开交易密码，不解锁交易，风险最低。

## 架构

```
Claude Desktop (Windows)
      |
      | MCP (stdio, uvx moomoo-api-mcp)
      v
moomoo-api-mcp  --- 127.0.0.1:11111 --->  OpenD 网关 (需登录你的 moomoo 账号)
      |
      v (仅只读: get_accounts / get_positions / get_stock_quote 等)
   moomoo 服务器
```

- OpenD: moomoo 官方网关程序，负责登录账号、转发行情/账户数据。必须由你本人在真实 Windows 上安装并登录（涉及账号密码+验证码，不能代做）。
- moomoo-api-mcp: 开源(非官方) MCP server，把 OpenD 的接口包装成 Claude 能调用的工具。已发布在 PyPI，不需要手动 clone 代码。

## 步骤

### 1. 安装并登录 OpenD（你自己在 Windows 上做）

1. 打开 https://www.moomoo.com/download/opend 下载 Windows 版 OpenD
2. 安装后启动，用你的 moomoo 账号登录（会有短信/App 验证码）
3. 确认监听端口是默认的 11111（设置里能看到）
4. 让 OpenD 保持登录/运行状态 —— 之后要查数据时它必须在跑

### 2. 安装 uv（Windows PowerShell 里跑一次）

```powershell
irm https://astral.sh/uv/install.ps1 | iex
```

装完重新开一个 PowerShell 窗口，跑 `uv --version` 确认装好了。

### 3. 测试 MCP server 能不能连上 OpenD

OpenD 保持运行的情况下，在 PowerShell 跑：

```powershell
uvx moomoo-api-mcp
```

正常应该没报错、进程挂起等待 MCP 连接（Ctrl+C 退出）。如果报连接错误，先检查 OpenD 是否在跑、端口是不是 11111。

### 4. 配置 Claude Desktop

打开配置文件（一般在 `%APPDATA%\Claude\claude_desktop_config.json`），把下面这段加进 `mcpServers` 里（同目录下 claude_desktop_config_snippet.json 是同样内容，可以直接抄）：

```json
{
  "mcpServers": {
    "moomoo": {
      "command": "uvx",
      "args": ["moomoo-api-mcp"]
    }
  }
}
```

**注意：故意不设置 MOOMOO_TRADE_PASSWORD / MOOMOO_SECURITY_FIRM。**
不设置的话，下单类工具（place_order/modify_order/cancel_order/unlock_trade）会用不了，
但查询类工具（get_accounts/get_positions/get_assets/get_stock_quote/get_historical_klines 等）正常可用，
不需要解锁交易密码 —— 符合"只查行情/持仓"的需求，也避免交易密码被写进配置文件。

保存后重启 Claude Desktop 生效。

### 5. 验证

重启后在 Claude Desktop 里问一句 "帮我查一下 moomoo 账户持仓"，
它应该会调用 check_health -> get_accounts -> get_positions。

## 安全提醒

- 不要把 moomoo 登录密码或交易密码贴给任何 AI/脚本，OpenD 登录只在官方客户端里手动输入
- 这个 MCP server 是社区项目（Litash/moomoo-api-mcp），不是 moomoo 官方产品，用之前自己评估风险
- 如果之后想开交易权限，务必先在 SIMULATE（模拟盘）测试，参考它 README 里的 Disclaimer
