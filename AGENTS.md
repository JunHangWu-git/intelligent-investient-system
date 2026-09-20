# AGENTS.md — 智能投研系统

自动化分析股票行情、辅助人工投资决策。**不自动下单**，信号仅供人工确认后手动交易。

## 阶段划分

```
Phase 0  基础设施        git repo + moomoo OpenD/MCP 连接      [完成]
Phase 1  数据层          定时抓行情，存本地文件/sqlite         [完成]
Phase 2  策略层          MACD/state-A 信号逻辑 + 历史回测       [完成]
Phase 3  执行/提醒层      生成 signals.md 交给 Cowork agent      [完成，前半，Claude Code负责]
Phase 4  监控/复盘        Cowork 负责                           [不归 Claude Code 管]
```

## 现状（下次接着做）

Phase 0 已完成并验证：moomoo MCP 连接可用，`get_stock_quote`/`get_historical_klines`
读到真实数据。开始 Phase 1 前先确认 OpenD 在跑：`ss -tln | grep 11111`，没起的话
跑 `scripts/start_opend.sh`（前提是之前交互登录过一次并选了"记住密码"，否则得先
交互登录一次）。

Phase 0-2 + Phase 3 前半（生成信号文件）由 Claude Code 负责，可用单 agent 或多 agent
（team/并行 executor）协作写代码/跑代码/回测，不限定单人单线程完成。
Phase 3 后半（简报整理/推送提醒）和 Phase 4 由云端 Cowork agent 负责，通过共享文件交接
（Claude Code 写 `signals.md` / `daily_report.md` 到 repo 里，Cowork 读，不直接对接）。
**定时调度必须在本机跑，不能交给 Cowork**——Cowork 是云端 agent，连不到本机
`127.0.0.1:11111` 的 OpenD，Cowork 只能读 Claude Code 产出的文件。

2026-09-19：Phase 1 完成。Phase 2/3 状态见下方2026-09-20记录。

2026-09-19（旧）：Phase 1 完成，下次接着做 Phase 2（MACD/state-A 信号逻辑 + 历史回测，
直接读 `investment-system/` 六件套，见下方相关记录）。数据源是 Phase 1 落的
`data/quotes.db`（sqlite，`quotes`/`klines` 两张表，klines 主键含 `code`/`ktype`/
`autype`/`time_key`）。watchlist 暂定 `US.NVDA`/`US.AMD`/`US.STZ`/`US.QQQ`
（BTC 跳过——moomoo 只读接口无 crypto 现货代码格式，试过 `BTC.BTCUSD`/`US.BTCUSD`
都不认，后续要接的话得找别的数据源，如公开 crypto API 或改用 IBIT 等 ETF 代理）。
抓取脚本直连 OpenD（不走 Claude MCP，本机 cron 独立跑），装了 `moomoo-api`
（pip 包名，import 名是 `moomoo`）到项目 `.venv/`，MCP 用的是同一个包，不算引入新依赖。
踩坑记录：1) `get_stock_quote` 前必须先 `ctx.subscribe(codes, [SubType.QUOTE])`——
Claude MCP 工具会自动订阅，原生 SDK 不会；2) K线接口叫 `request_history_kline`
不是 `get_history_kline`，返回值是三元组 `(ret, df, page_req_key)`；
3) `AuType.QFQ` 的实际字符串值是小写 `'qfq'`，传大写字符串大概率不认。
code review（opus, high）过了一轮修了5条（详见 git log），另建了 `cowork_sync.md`
给 Cowork 每日同步状态用，见下方"与 Cowork 的交接"。

2026-09-19：整理了 `holdle-knowledge/` 知识库（HOLDLE 方法论7章笔记，通过 `mcp__holdle-ai`
的 `holdle_ask`/`holdle_get_rules` 检索转述，非课程原文）。同一天内又做了两轮二次加工：
1) `decomposition/`（A-H共8个模块文件，按"原始观点/核心原则/判断流程/决策规则/常见错误"
五栏拆解）；2) `investment-system/`（整合成六件套完整投资体系：投资哲学/投资理念/状态A与
买入时机判断体系/企业分析体系/交易管理规则/入场决策流程图，面向"任何AI读到都能一步步
判断"）。**Phase 2 做 MACD/state-A 信号逻辑时，直接读 `investment-system/` 六件套**
（尤其 `03-state-a-entry-timing-system.md`、`06-entry-decision-flowchart.md`），不用再
翻 `notes/`/`rag/`——那两个是更早期的中间产物，内容已经吸收进 decomposition/ 和
investment-system/。

额度用量：14次里累计用掉13次（首轮学7章7次+二次查询补缺口2次+"先自己答再对比
holdle_ask"实战校对3次+Phase2代码review后校准贴0轴/5%追高口径1次），**剩1次**，
非必要不再调用。2026-09-20那次问清楚了：①贴0轴(|柱|<0.5)是逐月按绿柱处理、
不是把月份从序列里剔除——红→贴0轴→红这种情况，第二个红月要算新的绿转红事件
（我原来的实现把贴0轴月直接剔除，判断逻辑错了，已按正确口径重写）；②0.5这个
阈值是固定绝对值，不因复权口径(qfq/hfq)缩放——回测本来就该用后复权，现状判断
用前复权，两套各自内部一致就行，不用为阈值再加相对化逻辑。二次查询补到的关键缺口：绿柱日精确
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

2026-09-20：Phase 2 开工（策略层：MACD/state-A/开窗/绿柱日/参考价/突破/止损/
周K有效低点，全按 `investment-system/` 六件套03/05/06号文档实现）。

踩坑记录：Phase1 的 `scripts/fetch_quotes.py` 不传 `start`/`end`，moomoo
`request_history_kline` 默认给近365天，导致月K只有12条、周K只有52条——完全不够
算MACD(12,26,9)更别说回测（EMA26/9需要更长历史才稳定，回测更要多年数据）。
新增 `scripts/backfill_klines.py`（一次性跑，不进cron）修复：`start='2000-01-01'`
+ `end=`显式传今天（**不能传None**——start给了、end给None的话moomoo默认
`end=start+365天`，不是"到今天"，会卡在一年窗口里出不来，之前踩过一次）+
`page_req_key`分页拉全部可用历史。现在月K/周K补到2000年至今（321条/1394条），
日K受moomoo接口限制只能到2006年（5040条），qfq（前复权，实时判断用）和hfq
（后复权，回测用，按03号文档"回测用后复权"规则）两套都存了，同一张`klines`表
（主键含autype天然不冲突）。

新增文件：`scripts/strategy.py`（纯函数策略逻辑：`macd()`公式对齐
`holdle_data.py`里`calc_macd`的口径——EMA用`adjust=False`递推、柱=
`(DIF-DEA)*2`，跟moomoo/国内看盘软件显示一致；`evaluate_windows()`实现
开窗判定含"贴0轴不算数"阈值和窗口关闭规则；`find_green_bar_day`/
`compute_reference_price`/`find_breakout`严格按03号文档机械定义实现；
`stop_loss_price`/`weekly_position_tracker`实现05号文档三阶止损+周K有效低点）
+ `scripts/backtest.py`（跑全历史回测，结果写`data/backtest_results.md`，
4只标的都跑出交易记录，链路走通）。

已知局限（未解决，标在代码注释里）：05号文档"周K有效低点"只有描述性规则
（"新高后绿柱回撤的低点"），不像绿柱日那样有机械定义，`weekly_position_tracker`
里是工程化实现（新高后遇hist<0算回撤期，回撤最低点>入场价才算有效低点），
**没拿真实case校对过**，正式当信号用前建议按training-log方法核对几个真实案例。
回测用的hfq价格数值会失真（早期基准放大，近期数字很大不代表真实报价），
只看收益率不看绝对价位，属正常现象不是bug。

code review（opus, high effort）发现14条问题（1 CRITICAL/4 HIGH/6 MEDIUM/3 LOW），
全部修完并重跑backfill+backtest验证过。修的问题里最关键的几条：
1. 参考价区间少算了开窗月本身（少算一整月，系统性压低参考价，会把该失效的
   突破误判成成功入场）——`backtest.py`里参考价起点和绿柱日起点被错误合并成
   一个，已拆开成两个独立起点。
2. 贴0轴(|柱|<0.5)判定逻辑错了——原实现把贴0轴月从序列里剔除再比较前后月，
   正确做法是逐月判色（贴0轴当绿柱），已用holdle_ask校准过口径重写（见上方
   额度用量记录）。
3. 窗口关闭规则(`close_month_index`)算出来了但backtest没真的拿去跳过已关闭
   窗口，等于摆设——已接上。
4. 次新股30个月门槛只看序列总长度，没按事件发生的月份判定，等于没生效——
   已改成按事件月下标判定。
5. `backfill_klines.py`分页失败原来只print不报错，会把残缺数据当正常数据
   留在库里且脚本还exit 0——已改成失败直接抛异常+加分页数上限防死循环+加
   请求间隔防触发moomoo频率限制。
6. 周K止损/出场有单周内前视问题（用本周high先抬止损线，又用本周low去撞）+
   入场周下标偏移（周中入场会漏检头1-2周）+回撤期最低点只在绿柱周更新会漏记
   真实最低点——三条一起在`weekly_position_tracker`里修了。
7. "超5%不追"原来判的是盘中high，改判开盘价（挂参考价的单只要没跳空高开
   超5%就能成交，盘中冲多高不影响）——这条是工程推断，没在holdle规则里找到
   机械定义，标注在代码注释里了。

回测结果重新跑过（`data/backtest_results.md`），4只标的都有交易记录，链路
（状态A→开窗→绿柱日→参考价→突破→止损/周K出场）走通。

2026-09-20：Phase 3 完成（前半，Claude Code负责的部分）。Nick明确要求"决策层面
要agent推理，不是纯script"——架构分两层：`scripts/strategy.py`(机械层，照旧)
不变，新增`scripts/signal_facts.py <code>`把机械结果+原始K线打包成JSON，喂给
headless `claude -p`（`scripts/run_signals.sh`当cron入口，`scripts/signals_prompt.md`
是prompt）。agent只对文档没给机械定义的两处做判断：①行情段自查(新起点/老行情
半路)②周K有效低点合理性，其余机械数字一律读JSON不自己重算。

`positions.json`（挪到repo根目录而不是`data/`下，因为`data/`整个被gitignore，
手动维护的持仓状态不能丢——**Nick每次实际下单/出场后要手动更新这个文件**，
不更新的话agent的止损/行情段判断会依据过期持仓状态）。

实测跑出来质量不错：NVDA/AMD/QQQ三只标的agent都主动发现"月K窗口连续多年从未
被规则关闭过+涨幅巨大"这种异常，怀疑`positions.json`可能漏记了真实持仓，
提示Nick核对——没让它这么做，是它自己从数据里看出来的。

踩了一个坑：`signal_facts.py`最初找"当前开窗"用的是"从后往前找第一个未关闭
窗口"，会在最新窗口已关闭、但更早年份有个从未被关闭判定命中过的陈年老窗口时，
错误地把那个老窗口当成当前信号（在STZ标的上实测复现），改成只认真正最新的
窗口（不管关没关）。

cron已接上：`40 13 * * 1-5`（fetch之后10分钟），跑完自动`git commit+push`
`signals.md`/`daily_report.md`（Cowork是云端agent，得靠git拉库才能看到更新，
不push看不到）。权限用`--permission-prompts none`（防止无人值守时卡在权限
弹窗上，不是沙箱隔离——跑在Nick自己账号下，工具权限跟交互式session一样，
真正的范围边界是prompt文件里写的任务范围）。

Phase 3 后半（简报推送/提醒）仍是Cowork的活，不归Claude Code管。

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
- 代码直白简单，不用高级抽象/设计模式，图易改易读。
- 不确定的地方先问用户，不擅自假设。
- 不做自动下单。所有信号走人工确认。

## 与 Cowork 的交接

- 交接方式：共享文件，不直接对接。
- Claude Code 产出：`signals.md`（信号判断结果）、`daily_report.md`（简报素材）、
  `facts_cache/<代码>.json`（每只WATCHLIST标的的完整机械事实，供Cowork聊天/
  自己的定时任务读，不用等signals.md）。
- 参数（MACD 周期等）写死在 config 文件里，不做成动态可调。
- `cowork_sync.md` — 状态同步文件（非信号文件）。Cowork 自己起了个 cron 每天读一次，
  了解 Claude Code 这边进度/依赖/阻塞。**每次阶段性进展后（尤其 Phase 切换、
  遇到需要 Cowork 知道的限制或风险时）都要更新这份文件**，不更新 Cowork 就看不到最新状态。

### 2026-09-20：整体workflow扩展（Cowork变成主对话agent + 自己的4个定时任务）

Nick定的workflow：①Nick日常问股票问题找Cowork问，Cowork用HOLDLE方法论
（读repo里的`holdle-knowledge/`）综合回答，不是简单转述数字；②Cowork自己
配4个定时任务（不是本机cron，Nick自己在Cowork界面里设，本Claude Code给了
每个job的prompt规划，见`cowork_cron_jobs.md`）：关注股票更新/新闻财报研究
(写`research_log.md`,追加制)/选股发现新标的(过04号文档企业门槛后写
`candidates.md`，**候选票不自动转正进WATCHLIST，必须Nick手动批准，因为
每加一只本机要多跑一次backfill有开销**)/盯已持仓给策略；③本机Claude Code
继续当backend（moomoo数据+机械计算+必要时调holdle-ai MCP补知识库缺口）。

架构决定（Nick问过"agent用HOLDLE全套方法 vs 只用strategy.py判断哪个好"，
给的结论）：**不是二选一，分层**——`strategy.py`/`signal_facts.py`算出来的
机械数字（状态A/开窗/绿柱日/参考价/止损%）永远保持代码实现，不交给agent
重新推理（这些是HOLDLE写死的公式，不是"看法"，agent每次重新判断长期一定
会算错/不一致，也没法backtest）；但**推理/叙述层**（企业质量定性判断、
新闻行业上下文、行情段自查这类没有机械定义的地方、以及跟Nick对话时的综合
表达）应该让agent(Cowork或本机headless agent)基于HOLDLE全套知识自由发挥，
不要把agent限制成"只能碰两个判断点"——这部分本来就没被代码锁死。

04号文档企业质量门槛（ROE≥20%等5项）**先不写机械代码**，让Cowork选股job
自己读文档判断，观察一阵子判断质量再决定要不要机械化（跟状态A那种严谨
公式化实现不是同一优先级）。

新增文件：`scripts/dump_facts_cache.py`（确定性脚本，`run_signals.sh`里跑，
把WATCHLIST每只标的的signal_facts.py结果落进`facts_cache/`，commit+push）、
`research_log.md`/`candidates.md`（Cowork的job②③写的地方，空模板+格式说明）、
`cowork_cron_jobs.md`（4个Cowork job的规划+prompt文本，给Nick抄进Cowork
界面用）。
