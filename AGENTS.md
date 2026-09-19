# AGENTS.md — 智能投研系统

自动化分析股票行情、辅助人工投资决策。**不自动下单**，信号仅供人工确认后手动交易。

## 阶段划分

```
Phase 0  基础设施        git repo + moomoo OpenD/MCP 连接      [完成]
Phase 1  数据层          定时抓行情，存本地文件/sqlite         [下一步，未开始]
Phase 2  策略层          MACD/state-A 信号逻辑 + 历史回测       [未开始]
Phase 3  执行/提醒层      生成 signals.md 交给 Cowork agent      [Claude Code 负责]
Phase 4  监控/复盘        Cowork 负责                           [不归 Claude Code 管]
```

## 现状（下次接着做）

Phase 0 已完成并验证：moomoo MCP 连接可用，`get_stock_quote`/`get_historical_klines`
读到真实数据。开始 Phase 1 前先确认 OpenD 在跑：`ss -tln | grep 11111`，没起的话
跑 `scripts/start_opend.sh`（前提是之前交互登录过一次并选了"记住密码"，否则得先
交互登录一次）。

Phase 0-2 + Phase 3 前半（生成信号文件）由 Claude Code 负责写代码/跑代码/回测。
Phase 3 后半（简报整理/推送提醒）和 Phase 4 由云端 Cowork agent 负责，通过共享文件交接
（Claude Code 写 `signals.md` / `daily_report.md` 到 repo 里，Cowork 读，不直接对接）。

2026-09-19：整理了 `holdle-knowledge/` 知识库（HOLDLE 方法论7章笔记，通过 `mcp__holdle-ai`
的 `holdle_ask`/`holdle_get_rules` 检索转述，非课程原文）。同一天内又做了两轮二次加工：
1) `decomposition/`（A-H共8个模块文件，按"原始观点/核心原则/判断流程/决策规则/常见错误"
五栏拆解）；2) `investment-system/`（整合成六件套完整投资体系：投资哲学/投资理念/状态A与
买入时机判断体系/企业分析体系/交易管理规则/入场决策流程图，面向"任何AI读到都能一步步
判断"）。**Phase 2 做 MACD/state-A 信号逻辑时，直接读 `investment-system/` 六件套**
（尤其 `03-state-a-entry-timing-system.md`、`06-entry-decision-flowchart.md`），不用再
翻 `notes/`/`rag/`——那两个是更早期的中间产物，内容已经吸收进 decomposition/ 和
investment-system/。

额度用量：14次里累计用掉12次（首轮学7章7次+二次查询补缺口2次+"先自己答再对比
holdle_ask"实战校对3次），**剩2次**，非必要不再调用。二次查询补到的关键缺口：绿柱日精确
机械定义（原笔记只写"MACD绿柱确认回撤"太糊）、复权口径规则（forward/backward，原笔记
完全没有，写代码前必须搞对否则算出的价格和行情软件对不上）、方式b首红案例完整时间线。
**"23条规则清单"已确认不存在**——现行规则包是 §3.1-3.11 编号结构，之前笔记里的
"待补充"是找错了方向，不用再为这份清单去查。仍未覆盖：第5章更多案例图解、第7章原生
内容（第7章本身也没有独立文档，是散落进阶文章）。

实战校对进度（`training-log/`，流程=自己按规则算→抽查+`holdle_ask`校对→错的记
`纠正记录_第N条_<股票名>.md`→重做）：
1. 携程网TCOM 企业质量 → 判"不过关"，纠错3条（ROE用错算法/漏现金占比联动否决/
   混淆定性检查表与定量评分算法八项），已记`纠正记录_第1条_携程网TCOM.md`。
2. 贵州茅台 买入时机(状态A/开窗) → 判"不满足"，对照holdle_ask规则原文无误，
   没生成纠正记录（验证通过的不记录，只记真错的，避免污染错误库信噪比）。
   月/周/日K数据源：Tencent公开行情API（`web.ifzq.gtimg.cn`，前复权QFQ），
   本地Python算MACD(12,26,9)，未用`holdle_data.py`（依赖baostock/tickflow/akshare
   都没装，装前得先问——见下方"代码风格约定"）。

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
- `holdle-knowledge/` — HOLDLE 方法论学习笔记（转述整理，非课程原文），`notes/` 按
  1-7章分文件，`rag/` 是按概念切块+frontmatter的检索友好版。详见该目录下 README.md。

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
