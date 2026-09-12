# -*- coding: utf-8 -*-
"""《天涯明月刀》端游 · 战斗属性转换与论剑数值拆解案 · 计算脚本（v1.1，两路审核后修订）

数据全部来自 data/tianya_sources.md（公开资料，标注年份）：
- 防御减伤：外功承伤 = 3000/(外防+3000)（2024 实测、2025-07 发布，K=3000）；2015 口径 外防/(0.9845·外防+2761)（二手转述）；2016 实测 K≈2700
- 2023.02 十二门派五维→战斗属性线性系数表；2023.02 战斗属性→功力/战力换算表；官方"每点五维=0.8 功力"（2016）
- 对抗：命中−格挡 减算；会心−韧劲 减算；每 1% 韧劲抵 0.8% 会伤、会伤最低降至 50%（2016-06-23 公告，本文取"绝对百分点"读法）
- 论剑：2015 官方 场均 61 s；2018 四大区段位人数（榜内可见）；S1 2015-09 → S19 2024-11；剑荡初赛 9 局 5 胜
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
# 1. 防御减伤：面板递减；固定气血下有效生命线性；血防之间是乘法关系
# =====================================================================
K24 = 3000.0
def mit_2024(D): return D / (D + K24)
def mit_2015(D): return D / (0.9845 * D + 2761)
def mit_2016(D): return D / (D + 2700)
D = np.arange(0, 20001, 100)
print("## 1 防御减伤（2024 实测 K=3000）")
tbl = {}
for d in (1000, 3000, 5000, 8000, 12000, 20000):
    r = mit_2024(d); dr = K24 / (d + K24) ** 2 * 1e4
    tbl[d] = dict(mit=r, marg_per100=dr, ehp_mult=1 / (1 - r))
    print(f"  外防 {d:6d}: 减伤 {100*r:5.1f}%  每 +100 防边际减伤 {dr:.2f} 个百分点  有效生命倍率 {1/(1-r):.2f}×")
print("  固定气血下：有效生命 EHP = HP × (D+K)/K，对 D 线性，每 1 防 = HP/K 点【有效生命】")
print("  血防取舍：1 防折成【面板气血】= HP/(D+K)，随 D 递减；功力价 防 0.5 : 血 0.1 = 5 → 当 HP > 5(D+K) 时功力低估防御，反之高估")
S["mitigation"] = {"K_2024": K24, "K_2015_effective": 2761 / 0.9845, "K_2016": 2700, "table": tbl}
print("  三版本在同一防御下的减伤（2024 / 2015 / 2016）：")
for d in (3000, 6000, 10000):
    print(f"    D={d}: {100*mit_2024(d):.1f}% | {100*mit_2015(d):.1f}% | {100*mit_2016(d):.1f}%")
print("  1 点外防 等价多少点气血（= HP/(D+K)）：")
grid = {}
for hp in (60000, 120000, 240000):
    grid[hp] = {d: hp / (d + K24) for d in (3000, 6000, 12000)}
    print(f"    HP={hp:6d}: " + "  ".join(f"D={d}: {v:5.1f} 血" for d, v in grid[hp].items()) + f"   平衡点 HP=5(D+K) 处的 D = {hp/5 - K24:.0f}")
S["def_vs_hp"] = {"gongli_ratio": 5.0, "grid": {str(k): {str(d): v for d, v in r.items()} for k, r in grid.items()}}

fig, axs = plt.subplots(1, 2, figsize=(12, 4.3))
ax = axs[0]
ax.plot(D, 100 * mit_2024(D), color=GOLD, lw=2.2, label="2024 实测 K=3000")
ax.plot(D, 100 * mit_2015(D), color=BLUE, lw=1.4, ls="--", label="2015 转述 D/(0.9845D+2761)")
ax.plot(D, 100 * mit_2016(D), color=VIOLET, lw=1.4, ls=":", label="2016 实测 K≈2700")
ax.set_xlabel("外功防御"); ax.set_ylabel("面板减伤 %"); ax.set_title("面板减伤：双曲饱和", color=INK, fontsize=12)
ax.legend(frameon=False, fontsize=9); style(ax)
ax = axs[1]
ax.plot(D, (D + K24) / K24, color=GOLD, lw=2.2, label="有效生命倍率 (D+K)/K（固定气血）")
ax2 = ax.twinx(); ax2.plot(D, 120000 / (D + K24), color=ICE, lw=1.6, ls="--", label="1 防折算气血 HP/(D+K)，HP=12 万")
ax2.set_ylabel("1 防 = 多少血"); ax2.tick_params(colors=MUTED); ax2.spines["top"].set_visible(False)
ax.set_xlabel("外功防御"); ax.set_ylabel("有效生命 ÷ 面板气血"); ax.set_title("固定气血下线性；相对气血则递减（血防乘法）", color=INK, fontsize=12)
h1, l1 = ax.get_legend_handles_labels(); h2, l2 = ax2.get_legend_handles_labels(); ax.legend(h1 + h2, l1 + l2, frameon=False, fontsize=8.5, loc="upper left"); style(ax)
fig.tight_layout(); fig.savefig(os.path.join(OUT, "ty_mitigation.png"), dpi=170); plt.close(fig)

# =====================================================================
# 2. 五维 → 战斗属性 → 功力：重算 2023 表并核对
# =====================================================================
G = {"外功": 1, "内功": 1.6, "外防": .5, "内防": .5, "气血": .1, "命中": 5, "会心": 10, "会伤": 4, "格挡": 5, "韧劲": 9}
W = {"外功": .84, "内功": 1.08, "外防": .18, "内防": .18, "气血": .03, "命中": 3, "会心": 12, "会伤": 12, "格挡": 3, "韧劲": .3}
ZERO = {"破招": (1, 0), "拆招": (2, 0), "破伤": (0, 10), "御伤": (0, 5)}
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
PUB = {"唐门": (.6, .4, .76, .9, .235), "五毒": (.8, .5, .76, .7, .235), "天香": (.8, .7, .91, .232, .395), "真武": (.82, .79, 1.1615, .2, .158),
       "丐帮": (.75, .75, .76, .3, .63), "神威": (1, 1, .76, .3, .235), "太白": (.55, .7, .78, .65, .535), "移花": (.5, .9, .9, .7, .235),
       "神刀": (.82, .65, .76, .5, .235), "少林": (1.1, .5, 1.37, .2, .235), "从龙": (1, .7, .76, .5, .235), "雪衣": (.5, .3, .76, .7, .795)}
DIMS = ["力道", "根骨", "气劲", "洞察", "身法"]
def value(attrs, table): return sum(v * table[k] for k, v in attrs.items())
print("\n## 2 五维每点按功力权重折算（重算）vs 公布表；名义 0.8/点")
recalc = {}; mism = []
for cls in FIVE:
    row = [value(FIVE[cls][d], G) for d in DIMS]; recalc[cls] = row
    pub = PUB[cls]; diff = [abs(a - b) for a, b in zip(row, pub)]
    flag = "" if max(diff) < 0.006 else "  ⚠ 与公布表不符: " + ", ".join(f"{DIMS[i]} 算 {row[i]:.3f}/表 {pub[i]}" for i in range(5) if diff[i] >= 0.006)
    print(f"  {cls}: " + " ".join(f"{DIMS[i]} {row[i]:.3f}" for i in range(5)) + f"  合计 {sum(row):.3f}{flag}")
    if flag: mism.append(cls)
S["five_dim_recalc"] = {c: dict(zip(DIMS, r)) for c, r in recalc.items()}; S["five_dim_mismatch"] = mism
G10 = dict(G, 韧劲=10)
print(f"  韧劲系数裁决：唐门身法 按韧劲=9 折 {value(FIVE['唐门']['身法'], G):.3f}，按 10 折 {value(FIVE['唐门']['身法'], G10):.3f}；公布表 0.235 → 2023 系数为 9")
print("  与名义 0.8 的偏离：")
for cls in ("唐门", "天香", "五毒"):
    print(f"    {cls}: " + " ".join(f"{DIMS[i]} {recalc[cls][i]/0.8:.2f}×" for i in range(5)))
print("  功力 / 战力 零权重行：" + "，".join(f"{k} {g}/{w}" for k, (g, w) in ZERO.items()))
ratio = {k: (G[k], W[k], W[k] / G[k]) for k in G}
for k, (g, w, r) in ratio.items(): print(f"    {k}: 功力 {g} / 战力 {w}  → 战力÷功力 {r:.2f}")
S["gongli_vs_zhanli"] = {k: {"gongli": g, "zhanli": w, "ratio": r} for k, (g, w, r) in ratio.items()}; S["zero_rows"] = ZERO

fig, ax = plt.subplots(figsize=(11, 4.4))
x = np.arange(len(FIVE)); wdt = .16
for i, d in enumerate(DIMS):
    ax.bar(x + (i - 2) * wdt, [recalc[c][i] for c in FIVE], wdt, label=d, color=[GOLD, ROSE, VIOLET, ICE, BLUE][i])
ax.axhline(.8, color=INK, ls="--", lw=1, alpha=.6); ax.text(len(FIVE) - .5, .82, "名义 0.8 功力/点", color=INK, fontsize=9, ha="right")
ax.set_xticks(x); ax.set_xticklabels(list(FIVE)); ax.set_ylabel("每点五维按功力权重折算（2023.02）")
ax.set_title("功力体系内部不自洽：五维名义 0.8，按其自身属性权重折算 0.16–1.37", color=INK, fontsize=12)
ax.legend(frameon=False, ncol=5, fontsize=9); style(ax)
fig.tight_layout(); fig.savefig(os.path.join(OUT, "ty_five_dim_value.png"), dpi=170); plt.close(fig)

# =====================================================================
# 3. 对抗：韧劲的双重抵消（假设：会伤下限为绝对 50 个百分点；抵消为绝对百分点）
# =====================================================================
def exp_mult(c, cd, t, floor=0.5, rel=False):
    eff_c = max(c - t, 0.0)
    eff_cd = max(cd * (1 - 0.8 * t), floor) if rel else max(cd - 0.8 * t, floor)
    return 1 + eff_c * eff_cd
print("\n## 3 韧劲双重抵消：M = 1 + max(c−t,0)·max(CD−0.8t, 0.5)")
c0, cd0, t0 = .40, 1.50, .20; d = .01
m0 = exp_mult(c0, cd0, t0)
dc = exp_mult(c0 + d, cd0, t0) - m0; dcd = exp_mult(c0, cd0 + d, t0) - m0; dt = m0 - exp_mult(c0, cd0, t0 + d)
print(f"  基准（会心 40% / 会伤 150% / 对方韧劲 20%）：M = {m0:.4f}；+1% 会心 +{dc:.4f}；+1% 会伤 +{dcd:.4f}；对方 +1% 韧劲 −{dt:.4f}")
print(f"  1% 韧劲 ≈ {dt/dc:.2f}% 会心 ≈ {dt/dcd:.2f}% 会伤（基准点）；功力表 韧劲 9 : 会心 10 : 会伤 4（0.9 与 1.11 分居 1 两侧：同量级、方向相反）")
m0r = exp_mult(c0, cd0, t0, rel=True); dtr = m0r - exp_mult(c0, cd0, t0 + d, rel=True); dcdr = exp_mult(c0, cd0 + d, t0, rel=True) - m0r
print(f"  若 0.8% 为相对抵消（CD×(1−0.8t)）：基准 M = {m0r:.4f}，1% 韧劲 ≈ {dtr/dcdr:.2f}% 会伤（绝对读法 {dt/dcd:.2f}）")
S["resilience_base"] = {"M": m0, "d_crit": dc, "d_cd": dcd, "d_res": dt, "res_in_crit": dt / dc, "res_in_cd": dt / dcd, "rel_reading_res_in_cd": dtr / dcdr}
print("  功力'会伤:会心=0.4'相对实战边际比的高估倍数（会伤 150%）：")
sens = {}
for c_ in (.30, .45, .60):
    row = {}
    for t_ in (.10, .20, .30):
        m_ = exp_mult(c_, cd0, t_); dcx = exp_mult(c_ + d, cd0, t_) - m_; dcdx = exp_mult(c_, cd0 + d, t_) - m_
        row[t_] = 0.4 / (dcdx / dcx) if dcx > 0 and dcdx > 0 else float("nan")
    sens[c_] = row
    print(f"    会心 {100*c_:.0f}%: " + "  ".join(f"韧劲 {100*t_:.0f}% → {v:.1f}×" for t_, v in row.items()))
S["cd_overvalue_sens"] = {f"{100*c_:.0f}": {f"{100*t_:.0f}": v for t_, v in r.items()} for c_, r in sens.items()}
ts = np.arange(0, .61, .05); Ms = [exp_mult(c0, cd0, t) for t in ts]
S["res_curve"] = {f"{100*t:.0f}": M for t, M in zip(ts, Ms)}
print("  对方韧劲 0→60% 时 M（会心 40%/会伤 150%）：" + " ".join(f"{100*t:.0f}%:{M:.2f}" for t, M in zip(ts, Ms)))
cross = {cd: .2 + .4 * (cd - .16) for cd in (1.2, 1.5, 2.0)}
print("  以功力为统一计价单位时（功力天平 / 自定义模板场景）会心→会伤分岔点（对方韧劲 20%）：" + "，".join(f"会伤 {100*cd:.0f}% → 会心 {100*c:.0f}%" for cd, c in cross.items()))
S["crit_vs_cd_crossover"] = {str(k): v for k, v in cross.items()}

fig, axs = plt.subplots(1, 2, figsize=(12, 4.3))
ax = axs[0]
for c, col in ((.30, BLUE), (.40, GOLD), (.55, VIOLET)):
    ax.plot(100 * ts, [exp_mult(c, cd0, t) for t in ts], color=col, lw=2, marker="o", ms=3, label=f"我方会心 {100*c:.0f}%")
ax.set_xlabel("对方韧劲 %"); ax.set_ylabel("期望伤害倍率 M"); ax.set_title("韧劲双重抵消：先压会伤，再把会心压到 0", color=INK, fontsize=12)
ax.legend(frameon=False, fontsize=9); style(ax)
ax = axs[1]
cs = np.arange(.20, .80, .01)
for cd, col in ((1.2, BLUE), (1.5, GOLD), (2.0, VIOLET)):
    gc = np.full_like(cs, max(cd - .16, .5) / 10); gcd = np.maximum(cs - .2, 0) / 4
    ax.plot(100 * cs, gc / gcd.clip(1e-9), color=col, lw=2, label=f"会伤 {100*cd:.0f}%")
ax.axhline(1, color=INK, ls="--", lw=1, alpha=.6); ax.set_ylim(0, 4)
ax.set_xlabel("我方会心 %（对方韧劲 20%）"); ax.set_ylabel("每功力收益比：会心 ÷ 会伤"); ax.set_title("功力作计价单位时：>1 堆会心，<1 堆会伤", color=INK, fontsize=11.5)
ax.legend(frameon=False, fontsize=9); style(ax)
fig.tight_layout(); fig.savefig(os.path.join(OUT, "ty_resilience.png"), dpi=170); plt.close(fig)

# =====================================================================
# 4. 论剑：段位分布、赛季节奏、剑荡晋级概率
# =====================================================================
print("\n## 4 论剑")
RANKS = ["心剑", "白虹", "秋水", "吹雪", "登峰", "造极", "化境"]
D2018 = {"陌上花开": [1075, 734, 641, 340, 196, 141, 1005], "大地飞鹰": [1361, 803, 721, 359, 226, 159, 1114],
         "血海飘香": [1459, 879, 727, 394, 218, 169, 1151], "青龙乱舞": [2828, 1803, 1533, 806, 425, 304, 2112]}
tot = np.array([D2018[k] for k in D2018]).sum(0); share = tot / tot.sum()
print("  2018-03 四大区（心剑以上合计均 <10,000、榜单未截断的四个区）各段合计与占比：")
for r, n, s in zip(RANKS, tot, share): print(f"    {r}: {n:5d}  {100*s:5.1f}%")
drops = [1 - tot[i + 1] / tot[i] for i in range(5)]
print("  心剑→造极逐段降幅: " + ", ".join(f"{100*x:.0f}%" for x in drops))
print(f"  化境 ÷ 造极 = {tot[-1]/tot[-2]:.1f}×；化境 ÷ 登峰 = {tot[-1]/tot[-4]:.1f}×")
S["ladder_2018"] = dict(zip(RANKS, [int(x) for x in tot])); S["ladder_ratio_hj_zj"] = float(tot[-1] / tot[-2]); S["ladder_drops"] = drops
per19 = ((2024 + 10 / 12) - (2015 + 8 / 12)) * 12 / 19
print(f"  S1 起 2015-09 → S19 剑荡 2024-11：19 个完整赛季 ≈ {per19:.1f} 个月/季（端点平均）")
S["season_months"] = per19
def p_adv(p, n=9, k=5): return sum(comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k, n + 1))
adv = {p: p_adv(p) for p in (.35, .40, .45, .50, .55, .60, .65, .70)}
amp = (adv[.60] - adv[.40]) / .20
print("  剑荡初赛 9 局 5 胜 晋级概率：" + "  ".join(f"{100*p:.0f}%→{100*v:.1f}%" for p, v in adv.items()))
print(f"  胜率 40%→60%（差 20 个百分点）晋级差 {100*(adv[.60]-adv[.40]):.1f} 个百分点，放大 {amp:.2f}×；月下第一人 9 局 2 胜：胜率 30% 过线 {100*p_adv(.30, 9, 2):.0f}%")
S["jiandang_adv"] = {f"{100*p:.0f}": v for p, v in adv.items()}; S["jiandang_amp"] = amp

fig, axs = plt.subplots(1, 2, figsize=(12, 4.3))
ax = axs[0]
ax.barh(RANKS, tot, color=[BLUE] * 5 + [VIOLET, GOLD])
for i, n in enumerate(tot): ax.text(n + 60, i, f"{n}", va="center", color=INK, fontsize=9)
ax.invert_yaxis(); ax.set_xlabel("四大区合计人数（2018-03，榜内可见）"); ax.set_title(f"段位分布：造极是瓶颈，化境人数是造极的 {tot[-1]/tot[-2]:.1f}×", color=INK, fontsize=11.5); style(ax)
ax = axs[1]
ps = np.linspace(.2, .8, 61)
ax.plot(100 * ps, [100 * p_adv(p) for p in ps], color=GOLD, lw=2.2, label="初赛 9 局 5 胜")
ax.plot(100 * ps, [100 * p_adv(p, 9, 2) for p in ps], color=BLUE, lw=1.6, ls="--", label="9 局 2 胜（月下第一人）")
ax.plot(100 * ps, 100 * ps, color=MUTED, lw=1, ls=":", label="y = x")
ax.set_xlabel("真实胜率 %"); ax.set_ylabel("晋级概率 %"); ax.set_title(f"九局五胜：20 个百分点的胜率差 → {100*(adv[.60]-adv[.40]):.0f} 个百分点的晋级差", color=INK, fontsize=11.5)
ax.legend(frameon=False, fontsize=9); style(ax)
fig.tight_layout(); fig.savefig(os.path.join(OUT, "ty_ladder.png"), dpi=170); plt.close(fig)

# =====================================================================
# 5. 设计动作：自定义模板下韧劲的阶梯定价（等 ΔM 定价，示意）
# =====================================================================
print("\n## 5 阶梯定价（设计动作）：让每能力点买到的期望伤害变化恒定")
opp = {.30: .3, .40: .4, .50: .3}
def dM_res(t): return sum(w * (exp_mult(c_, cd0, t) - exp_mult(c_, cd0, t + d)) for c_, w in opp.items())
tiers = [(0, .15), (.15, .30), (.30, .45), (.45, .60)]
base_val = dM_res(0.0); price = {}
print("  会心：每 +1% 的 ΔM = max(CD−0.8t, 0.5)，与自身会心无关 → 对手韧劲给定时线性定价即可")
print("  韧劲（对手会心 30/40/50% 各占 0.3/0.4/0.3，示意）：")
for lo, hi in tiers:
    v = dM_res((lo + hi) / 2); rel = v / base_val
    key = f"{100*lo:.0f}-{100*hi:.0f}"; idx = rel   # 等 ΔM 定价：价格 ∝ 边际收益
    price[key] = dict(marginal=v, price_index=idx)
    print(f"    韧劲 {100*lo:2.0f}–{100*hi:2.0f}%: 每 1% 边际 ΔM {v:.4f} → 等 ΔM 价格指数 {idx:.2f}（官方阶梯为递增，目标不同：压极端堆叠）")
S["tier_pricing"] = price
json.dump(S, open(os.path.join(HERE, "data/ty_attr_summary.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=float)
print("\ncharts →", OUT)
