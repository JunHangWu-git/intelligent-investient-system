# Cowork Sync

> Claude Code 每次阶段性进展后更新这份文件。Cowork 用自己的 cron 每天读一次，
> 了解 Claude Code 这边在做什么、进度到哪、有什么依赖或阻塞。这不是信号文件
> （信号见 `signals.md`/`daily_report.md`），是状态同步文件。

最后更新: 2026-09-20

## 当前阶段

Phase 2（策略层）+ Phase 3（信号生成）都跑通了。**信号agent已经接进本机cron，
每个交易日13:40 PT自动跑，跑完自动commit+push `signals.md`/`daily_report.md`
到这个repo——Cowork从今天起可以直接读这两个文件了，不用等人工手动同步。**

## 最近完成

- Phase 1：定时抓 watchlist 行情存本地 sqlite。
  - watchlist: `US.NVDA` / `US.AMD` / `US.STZ` / `US.QQQ`（BTC 暂时跳过，moomoo
    只读接口没有 crypto 现货代码格式）。
  - 脚本：`scripts/fetch_quotes.py`（抓报价+日/周/月K）+ `scripts/run_fetch.sh`
    （cron 入口，自带日志到 `logs/fetch.log`）。
  - 数据落地：`data/quotes.db`（sqlite，本机 cron 周一到五 13:30 PT 跑一次，
    美股收盘后）。
  - 经过一轮 code review（opus, high effort）并修完 5 条问题（配额风险注释、
    日志重定向、K线表主键补 autype、db 路径锚定到项目根、连接资源释放顺序）。
- Phase 2：MACD/状态A/开窗/绿柱日/参考价/突破/止损/周K有效低点，全按
  `investment-system/` 六件套（03/05/06号文档）实现。
  - `scripts/backfill_klines.py`：一次性历史回补（原 Phase1 抓取脚本默认只有
    近1年数据，不够算月K MACD更别说回测——踩坑记录见下）。日/周/月K都补到了
    2000年至今（日K受限moomoo接口只能到2006年），qfq+hfq两套复权都存了。
  - `scripts/strategy.py`：纯函数策略逻辑，可被回测和未来Phase3信号脚本复用。
  - `scripts/backtest.py`：跑全历史回测，结果写 `data/backtest_results.md`。
  - 4只标的修复后重新跑出交易记录（NVDA 9笔/AMD 4笔/STZ 4笔/QQQ 8笔），逻辑
    链路走通（状态A→开窗→绿柱日→参考价→突破→入场→止损/周K出场），结果见
    `data/backtest_results.md`。
  - code review（opus, high effort）挑出14条问题，最关键的几条：参考价区间
    漏算开窗月本身（系统性压低参考价）、贴0轴判定逻辑写错（已用holdle_ask
    校准）、窗口关闭规则算出来没生效、次新股30个月门槛没按事件月判定、
    backfill分页失败原来会静默截断数据。全部修完，backfill+backtest 都
    重跑验证过。
  - 已知局限：周K"有效低点"05号文档只有描述性规则没有像绿柱日那样的机械定义，
    代码里是工程化实现，标了注释，用前建议按 training-log 方法用真实案例校对。

## Phase 3 怎么实现的（agent推理，不是纯script）

Nick明确要求"决策层面要agent推理，不是script"——设计成两层：

```
scripts/strategy.py       机械层：MACD/状态A/开窗/绿柱日/参考价/突破/止损百分比
      ↓ (agent通过Bash调用)
scripts/signal_facts.py <code>   把machine层结果+原始K线打包成JSON给agent读
      ↓
headless claude -p (scripts/run_signals.sh + scripts/signals_prompt.md)
      ↓ agent只对两处没有机械定义的地方做判断:
        ① 行情段自查(新起点 vs 老行情半路追高)
        ② 周K有效低点的合理性核查
      ↓
signals.md(技术细节版) + daily_report.md(口语摘要版)
      ↓ run_signals.sh 自动 git commit+push
Cowork 读 signals.md/daily_report.md
```

- `positions.json`（repo根目录，不在data/里，进git）：手动维护的持仓记录，
  因为CA账户moomoo持仓API用不了（Phase0已知限制）。**Nick每次实际下单/出场
  后要手动更新这个文件**，不更新的话agent没法正确判断止损/行情段自查。
- 实测跑出来的agent判断质量不错：4只标的里3只（NVDA/AMD/QQQ）agent发现
  "月K窗口连续多年从未被规则关闭过+涨幅巨大"，主动怀疑`positions.json`可能
  漏记了真实持仓，提示Nick核对——这正是要agent而不是死script的原因。
- 中途发现并修复一个bug：`signal_facts.py`最初"找最新未关闭窗口"的逻辑用
  "从后往前找第一个未关闭的"，会在最新窗口已关闭但更早年份有个从未被关闭
  判定命中过的老窗口时，错误地把那个陈年老窗口当成当前信号（在STZ上复现过）。
  已改成只认真正最新的窗口。
- 权限模型：cron跑的headless claude用的是Nick账号自己的全局工具权限
  （`--permission-prompts none`只是防止cron卡在无人能应答的权限弹窗上，
  不是沙箱隔离），真正的范围边界写在`scripts/signals_prompt.md`里。

## 需要 Cowork 知道的事

- **调度权责边界**：所有定时任务都在本机跑，Cowork 连不到本机 moomoo OpenD
  （`127.0.0.1:11111`），不能代管这部分调度。
- **`signals.md`/`daily_report.md`从今天起每个交易日13:40 PT后会自动更新并
  push到这个repo**，Cowork可以直接读，不需要人工同步。
- **新增 `facts_cache/<代码>.json`**：跟signals.md同批产出，是每只WATCHLIST
  标的signal_facts.py的完整机械数字（状态A/开窗/绿柱日/参考价/止损线/有效
  低点全在里面）。Cowork跟Nick聊某只票、或做job①④时，直接读这个拿数字，
  不用等signals.md里有没有提到那只票。
- **Nick扩展了整体workflow，Cowork现在是主对话agent + 4个自己的定时任务**
  （在Cowork自己的界面里配，不是本机cron）。规划+每个job该用的prompt见
  `cowork_cron_jobs.md`：①关注股票定时更新 ②新闻/财报/行业资讯研究(写进
  `research_log.md`，追加不覆盖) ③选股发现新标的(过HOLDLE 04号文档企业质量
  门槛后写进`candidates.md`，**候选票不自动进WATCHLIST，Nick手动批准后本机
  才会加**) ④盯已持仓给策略建议。
- 04号文档企业质量门槛（ROE/毛利率/净利率/现金占比/现金流5项）**目前是
  Cowork选股job自己读文档判断，还没写成机械代码**（跟状态A那种严谨机械
  实现不是一个级别），按Nick决定先这样跑，观察判断质量后再考虑要不要机械化。

## 已知限制/风险

- BTC 暂无法通过 moomoo 接口抓取，watchlist 里先没有它。
- 本机（WSL/Windows）关机的话，cron 不会触发，行情会断更。
- moomoo OpenD 登录会话过期需要人工交互重新登录一次，没法完全自动化。
- 回测用的后复权(hfq)价格是数值失真的（早期基准价放大后数字很大，比如NVDA
  近期hfq价显示10万+），这是复权算法的正常现象，不代表实际报价，回测只看
  收益率不看绝对价位。
- 周K有效低点的出场判定是工程化近似，还没拿真实案例校对过，正式当信号用前
  建议先验证几个真实case。
