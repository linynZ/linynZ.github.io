# -*- coding: utf-8 -*-
"""《潮汐合成》7 天减负活动 · 体力预算与里程碑阈值（v1.1，审核后重写口径）

产出链按 Gossip Harbor wiki 原文建模：合成板活动的可合成棋子来自**完成厨房订单**（每单给 1 或 2 个 1 级或 2 级棋子），
不是生成器直出；生成器权重表只用于"1 个 B1 值多少体力"的定价参照（同《生成器经济模型拆解案》，B1 ≈ 8.33 体力）。
合成规则：二合一（wiki 原文 "merge two items"），i 级 = 2^(i-1) 个 1 级 → 用"B1 等价物"计数。
涨潮：每日一次，把棋盘上等级最低的落单棋子（无同级配对者）最多 TIDE_CAP 个各补一个同级"潮汐棋子"并合成
      → 每次涨潮净增 ≤ TIDE_CAP 个该级棋子 = 净增 ≤ TIDE_CAP × 2^(lv-1) 个 B1 等价物（按最低级=1 级取下限 TIDE_CAP）。
所有体力/订单数值为**假设参数**（公开资料无官方值），换参数重跑即可。
用法：PYTHONUTF8=1 python gh_tide_event_budget.py → 终端表 + charts/gh_tide_milestones.png + data/gh_tide_budget.json
"""
import json, os
from math import erf, sqrt
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
GOLD, BLUE, VIOLET, ICE = "#b57f22", "#2f96cc", "#a259e8", "#9fd8f0"
SURFACE, INK, MUTED = "#100e26", "#cdc9e0", "#a09ac0"
plt.rcParams.update({"font.family": ["Microsoft YaHei", "SimHei", "sans-serif"], "axes.unicode_minus": False, "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
                     "savefig.facecolor": SURFACE, "text.color": INK, "axes.labelcolor": MUTED, "xtick.color": MUTED, "ytick.color": MUTED, "axes.edgecolor": (1, 1, 1, .12), "font.size": 11})

# ---------- 假设参数（全部可改） ----------
P = dict(
    energy_per_order=20,      # 假设：完成一单平均耗 20 体力（订单需 2–4 个中高级菜品）
    items_per_order=1.5,      # wiki：每单给 1 或 2 个活动棋子 → 取 1.5
    item_level_mix=(0.6, 0.4),  # wiki：棋子为 1 级或 2 级 → 假设 60% 1 级 / 40% 2 级
    energy_per_session=60,    # 设计目标：每日一次 3 分钟闭环可花的体力（每次点击+拖拽约 3 秒）
    daily_gift=40,            # 假设：登录/任务免费体力
    regen_per_day=720,        # 假设：1 体力 / 2 分钟 × 24h
    days=7,
    tide_cap=2,               # 涨潮每日最多补齐 2 个落单棋子 → 净增 ≥2 个 B1 等价物（按最低级=1 级计）
    b1_energy_value=8.33,     # 1 个 B1 的体力价（生成器经济模型案：1/0.12）
    paid_tide_price_energy=25,  # 付费"再涨一次潮"定价（体力等价；宝石价按产品汇率换算，本文不给）
)
b1_per_item = P["item_level_mix"][0] * 1 + P["item_level_mix"][1] * 2       # 每个活动棋子的 B1 等价物期望 = 1.4
b1_per_order = P["items_per_order"] * b1_per_item                           # 每单 2.1
b1_per_energy = b1_per_order / P["energy_per_order"]                        # 每体力 0.105
tide_daily = P["tide_cap"]                                                    # 每日涨潮净增（下限）

profiles = {
    "轻度（只做每日一次 3 分钟）": P["energy_per_session"] * P["days"],
    "中度（每日 3 分钟 + 用完免费赠送）": (P["energy_per_session"] + P["daily_gift"]) * P["days"],
    "重度（60% 自然回复也投入活动板）": (P["regen_per_day"] * 0.6 + P["daily_gift"]) * P["days"],
}
print(f"## 产出口径：每单 {b1_per_order:.2f} B1 等价物 / {P['energy_per_order']} 体力 → 每体力 {b1_per_energy:.3f}；涨潮每日净增 ≥{tide_daily} 个（{P['days']} 天 {tide_daily*P['days']} 个）")
print("## 体力投入（7 日）与 B1 等价物期望")
budget = {}
for k, e in profiles.items():
    base = e * b1_per_energy; b1 = base + tide_daily * P["days"]
    budget[k] = dict(energy=e, b1_from_orders=base, b1_equiv=b1, tide_share=tide_daily * P["days"] / b1)
    print(f"  {k:28s} 体力 {e:6.0f} → 订单产 {base:6.1f} + 涨潮 {tide_daily*P['days']} = {b1:6.1f}（涨潮占 {100*budget[k]['tide_share']:.0f}%）")

light = budget["轻度（只做每日一次 3 分钟）"]["b1_equiv"]
tiers = [0.4, 0.7, 1.0, 1.4, 2.0]
milestones = [round(light * t) for t in tiers]
names = ["潮标 I", "潮标 II", "潮标 III", "潮标 IV", "潮标 V"]
print("\n## 里程碑阈值（B1 等价物；按轻度玩家 7 日期望的 40/70/100/140/200%）")
# 方差：订单数 ~ 体力/每单（近似固定），每单棋子数与等级随机 → 用每单 B1 等价物方差近似
var_item = P["item_level_mix"][0] * 1 + P["item_level_mix"][1] * 4 - b1_per_item ** 2
var_order = P["items_per_order"] * var_item + 0.25 * b1_per_item ** 2        # 棋子数 1/2 各半的方差 0.25
e_light = profiles["轻度（只做每日一次 3 分钟）"]
sigma = sqrt(var_order * e_light / P["energy_per_order"])
def p_reach(m): return 0.5 * (1 - erf((m - light) / (sigma * sqrt(2))))
for n, m, t in zip(names, milestones, tiers):
    reach = " ".join("✓" if v["b1_equiv"] >= m else "✗" for v in budget.values())
    print(f"  {n:6s} {m:4d}（×{t}）  轻/中/重 期望达成：{reach}   轻度达成概率 {100*p_reach(m):.0f}%")
print(f"  轻度玩家 7 日期望 {light:.1f}，σ≈{sigma:.1f}（订单产出独立近似）")
# 到达日：轻度玩家累计到各档的期望天数
daily_light = light / P["days"]
reach_day = {n: (m / daily_light) for n, m in zip(names, milestones)}
print("  轻度玩家期望到达日：" + "，".join(f"{n} D{max(1, int(np.ceil(d)))}" for n, d in reach_day.items()))

# ---------- 付费点：再涨一次潮 ----------
extra_b1 = tide_daily
value_energy = extra_b1 * P["b1_energy_value"]
print(f"\n## 付费点：再涨一次潮 = 当日再净增 ≥{extra_b1} 个 B1 等价物，价值 ≈ {value_energy:.1f} 体力；定价 {P['paid_tide_price_energy']} 体力等价（溢价 {P['paid_tide_price_energy']/value_energy:.1f}×）。"
      f"这是**有上限的小额产出加成**，不是便利性售卖；对轻度玩家 7 日总量的影响上限 = {extra_b1*P['days']}/{light:.0f} = {100*extra_b1*P['days']/light:.0f}%")

json.dump(dict(params=P, b1_per_order=b1_per_order, b1_per_energy=b1_per_energy, budget=budget, milestones=dict(zip(names, milestones)), light_sigma=sigma,
               p_reach={n: p_reach(m) for n, m in zip(names, milestones)}, reach_day=reach_day),
          open(os.path.join(HERE, "data/gh_tide_budget.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

# ---------- 图 ----------
fig, ax = plt.subplots(figsize=(9, 4.2))
days = np.arange(0, 8); cols = [BLUE, GOLD, VIOLET]
for (k, v), c in zip(budget.items(), cols):
    ax.plot(days, days / 7 * v["b1_equiv"], color=c, lw=2.2, marker="o", ms=4, label=k)
for n, m in zip(names, milestones):
    ax.axhline(m, color=ICE, alpha=.35, ls="--", lw=1); ax.text(0.05, m + 1, f"{n} {m}", color=ICE, fontsize=8.5)
ax.set_xlabel("活动第几天"); ax.set_ylabel("累计 B1 等价物（期望）"); ax.set_xticks(days); ax.set_ylim(0, max(milestones) * 1.25)
hv = budget["重度（60% 自然回复也投入活动板）"]["b1_equiv"]; ax.annotate(f"重度 D7 ≈ {hv:.0f}（超出图幅）", (2, max(milestones) * 1.15), color=VIOLET, fontsize=9)
ax.set_title("《潮汐合成》里程碑 5 档：轻度玩家 7 天期望恰到 III，IV/V 留给中重度（示例参数）", color=INK, fontsize=12)
ax.grid(True, color=(157/255, 143/255, 240/255, .16)); ax.set_axisbelow(True)
for s in ("top", "right"): ax.spines[s].set_visible(False)
ax.legend(frameon=False, fontsize=9, loc="upper left"); fig.tight_layout(); fig.savefig(os.path.join(HERE, "charts/gh_tide_milestones.png"), dpi=170)
print("chart → charts/gh_tide_milestones.png")
