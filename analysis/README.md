# analysis/ — 拆解案与策划案的计算脚本、数据与图

每份案子的数字都由这里的脚本产出，可重跑复核（Python 3.11+，numpy / scipy / matplotlib；抓取脚本需网络）。

| 案子 | 脚本 | 数据 / 输出 |
|---|---|---|
| 《鸣潮》战斗 / 声骸 | wuwa_combat_math.py · wuwa_echo_cost.py | output.txt · output_echo.txt |
| 《崩坏：星穹铁道》遗器 | hsr_relic_math.py | output_hsr.txt |
| 《原神》新手关卡 | genshin_onboarding_funnel.py | output_genshin.txt |
| 合成游戏生成器经济模型 | merge_generator_economy.py | output_merge.txt |
| 三消关卡步数预算与难度曲线 | cc_scrape.py · match3_level_budget.py · novelty_rules.py · match3_sim.py · match3_calibrate.py · m3_calibration_stats.py | data/cc_levels.csv · data/m3_*.json · data/output_m3_*.txt |
| 三消十关关卡包 | m3_level_pack.py · m3_level_pack_variants.py | data/m3_level_pack.json · data/m3_variants.json |
| 天刀战斗属性与论剑 / 身份与日常时间预算 | tianya_attr_math.py · tianya_daily_budget.py | data/tianya_sources.md（数据源档案）· data/tianya_priors.md · data/ty_*.json |
| Gossip Harbor 活动疲劳 + 潮汐合成 | gh_events_scrape.py · gh_event_fatigue.py · gh_tide_event_budget.py | data/gh_events.csv · data/gh_*.json |
| 配图 | make_charts.py + 各脚本内出图 | charts/*.png |

抓取脚本经 Wayback Machine 镜像访问社区 wiki，只取公开的关卡参数 / 活动描述字段；不含任何官方内部数据。
