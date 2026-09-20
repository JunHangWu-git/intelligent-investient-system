# Cowork 定时任务规划（Nick 自己在 Cowork 里配）

这4个job都在Cowork（云端）跑，不需要moomoo/本机数据——本机Claude Code只负责
把机械数字算好、落进repo（`signals.md`/`daily_report.md`/`facts_cache/*.json`），
Cowork读这些文件+自己上网研究，不重新算MACD/状态A这些机械数字。

**每个job开头都要先`git pull`拿最新的repo内容**（本机每个交易日13:40 PT后会
push新数据），不pull就是在读旧数据。

---

## Job① 关注股票定时更新

**频率建议**：每个交易日，本机13:40 PT那轮跑完之后，留够时间给commit+push，
建议14:00 PT左右。

**Prompt**：
```
git pull最新代码。读 signals.md 和 daily_report.md（今天的信号+简报）。
用HOLDLE方法论的语言（状态A/开窗/绿柱日/参考价这些术语，参考
holdle-knowledge/investment-system/ 六件套）给Nick做一个口语化的今日更新，
不要照抄表格，要讲清楚"为什么"。如果两个文件都没有today的日期（比如本机
没跑成功），明确告诉Nick"今天没收到新数据，可能本机那边有问题"，不要装作
有数据。
```

---

## Job② 新闻/财报/行业资讯研究

**频率建议**：每天（或你觉得太频繁可以改成每周三次），跟job①错开时间，
比如收盘前或另一个你方便看的时段都行，不依赖本机数据所以时间自由。

**Prompt**：
```
git pull最新代码。针对 scripts/config.py 里 WATCHLIST 这几只标的
（US.NVDA/US.AMD/US.STZ/US.QQQ）+ 半导体/消费/科技等相关行业，上网搜索
最近的新闻、财报发布、行业动态。把有价值的信息追加写进 research_log.md
（注意是追加，不要删除或覆盖已有内容，格式看文件里的说明）。跟HOLDLE方法论
相关的信息（比如财报里的ROE/毛利率数据、行业景气度变化）优先记录。写完
commit+push（只commit research_log.md这一个文件）。
```

---

## Job③ 选股（发现新标的）

**频率建议**：每周一次（不用跟job②一样高频，选股不用追热点）。

**Prompt**：
```
git pull最新代码。读 research_log.md 最近的笔记 + 自己上网搜索，找有上升
空间的股票候选。**每只候选票必须先读 holdle-knowledge/investment-system/
04-enterprise-analysis-system.md，按里面的企业质量门槛（ROE≥20%、毛利率
≥20%、净利率≥10%、现金占比≥10%、经营现金流为正且稳定增长）逐项核实数据、
过五项才能放进候选池**，不达标的不要写进去（也不用写"否决了谁"，省篇幅）。
过关的候选票追加写进 candidates.md（格式看文件里的说明，按追加不覆盖），
写清楚五项数据的具体数字和来源，不能只写"符合门槛"。写完commit+push（只
commit candidates.md）。

不用做技术面判断（状态A/开窗那些）——那是本机的活，Nick看了候选票觉得
值得跟踪，会让本机加进WATCHLIST并补数据。
```

---

## Job④ 盯已持仓策略

**频率建议**：每个交易日，跟job①同一批（读的是同一份新数据）。

**Prompt**：
```
git pull最新代码。读 positions.json（Nick手动维护的持仓记录，为空`{}`表示
空仓）。对每个有记录的持仓，读 facts_cache/<代码>.json 里的机械数字
（current_stop_loss止损线/current_effective_low有效低点/weekly_trace_since_entry
周K轨迹），结合 holdle-knowledge/investment-system/05-trading-management-rules.md
的交易管理规则，给Nick讲清楚现在该怎么办（继续持有/接近止损线要注意/有效
低点被跌破建议出场）。

**重要**：Nick的moomoo是CA账户，API查不到真实持仓，positions.json完全靠
Nick手动维护，可能不准。如果你从facts_cache里的数据（比如某标的月K窗口
连续多年没关闭过、涨幅巨大）怀疑positions.json可能漏记了实际持仓，明确
提示Nick核对，不要假装没发现。

不自动下单，任何结论都是给Nick参考，最终决策Nick自己判断。
```
