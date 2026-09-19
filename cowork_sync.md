# Cowork Sync

> Claude Code 每次阶段性进展后更新这份文件。Cowork 用自己的 cron 每天读一次，
> 了解 Claude Code 这边在做什么、进度到哪、有什么依赖或阻塞。这不是信号文件
> （信号见 `signals.md`/`daily_report.md`），是状态同步文件。

最后更新: 2026-09-19

## 当前阶段

Phase 1（数据层）刚完成，下一个 session 开始 Phase 2（策略层）。

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

## 下一步（Phase 2，未开始）

- MACD/state-A 信号逻辑 + 历史回测，直接读 `investment-system/` 六件套方法论
  （尤其 `03-state-a-entry-timing-system.md`、`06-entry-decision-flowchart.md`）。
- 数据源是 Phase 1 的 `data/quotes.db`。

## 需要 Cowork 知道的事

- **调度权责边界**：所有定时任务（抓行情的 cron）都在本机跑，Cowork 连不到
  本机 moomoo OpenD（`127.0.0.1:11111`），不能代管这部分调度。Cowork 只读
  Claude Code 产出的文件（`signals.md`/`daily_report.md`，Phase 3 后半才会有）。
- Phase 3/4 交接文件还没生成，等 Phase 2 出信号逻辑之后才有。

## 已知限制/风险

- BTC 暂无法通过 moomoo 接口抓取，watchlist 里先没有它。
- 本机（WSL/Windows）关机的话，cron 不会触发，行情会断更。
- moomoo OpenD 登录会话过期需要人工交互重新登录一次，没法完全自动化。
