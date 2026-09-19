# AGENTS.md — 智能投研系统

自动化分析股票行情、辅助人工投资决策。**不自动下单**，信号仅供人工确认后手动交易。

## 阶段划分

```
Phase 0  基础设施        git repo + moomoo OpenD/MCP 连接      [完成]
Phase 1  数据层          定时抓行情，存本地文件/sqlite         [未开始]
Phase 2  策略层          MACD/state-A 信号逻辑 + 历史回测       [未开始]
Phase 3  执行/提醒层      生成 signals.md 交给 Cowork agent      [Claude Code 负责]
Phase 4  监控/复盘        Cowork 负责                           [不归 Claude Code 管]
```

Phase 0-2 + Phase 3 前半（生成信号文件）由 Claude Code 负责写代码/跑代码/回测。
Phase 3 后半（简报整理/推送提醒）和 Phase 4 由云端 Cowork agent 负责，通过共享文件交接
（Claude Code 写 `signals.md` / `daily_report.md` 到 repo 里，Cowork 读，不直接对接）。

## 现有文件

- `holdle_data.py` — 第三方"HOLDLE"分发的行情抓取脚本（非本项目自研代码）。
  抓月/周/日K + MACD(12/26/9) + 财报，数据源 TickFlow/Baostock/AkShare/腾讯/新浪。
  依赖 `baostock`/`tickflow`/`akshare`/`pandas`，带自更新逻辑（默认已关闭自动覆盖）。
  **按用户决定：保留原样当外部工具用，不改代码。** Phase 1 的定时抓取脚本另起，走标准库优先。
- `holdle-ai-mcp-config.json` — HOLDLE AI 助手的 MCP 配置，含明文 API key。跟本项目
  moomoo 数据流无直接关系，已加入 `.gitignore` 不进 git。
- `moomoo-mcp/` — moomoo OpenD + 社区 `moomoo-api-mcp`（只读，未开交易密码）接入说明文档，
  写的是 Windows Claude Desktop 配置方式，实际改走 WSL 本地部署（见下）。
- `.mcp.json` — 项目级 MCP 配置，注册了 `moomoo` server：
  `uvx --with "mcp<2" moomoo-api-mcp`（PyPI 包不锁 mcp 版本会崩，手动锁 `mcp<2`）。
  无密码，可进 git。
- `scripts/start_opend.sh` / `stop_opend.sh` — 后台启动/停止 moomoo OpenD（CLI版），
  `nohup + console=0` 脱离终端。前提：OpenD 目录下已交互登录过一次并选了"记住密码"。
- `moomoo_OpenD_10.11.7108_Ubuntu18.04/` — moomoo 官方 OpenD 安装包（CLI + GUI 两版），
  Ubuntu Linux 版，装在 WSL 本地。**不进 git**（522MB 二进制 + `AppData.dat` 登录会话数据）。
  CLI 版跑在 `127.0.0.1:11111`，Claude Code(WSL) 通过 mirrored 网络模式直连
  （WSL2 mirrored 模式下 `127.0.0.1` 与 Windows 主机共享，不用换 host IP）。

### Phase 0 已知限制

- 账号下的交易账户（保证金/TFSA）`get_accounts` 查不到，疑似 moomoo 官方 OpenAPI
  不覆盖加拿大(CA)主体账户（支持市场列表没列 CA）。已确认：行情/K线抓取
  （`get_stock_quote`/`get_historical_klines`）不受影响，正常可用。持仓/资产类
  工具暂时用不了，Phase 1-2 不需要，先搁置。
- OpenD 需要先交互登录一次（账号密码+验证码）并选"记住密码"，之后才能用
  `scripts/start_opend.sh` 非交互后台启动。这步没法完全自动化，登录状态过期
  需要用户重新交互登录。

## 代码风格约定

- 依赖越少越好，优先标准库；引入第三方包前先问。
- 代码直白简单，不用高级抽象/设计模式，本科生水平即可，图易改易读。
- 不确定的地方先问用户，不擅自假设。
- 不做自动下单。所有信号走人工确认。

## 与 Cowork 的交接

- 交接方式：共享文件，不直接对接。
- Claude Code 产出：`signals.md`（信号判断结果）、`daily_report.md`（简报素材）。
- 参数（MACD 周期等）写死在 config 文件里，不做成动态可调。
