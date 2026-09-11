# -*- coding: utf-8 -*-
"""Gossip Harbor 活动疲劳分析 · 三命题计算脚本（v1.0）

数据：data/gh_events.csv（gh_events_scrape.py 产出，79 行，page_status 标证据等级）
     + 主页 Event Calendar / 各活动页时长（见 data/gh_event_categories.txt 与 CSV notes）
命题：①模板复用率 ②竞争（排行榜）占比与奖励头部集中 ③一周并行活动窗口数
用法：PYTHONUTF8=1 python gh_event_fatigue.py  → 终端 + charts/gh_*.png + data/gh_fatigue_summary.json
"""
import csv, json, os, collections
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
GOLD, BLUE, VIOLET, ICE = "#b57f22", "#2f96cc", "#a259e8", "#9fd8f0"
SURFACE, INK, MUTED = "#100e26", "#cdc9e0", "#a09ac0"
GRID = (157/255, 143/255, 240/255, 0.16)
plt.rcParams.update({"font.family": ["Microsoft YaHei", "SimHei", "sans-serif"], "axes.unicode_minus": False,
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE, "text.color": INK,
    "axes.labelcolor": MUTED, "xtick.color": MUTED, "ytick.color": MUTED, "axes.edgecolor": (1, 1, 1, .12), "font.size": 11})
OUT = os.path.join(HERE, "charts")


def style(ax):
    ax.grid(True, color=GRID, linewidth=.8); ax.set_axisbelow(True)
    for s in ("top", "right"): ax.spines[s].set_visible(False)


rows = list(csv.DictReader(open(os.path.join(HERE, "data/gh_events.csv"), encoding="utf-8-sig")))
summary = {}

# ---------- ① 模板复用率：合成板活动 = 4 个棋盘模板换皮 ----------
merging = [r for r in rows if r["category"].startswith("Merging")]
sub = collections.Counter((r["subcategory"] or "未明") for r in merging)
deco = [r for r in rows if r["category"].startswith("Decoration")]
print("## ① 模板复用")
print(f"  合成板活动 {len(merging)} 个 → 子类型分布 {dict(sub)}；明确子类型的 {sum(v for k,v in sub.items() if k!='未明')} 个全部落在 4 个模板（云雾/多层/挖掘/单层）")
print(f"  装饰活动 {len(deco)} 个 → 1 个模板（订单产装饰点→按阶段买永久装饰）")
named_overview = [r for r in rows if r["page_status"].startswith("overview") or r["page_status"].startswith("archived")]
log_only = [r for r in rows if r["page_status"].startswith("log")]
print(f"  总览页/存档页活动 {len(named_overview)} 个；更新日志 2025-04~10 另出现 {len(log_only)} 个新名字（约 6.5 个月）→ 每月约 {len(log_only)/6.5:.1f} 个新命名活动，同期 wiki 分类页新增玩法子类 0 个（以 wiki 分类为准，可能低估）")
# 有子类型的 merging 事件：名字数 / 模板数
templ_ratio = sum(v for k, v in sub.items() if k != "未明") / 4
print(f"  合成板：{sum(v for k,v in sub.items() if k!='未明')} 个名字 ÷ 4 个模板 = 每个模板平均复用 {templ_ratio:.1f} 次（仅计总览页已归类者，下限）")
summary["template"] = {"merging_n": len(merging), "merging_sub": dict(sub), "deco_n": len(deco), "names_per_template": templ_ratio,
                        "log_only_new_names": len(log_only), "new_names_per_month": len(log_only) / 6.5}

# ---------- ② 竞争占比与奖励头部集中 ----------
det = [r for r in rows if r["is_competitive"] in ("true", "false")]
comp = [r for r in det if r["is_competitive"] == "true"]
print("\n## ② 竞争占比")
print(f"  可判定 {len(det)} 个活动中排行榜/对手制 {len(comp)} 个 = {100*len(comp)/len(det):.0f}%：{[r['event_name'] for r in comp]}")
coins = [r for r in rows if r["category"] == "Coins"]
print(f"  但按'周历'权重看：每周固定一档硬币赛（Beat the Heat / Lori / Ziva 三选一轮换，横跨周五到周一四天）；三档中 Beat the Heat 有页面确认为排行榜制，Ziva 仅 Tips 页描述为赛跑制、Lori 为个人里程碑——至少一档、可能两档是排行榜，轮换比例未知")
print("  头部集中：有页面快照的 2 个竞争活动——Beat the Heat Wipeout 每轮小组前 1/2/3 名有奖、Tidal Beats Fest 每阶段前三名——奖励都只发前三；24-Hour Player Competitions 仅有更新日志记录，按名次发奖但档位未知")
summary["competition"] = {"determined": len(det), "competitive": len(comp), "share": len(comp) / len(det), "weekly_coin_race_competitive_share": "1/3~2/3（轮换比例未知）",
                          "top3_only_archived": 2}

# ---------- ③ 一周并行窗口数（按主页 Event Calendar + 各活动时长，2025-11 快照） ----------
# 每天在线的"独立活动窗口"：常驻(persistent) + 周期(weekly) + 随机(random, 用周历里'possibly'出现天数计)
DAYS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
persistent = ["合成板活动（同时恒有 1 个，结束即开下一个）", "Restaurant Goals 周任务清单", "Seasons 赛季通行证（含 24h 限时任务）"]   # 需每日操作
passive = ["Card Collection 集卡相册", "装饰活动（按月一档）"]   # 被动累积，不需每日操作，单独计
weekly = {"硬币赛（周五 10:00 开 → 周一 10:00 收）": [4, 5, 6, 0]}          # 周五六日一
random_ev = {"Mutineer Mayhem 限时订单": [1, 2, 3], "Raccoon Rascals/Banana Peel 随机订单": [6, 0, 3, 4, 1],
             "24h 其他类活动（Bingo/Big Drop Rush 等，'often 24-hour'）": [0, 1, 2, 3, 4, 5, 6]}
per_day = []
for d in range(7):
    n_p = len(persistent); n_w = sum(1 for k, v in weekly.items() if d in v); n_r = sum(1 for k, v in random_ev.items() if d in v)
    per_day.append((DAYS[d], n_p, n_w, n_r, n_p + n_w + n_r, len(passive)))
print("\n## ③ 一周并行活动窗口（常驻 + 周期 + 随机可能）")
for d, p, w, r, tot, pv in per_day: print(f"  {d}  需操作常驻 {p} + 周期 {w} + 随机 {r} = {tot}（另有被动 {pv}）")
avg = sum(x[4] for x in per_day) / 7
print(f"  需每日操作的窗口日均 {avg:.1f} 个；只算常驻+周期（确定会有的）日均 {sum(x[1]+x[2] for x in per_day)/7:.1f}；被动窗口另有 {len(passive)} 个。阈值 3 为作者经验值（一天里超过三件'必须做'就开始像清单）")
summary["windows"] = {"per_day": per_day, "avg": avg, "persistent": persistent, "passive": passive, "weekly": list(weekly), "random": list(random_ev)}
json.dump(summary, open(os.path.join(HERE, "data/gh_fatigue_summary.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

# ---------- 图 1：一周窗口堆叠 ----------
fig, ax = plt.subplots(figsize=(9, 3.9))
x = range(7)
ax.bar(x, [d[1] for d in per_day], color=BLUE, alpha=.75, label="需每日操作的常驻（合成板/周任务/赛季）")
ax.bar(x, [d[2] for d in per_day], bottom=[d[1] for d in per_day], color=GOLD, label="周期（硬币赛 周五→周一）")
ax.bar(x, [d[3] for d in per_day], bottom=[d[1] + d[2] for d in per_day], color=VIOLET, alpha=.8, label="随机可能（限时订单/24h 活动）")
ax.set_xticks(list(x)); ax.set_xticklabels(DAYS); ax.set_ylabel("同时在线的活动窗口数")
ax.axhline(3, color=ICE, ls="--", lw=1.2); ax.text(6.4, 3.1, "命题③阈值 3", color=ICE, fontsize=9, ha="right")
ax.set_title(f"一周需操作的并行活动窗口：日均 {avg:.1f} 个（不含集卡/装饰两个被动窗口；2025-11 周历快照）", color=INK, fontsize=12)
ax.legend(frameon=False, fontsize=9, loc="upper left"); style(ax); fig.tight_layout(); fig.savefig(os.path.join(OUT, "gh_weekly_windows.png"), dpi=170); plt.close(fig)

# ---------- 图 2：模板复用 ----------
fig, ax = plt.subplots(figsize=(9, 3.6))
labels = ["云雾板", "多层板", "挖掘板", "单层板", "装饰(积分换装饰)", "硬币赛"]
key = {"云雾板": "Cloudy", "多层板": "Multilevel", "挖掘板": "Digging(Scrolling)", "单层板": "Single level"}
vals = [sub.get(key[l], 0) for l in labels[:4]] + [len(deco), len(coins)]
ax.barh(labels, vals, color=[BLUE, BLUE, BLUE, BLUE, GOLD, VIOLET])
for i, v in enumerate(vals): ax.text(v + .15, i, f"{v} 个活动名", va="center", color=INK, fontsize=10)
ax.invert_yaxis(); ax.set_xlabel("同一模板下的活动名数量（wiki 总览页 + 存档页，下限）")
ax.set_title(f"模板复用：6 个玩法模板承载了 {sum(vals)} 个活动名", color=INK, fontsize=12)
style(ax); fig.tight_layout(); fig.savefig(os.path.join(OUT, "gh_template_reuse.png"), dpi=170); plt.close(fig)
print("\ncharts →", OUT)
