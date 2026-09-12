# -*- coding: utf-8 -*-
"""《天涯明月刀》端游 · 战斗属性转换与论剑数值拆解案 · 计算脚本（v1.0）

数据全部来自 data/tianya_sources.md（公开资料，标注年份）：
- 防御减伤：外功承伤 = 3000/(外防+3000)（2024 实测，K=3000）；2015 口径 外防/(0.9845·外防+2761)；2016 实测 K≈2700（外）/2787（内）
- 2023.02 十二门派五维→战斗属性线性系数表；2023.02 战斗属性→功力/战力换算表；官方"每点五维=0.8 功力"
- 对抗：命中−格挡 减算；会心−韧劲 减算（会心>韧劲才有概率会心）；每 1% 韧劲抵 0.8% 会伤、会伤下限 50%（2016 公告）；基础会伤 100%
- 论剑：2015 官方 场均 61 s、化境 0.9%；2018 六大区段位人数；S1 2015-09 → S19 2024-11；剑荡初赛 9 局 5 胜
用法：PYTHONUTF8=1 python tianya_attr_math.py → 终端 + charts/ty_*.png + data/ty_attr_summary.json
"""
import json, os
from math import comb
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
GOLD, BLUE, VIOLET, ICE, ROSE = "#b57f22", "#2f96cc", "#a259e8", "#9fd8f0", "#e07a7a"
SURFACE, INK, MUTED = "#100e26", "#cdc9e0", "#a09ac0"
GRID = (157/255, 143/255, 240/255, 0.16)
plt.rcParams.update({"font.family": ["Microsoft YaHei", "SimHei", "sans-serif"], "axes.unicode_minus": False,
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE, "text.color": INK,
    "axes.labelcolor": MUTED, "xtick.color": MUTED, "ytick.color": MUTED, "axes.edgecolor": (1, 1, 1, .12), "font.size": 11})
OUT = os.path.join(HERE, "charts"); os.makedirs(OUT, exist_ok=True)
S = {}


def style(ax):
    ax.grid(True, color=GRID, linewidth=.8); ax.set_axisbelow(True)
    for s in ("top", "right"): ax.spines[s].set_visible(False)


# =====================================================================
# 1. 防御减伤：面板递减，有效生命线性
# =====================================================================
K24 = 3000.0
def mit_2024(D): return D / (D + K24)                       # 减伤
def mit_2015(D): return D / (0.9845 * D + 2761)            # 2015 多玩口径
def mit_2016(D): return D / (D + 2700)                     # 2016 实测 c/d
D = np.arange(0, 20001, 100)
print("## 1 防御减伤（2024 K=3000）")
for d in (1000, 3000, 5000, 8000, 12000, 20000):
    r = mit_2024(d); dr = K24 / (d + K24) ** 2 * 100 * 100   # 每 +100 防 → 减伤百分点
    print(f"  外防 {d:6d}: 减伤 {100*r:5.1f}%  每 +100 防边际减伤 {dr:.2f} 个百分点  有效生命倍率 {1/(1-r):.2f}×")
# 有效生命 EHP = HP/(1-R) = HP·(D+K)/K → 对 D 线性；每 1 点防御恒 +HP/K 的有效生命
print("  有效生命 = HP × (D+K)/K：每 1 点外防恒等于 HP/3000 点气血（与当前防御无关）")
S["mitigation"] = {"K_2024": K24, "K_2015_effective": 2761 / 0.9845, "K_2016": 2700,
                   "table": {int(d): {"mit": mit_2024(d), "marg_per100": K24 / (d + K24) ** 2 * 1e4, "ehp_mult": 1 / (1 - mit_2024(d))} for d in (1000, 3000, 5000, 8000, 12000, 20000)}}
# 三版本差异
print("  三版本在同一防御下的减伤差（2024 vs 2015 / 2016）：")
for d in (3000, 6000, 10000):
    print(f"    D={d}: 2024 {100*mit_2024(d):.1f}% | 2015 {100*mit_2015(d):.1f}% | 2016 {100*mit_2016(d):.1f}%")

fig, axs = plt.subplots(1, 2, figsize=(12, 4.3))
ax = axs[0]
ax.plot(D, 100 * mit_2024(D), color=GOLD, lw=2.2, label="2024 实测 K=3000")
ax.plot(D, 100 * mit_2015(D), color=BLUE, lw=1.4, ls="--", label="2015 口径 D/(0.9845D+2761)")
ax.plot(D, 100 * mit_2016(D), color=VIOLET, lw=1.4, ls=":", label="2016 实测 K≈2700")
ax.set_xlabel("外功防御"); ax.set_ylabel("面板减伤 %"); ax.set_title("面板减伤：双曲饱和，看起来边际递减", color=INK, fontsize=12)
ax.legend(frameon=False, fontsize=9); style(ax)
ax = axs[1]
ax.plot(D, (D + K24) / K24, color=GOLD, lw=2.2, label="有效生命倍率 (D+K)/K")
ax.set_xlabel("外功防御"); ax.set_ylabel("有效生命 ÷ 面板气血"); ax.set_title("有效生命：严格线性，防御没有边际递减", color=INK, fontsize=12)
ax.legend(frameon=False, fontsize=9); style(ax)
fig.tight_layout(); fig.savefig(os.path.join(OUT, "ty_mitigation.png"), dpi=170); plt.close(fig)

# 防御 vs 气血 的实战等价（1 防 = HP/(D+K) 血）与功力权重（1 外防 0.5 功力，1 气血 0.1 功力 → 1 防 = 5 血）
print("\n  1 点外防 等价多少点气血（实战有效生命口径）：")
grid = {}
for hp in (60000, 120000, 240000):
    row = {}
    for d in (3000, 6000, 12000):
        eq = hp / (d + K24); row[d] = eq
    grid[hp] = row
    print(f"    HP={hp:6d}: " + "  ".join(f"D={d}: {row[d]:5.1f} 血" for d in row) + "   （功力口径固定 5 血）")
S["def_vs_hp"] = {"gongli_ratio": 0.5 / 0.1, "grid": {str(k): {str(d): v for d, v in r.items()} for k, r in grid.items()}}

# =====================================================================
# 2. 五维 → 战斗属性 → 功力：重算 2023 表并核对
# =====================================================================
# 功力换算（2023.02）：每点/每%
G = {"外功": 1, "内功": 1.6, "外防": .5, "内防": .5, "气血": .1, "命中": 5, "会心": 10, "会伤": 4, "格挡": 5, "韧劲": 9}
W = {"外功": .84, "内功": 1.08, "外防": .18, "内防": .18, "气血": .03, "命中": 3, "会心": 12, "会伤": 12, "格挡": 3, "韧劲": .3}  # 战力
# 五维加成（2023.02 表）：每点五维给的属性；% 类以百分点计
FIVE = {
 "雪衣": {"力道": {"外功": .3, "外防": .4}, "根骨": {"气血": 3}, "气劲": {"内功": .4, "内防": .2, "会伤": .005}, "洞察": {"气血": 1, "命中": .02, "会心": .02}, "身法": {"外功": .4, "内功": .1, "格挡": .02, "韧劲": .015}},
 "从龙": {"力道": {"外功": .65, "外防": .4, "气血": 1.5}, "根骨": {"气血": 7}, "气劲": {"内功": .4, "内防": .2, "会伤": .005}, "洞察": {"外功": .2, "命中": .02, "会心": .02}, "身法": {"格挡": .02, "韧劲": .015}},
 "少林": {"力道": {"外功": .7, "外防": .4, "气血": 2}, "根骨": {"气血": 5}, "气劲": {"外功": .1, "内功": .5, "内防": .4, "气血": 2, "会心": .005, "会伤": .005}, "洞察": {"命中": .02, "会心": .01}, "身法": {"格挡": .02, "韧劲": .015}},
 "移花": {"力道": {"外功": .30, "外防": .4}, "根骨": {"外功": .2, "气血": 7}, "气劲": {"外功": .14, "内功": .4, "内防": .2, "会伤": .005}, "洞察": {"外功": .4, "命中": .02, "会心": .02}, "身法": {"格挡": .02, "韧劲": .015}},
 "神刀": {"力道": {"外功": .52, "外防": .4, "气血": 1}, "根骨": {"气血": 6.5}, "气劲": {"内功": .4, "内防": .2, "会伤": .005}, "洞察": {"外功": .2, "命中": .02, "会心": .02}, "身法": {"格挡": .02, "韧劲": .015}},
 "五毒": {"力道": {"外功": .6, "外防": .4}, "根骨": {"气血": 5}, "气劲": {"内功": .4, "内防": .2, "会伤": .005}, "洞察": {"外功": .3, "命中": .02, "会心": .02}, "身法": {"外功": .1, "格挡": .02, "韧劲": .015}},
 "天香": {"力道": {"外功": .6, "外防": .4}, "根骨": {"气血": 7}, "气劲": {"内功": .45, "内防": .3, "会心": .002, "会伤": .005}, "洞察": {"内功": .02, "命中": .02, "会心": .01}, "身法": {"内功": .1, "格挡": .02, "韧劲": .015}},
 "真武": {"力道": {"外功": .65, "外防": .4}, "根骨": {"内功": .1, "气血": 6.3}, "气劲": {"外功": .17, "内功": .4, "内防": .4, "格挡": .01, "会心": .005, "会伤": .005, "韧劲": .0035}, "洞察": {"命中": .02, "会心": .01}, "身法": {"格挡": .01, "韧劲": .012}},
 "唐门": {"力道": {"外功": .4, "外防": .4}, "根骨": {"气血": 4}, "气劲": {"内功": .4, "内防": .2, "会伤": .005}, "洞察": {"外功": .6, "命中": .02, "会心": .02}, "身法": {"格挡": .02, "韧劲": .015}},
 "丐帮": {"力道": {"外功": .55, "外防": .4}, "根骨": {"气血": 7.5}, "气劲": {"内功": .4, "内防": .2, "会伤": .005}, "洞察": {"命中": .02, "会心": .02}, "身法": {"外功": .35, "格挡": .02, "韧劲": .02}},
 "太白": {"力道": {"外功": .35, "外防": .4}, "根骨": {"气血": 7}, "气劲": {"内功": .4, "内防": .2, "会伤": .01}, "洞察": {"外功": .35, "命中": .02, "会心": .02}, "身法": {"外功": .3, "格挡": .02, "韧劲": .015}},
 "神威": {"力道": {"外功": .8, "外防": .4}, "根骨": {"气血": 10}, "气劲": {"内功": .4, "内防": .2, "会伤": .005}, "洞察": {"命中": .02, "会心": .02}, "身法": {"格挡": .02, "韧劲": .015}},
}
# 2023.02 文章公布的"五维实际功力收益表"（用于核对）
PUB = {"唐门": (.6, .4, .76, .9, .235), "五毒": (.8, .5, .76, .7, .235), "天香": (.8, .7, .91, .232, .395), "真武": (.82, .79, 1.1615, .2, .158),
       "丐帮": (.75, .75, .76, .3, .63), "神威": (1, 1, .76, .3, .235), "太白": (.55, .7, .78, .65, .535), "移花": (.5, .9, .9, .7, .235),
       "神刀": (.82, .65, .76, .5, .235), "少林": (1.1, .5, 1.37, .2, .235), "从龙": (1, .7, .76, .5, .235), "雪衣": (.5, .3, .76, .7, .795)}
DIMS = ["力道", "根骨", "气劲", "洞察", "身法"]
def value(attrs, table):  # 每点五维 → 功力/战力
    return sum(v * table[k] for k, v in attrs.items())
print("\n## 2 五维每点实际功力（重算）vs 公布表；每点五维设计基准 0.8")
recalc = {}; mism = []
for cls in FIVE:
    row = [value(FIVE[cls][d], G) for d in DIMS]; recalc[cls] = row
    pub = PUB[cls]; diff = [abs(a - b) for a, b in zip(row, pub)]
    flag = "" if max(diff) < 0.006 else "  ⚠ 与公布表不符: " + ", ".join(f"{DIMS[i]} 算 {row[i]:.3f}/表 {pub[i]}" for i in range(5) if diff[i] >= 0.006)
    print(f"  {cls}: " + " ".join(f"{DIMS[i]} {row[i]:.3f}" for i in range(5)) + f"  合计 {sum(row):.3f}{flag}")
    if flag: mism.append(cls)
S["five_dim_recalc"] = {c: dict(zip(DIMS, r)) for c, r in recalc.items()}; S["five_dim_mismatch"] = mism
# 身法/洞察的"功力低估/高估"：与 0.8 基准的比
print("  与 0.8 基准的偏离（<1 = 官方功力高估该属性的实战价值）：")
for cls in ("唐门", "天香", "五毒"):
    print(f"    {cls}: " + " ".join(f"{DIMS[i]} {recalc[cls][i]/0.8:.2f}×" for i in range(5)))
# 战力口径（PVE）同样算一遍，看 PVP/PVE 权重差
print("  同一属性的 功力(PVP 口径) : 战力(PVE 口径) 权重比：")
ratio = {k: (G[k], W[k], (W[k] / G[k]) if G[k] else None) for k in G}
for k, (g, w, r) in ratio.items(): print(f"    {k}: 功力 {g} / 战力 {w}  → 战力÷功力 {r:.2f}")
S["gongli_vs_zhanli"] = {k: {"gongli": g, "zhanli": w, "ratio": r} for k, (g, w, r) in ratio.items()}

fig, ax = plt.subplots(figsize=(11, 4.4))
x = np.arange(len(FIVE)); wdt = .16
for i, d in enumerate(DIMS):
    ax.bar(x + (i - 2) * wdt, [recalc[c][i] for c in FIVE], wdt, label=d, color=[GOLD, ROSE, VIOLET, ICE, BLUE][i])
ax.axhline(.8, color=INK, ls="--", lw=1, alpha=.6); ax.text(len(FIVE) - .5, .82, "设计基准 0.8 功力/点", color=INK, fontsize=9, ha="right")
ax.set_xticks(x); ax.set_xticklabels(list(FIVE)); ax.set_ylabel("每点五维折算功力（2023.02）")
ax.set_title("功力是平的（每点 0.8），实战价值不是：身法普遍只值 0.16–0.24，洞察在唐门值 0.9", color=INK, fontsize=12)
ax.legend(frameon=False, ncol=5, fontsize=9); style(ax)
fig.tight_layout(); fig.savefig(os.path.join(OUT, "ty_five_dim_value.png"), dpi=170); plt.close(fig)

# =====================================================================
# 3. 对抗：韧劲的双重抵消
# =====================================================================
def exp_mult(c, cd, t):
    """期望伤害倍率。c 会心率, cd 会伤(基础 1.0=100%), t 对方韧劲；均为小数。
    会心率减算：max(c−t,0)；会伤被韧劲抵消：每 1 韧劲抵 0.8 会伤，下限 0.5。"""
    eff_c = max(c - t, 0.0); eff_cd = max(cd - 0.8 * t, 0.5)
    return 1 + eff_c * eff_cd
print("\n## 3 韧劲双重抵消：期望伤害倍率 M = 1 + max(c−t,0)·max(CD−0.8t, 0.5)")
base = dict(c=.40, cd=1.50, t=.20)
m0 = exp_mult(**base); print(f"  基准（会心 40% / 会伤 150% / 对方韧劲 20%）：M = {m0:.4f}")
d = .01
dc = exp_mult(base["c"] + d, base["cd"], base["t"]) - m0
dcd = exp_mult(base["c"], base["cd"] + d, base["t"]) - m0
dt = m0 - exp_mult(base["c"], base["cd"], base["t"] + d)
print(f"  +1% 会心 → M +{dc:.4f}；+1% 会伤 → M +{dcd:.4f}；对方 +1% 韧劲 → M −{dt:.4f}")
print(f"  1% 韧劲的防御价值 ≈ {dt/dc:.2f}% 会心 ≈ {dt/dcd:.2f}% 会伤（在基准点）；功力换算表给的是 韧劲 9 : 会心 10 : 会伤 4")
S["resilience_base"] = {"M": m0, "d_crit": dc, "d_cd": dcd, "d_res": dt, "res_in_crit": dt / dc, "res_in_cd": dt / dcd}
# 韧劲边际价值随对方会心变化（分岔：t ≥ c 时会心归零，再堆韧劲只剩会伤抵消直到 50% 下限）
print("  对方韧劲 t 从 0 到 60% 时的 M（会心 40% / 会伤 150%）：")
ts = np.arange(0, .61, .05); Ms = [exp_mult(.40, 1.5, t) for t in ts]
for t, M in zip(ts, Ms): print(f"    t={100*t:4.0f}%  M={M:.3f}")
S["res_curve"] = {f"{100*t:.0f}": M for t, M in zip(ts, Ms)}
# 会心堆到多少后会伤更划算：dM/dc = eff_cd, dM/dcd = eff_c；按功力价（会心 10、会伤 4）算每功力收益
print("  每 1 功力买到的 M 增量（会心 10 功力/%，会伤 4 功力/%），对方韧劲 20%：")
for c in (.25, .35, .45, .55, .65):
    for cd in (1.2, 1.5, 2.0):
        gc = max(cd - .8 * .2, .5) / 10; gcd = max(c - .2, 0) / 4
        better = "会心" if gc > gcd else "会伤"
    # 只打印 cd=1.5 的行，其它入 JSON
    gc = max(1.5 - .16, .5) / 10; gcd = max(c - .2, 0) / 4
    print(f"    会心 {100*c:.0f}%（会伤 150%）: 会心 {gc:.4f}/功力  会伤 {gcd:.4f}/功力  → {'堆会心' if gc > gcd else '堆会伤'}")
# 分岔点：gc = gcd → (CD−0.16)/10 = (c−0.2)/4 → c = 0.2 + 0.4·(CD−0.16)
cross = {cd: .2 + .4 * (cd - .16) for cd in (1.2, 1.5, 2.0)}
print("  会心/会伤功力分岔点（对方韧劲 20%）：" + "，".join(f"会伤 {100*cd:.0f}% → 会心 {100*c:.0f}%" for cd, c in cross.items()))
S["crit_vs_cd_crossover"] = {str(k): v for k, v in cross.items()}

fig, axs = plt.subplots(1, 2, figsize=(12, 4.3))
ax = axs[0]
for c, col in ((.30, BLUE), (.40, GOLD), (.55, VIOLET)):
    ax.plot(100 * ts, [exp_mult(c, 1.5, t) for t in ts], color=col, lw=2, marker="o", ms=3, label=f"我方会心 {100*c:.0f}%")
ax.set_xlabel("对方韧劲 %"); ax.set_ylabel("期望伤害倍率 M"); ax.set_title("韧劲双重抵消：先压会伤，再把会心压到 0", color=INK, fontsize=12)
ax.legend(frameon=False, fontsize=9); style(ax)
ax = axs[1]
cs = np.arange(.20, .80, .01)
for cd, col in ((1.2, BLUE), (1.5, GOLD), (2.0, VIOLET)):
    gc = np.full_like(cs, max(cd - .16, .5) / 10); gcd = np.maximum(cs - .2, 0) / 4
    ax.plot(100 * cs, gc / gcd.clip(1e-9), color=col, lw=2, label=f"会伤 {100*cd:.0f}%")
ax.axhline(1, color=INK, ls="--", lw=1, alpha=.6); ax.set_ylim(0, 4)
ax.set_xlabel("我方会心 %（对方韧劲 20%）"); ax.set_ylabel("每功力收益比：会心 ÷ 会伤"); ax.set_title(">1 堆会心划算，<1 堆会伤划算；分岔点随会伤上移", color=INK, fontsize=11.5)
ax.legend(frameon=False, fontsize=9); style(ax)
fig.tight_layout(); fig.savefig(os.path.join(OUT, "ty_resilience.png"), dpi=170); plt.close(fig)

# =====================================================================
# 4. 论剑：段位堆积、赛季节奏、剑荡晋级概率
# =====================================================================
print("\n## 4 论剑")
RANKS = ["心剑", "白虹", "秋水", "吹雪", "登峰", "造极", "化境"]
D2018 = {"陌上花开": [1075, 734, 641, 340, 196, 141, 1005], "大地飞鹰": [1361, 803, 721, 359, 226, 159, 1114],
         "血海飘香": [1459, 879, 727, 394, 218, 169, 1151], "青龙乱舞": [2828, 1803, 1533, 806, 425, 304, 2112]}
tot = np.array([D2018[k] for k in D2018]).sum(0)
share = tot / tot.sum()
print("  2018-03 四大区（榜内前 10000 名可见部分）心剑以上各段合计与占比：")
for r, n, s in zip(RANKS, tot, share): print(f"    {r}: {n:5d}  {100*s:5.1f}%")
print(f"  化境 ÷ 造极 = {tot[-1]/tot[-2]:.1f}×；化境 ÷ 登峰 = {tot[-1]/tot[-4]:.1f}× —— 顶端倒金字塔（化境不掉段，是堆积段）")
print("  2015-09 热身赛季官方：化境 0.9%、场均 61 秒、4000 万场")
S["ladder_2018"] = dict(zip(RANKS, [int(x) for x in tot])); S["ladder_ratio_hj_zj"] = float(tot[-1] / tot[-2])
# 赛季节奏
months = (2024 + 10 / 12) - (2015 + 8 / 12); per = months * 12 / 18   # 19 个赛季 = 18 个间隔
print(f"  S1 2015-09 → S19 2024-11：19 季 = 18 个间隔 ≈ {per:.1f} 个月/季")
S["season_months"] = per
# 剑荡初赛 9 局 5 胜：真实胜率 p → 晋级概率
def p_adv(p, n=9, k=5): return sum(comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k, n + 1))
print("  剑荡初赛 9 局 5 胜 晋级概率：")
adv = {}
for p in (.35, .40, .45, .50, .55, .60, .65, .70):
    adv[p] = p_adv(p); print(f"    真实胜率 {100*p:.0f}% → 晋级 {100*adv[p]:.1f}%")
print("  月下第一人复赛门槛 9 局 2 胜：胜率 30% 玩家也有 {:.0f}% 过线".format(100 * p_adv(.30, 9, 2)))
S["jiandang_adv"] = {f"{100*p:.0f}": v for p, v in adv.items()}

fig, axs = plt.subplots(1, 2, figsize=(12, 4.3))
ax = axs[0]
ax.barh(RANKS, tot, color=[BLUE] * 5 + [VIOLET, GOLD])
for i, n in enumerate(tot): ax.text(n + 60, i, f"{n}", va="center", color=INK, fontsize=9)
ax.invert_yaxis(); ax.set_xlabel("四大区合计人数（2018-03，榜内可见）"); ax.set_title("段位分布：造极是真瓶颈，化境是堆积段（7.6× 造极）", color=INK, fontsize=11.5)
style(ax)
ax = axs[1]
ps = np.linspace(.2, .8, 61)
ax.plot(100 * ps, [100 * p_adv(p) for p in ps], color=GOLD, lw=2.2, label="初赛 9 局 5 胜")
ax.plot(100 * ps, [100 * p_adv(p, 9, 2) for p in ps], color=BLUE, lw=1.6, ls="--", label="9 局 2 胜（月下第一人）")
ax.plot(100 * ps, 100 * ps, color=MUTED, lw=1, ls=":", label="y = x")
ax.set_xlabel("真实胜率 %"); ax.set_ylabel("晋级概率 %"); ax.set_title("九局五胜把 60% 胜率放大到 73%，40% 压到 27%", color=INK, fontsize=11.5)
ax.legend(frameon=False, fontsize=9); style(ax)
fig.tight_layout(); fig.savefig(os.path.join(OUT, "ty_ladder.png"), dpi=170); plt.close(fig)

json.dump(S, open(os.path.join(HERE, "data/ty_attr_summary.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=float)
print("\ncharts →", OUT)
