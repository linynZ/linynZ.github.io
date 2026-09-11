# -*- coding: utf-8 -*-
"""三消关卡「步数预算与难度曲线」拆解案 · 计算脚本（v1.0）

数据：data/cc_levels.csv（Candy Crush Saga 1–1505 关，fandom wiki 经 Wayback 镜像抓取，cc_scrape.py 可复现）
输出：终端表格 + charts/m3_*.png + data/m3_budget_summary.json
用法：PYTHONUTF8=1 python match3_level_budget.py
"""
import csv, json, os, collections, statistics as st
import numpy as np
from scipy import stats
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
GOLD, BLUE, VIOLET, ICE = "#b57f22", "#2f96cc", "#a259e8", "#9fd8f0"
SURFACE, INK, MUTED = "#100e26", "#cdc9e0", "#a09ac0"
GRID = (157/255, 143/255, 240/255, 0.16)
plt.rcParams.update({"font.family": ["Microsoft YaHei", "SimHei", "sans-serif"], "axes.unicode_minus": False,
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE, "text.color": INK,
    "axes.labelcolor": MUTED, "xtick.color": MUTED, "ytick.color": MUTED, "axes.edgecolor": (1, 1, 1, 0.12), "font.size": 11})
OUT = os.path.join(HERE, "charts"); os.makedirs(OUT, exist_ok=True)
DIFF_ZH = ["极易", "易", "偏易", "中", "偏难", "难", "很难", "极难", "近乎不可能"]


def style(ax):
    ax.grid(True, color=GRID, linewidth=0.8); ax.set_axisbelow(True)
    for s in ("top", "right"): ax.spines[s].set_visible(False)


rows = list(csv.DictReader(open(os.path.join(HERE, "data/cc_levels.csv"), encoding="utf-8")))
for r in rows:
    r["level"] = int(r["level"]); r["moves"] = int(r["moves"])
    r["rank"] = int(r["difficulty_rank"]) if r["difficulty_rank"] else None
    icons = [i for i in r["goal_icons"].split("|") if i]
    nums = [int(n.replace(",", "")) for n in r["goal_nums"].split("|") if n]
    r["goals"] = list(zip(icons, nums))
rated = [r for r in rows if r["rank"]]
summary = {}

# ---------- 1. 章内难度锯齿（每 15 关一章，从 21 关起章节整齐） ----------
pos = collections.defaultdict(list)
for r in rated:
    if r["level"] >= 21: pos[(r["level"] - 21) % 15 + 1].append(r["rank"])
pos_mean = {p: st.mean(v) for p, v in pos.items()}
pos_hard = {p: sum(1 for x in v if x >= 6) / len(v) for p, v in pos.items()}
print("## 1 章内位置 → 难度均值 / 难关占比(评级≥难)")
for p in range(1, 16):
    print(f"  第{p:2d}关  均值 {pos_mean[p]:.2f}  难关占比 {pos_hard[p]*100:4.0f}%  n={len(pos[p])}")
peaks = [5, 10, 15]; others = [p for p in range(1, 16) if p not in peaks]
peak_vals = [x for p in peaks for x in pos[p]]; other_vals = [x for p in others for x in pos[p]]
u = stats.mannwhitneyu(peak_vals, other_vals, alternative="greater")
print(f"  5/10/15 位均值 {st.mean(peak_vals):.2f} vs 其他位 {st.mean(other_vals):.2f}，Mann-Whitney p={u.pvalue:.2e}")
drop_after_peak = st.mean([pos_mean[p] - pos_mean[p + 1] for p in (5, 10)])
print(f"  峰后一关平均回落 {drop_after_peak:.2f} 档（第 5→6、10→11）")
summary["episode_position"] = {"mean": pos_mean, "hard_share": pos_hard, "peak_mean": st.mean(peak_vals),
                               "other_mean": st.mean(other_vals), "mw_p": u.pvalue, "drop_after_peak": drop_after_peak}

fig, ax = plt.subplots(figsize=(9, 4.2))
xs = list(range(1, 16)); ys = [pos_mean[p] for p in xs]
ax.bar(xs, [pos_hard[p] * 9 for p in xs], color=BLUE, alpha=.28, width=.7, label="难关占比（评级≥难，右轴）")
ax.plot(xs, ys, color=GOLD, lw=2.2, marker="o", ms=6, zorder=3, label="难度评级均值（左轴）")
for p in peaks: ax.axvline(p, color=VIOLET, alpha=.35, ls="--")
ax.set_xticks(xs); ax.set_xlabel("章内第几关（每章 15 关，21–1505 关共 99 章）")
ax.set_ylabel("社区难度评级均值（1 极易 … 9 近乎不可能）")
ax2 = ax.twinx(); ax2.set_ylim(0, 1); ax2.set_ylabel("难关占比"); ax2.tick_params(colors=MUTED); ax2.spines["top"].set_visible(False)
ax.set_ylim(0, 9); style(ax)
ax.set_title("章内难度锯齿：第 5 / 10 / 15 关是三个峰（均值层面；峰后一关在约 2/3 的章回落）", color=INK, fontsize=12)
ax.legend(loc="upper left", frameon=False)
fig.tight_layout(); fig.savefig(os.path.join(OUT, "m3_episode_sawtooth.png"), dpi=170); plt.close(fig)

# ---------- 2. 隐含需求速率（果冻层/步、配料/步）随关卡序号漂移 ----------
def jelly_layers(r):
    tot = 0
    for ic, n in r["goals"]:
        if "Single jelly" in ic: tot += n
        elif "Double jelly" in ic: tot += 2 * n
        else: return None
    return tot or None


jelly = [(r, jelly_layers(r)) for r in rows if r["type"] == "Jelly"]
jelly = [(r, j) for r, j in jelly if j]
for r, j in jelly: r["demand"] = j / r["moves"]
ingr = [r for r in rows if r["type"] == "Ingredients" and len(r["goals"]) == 1]
for r in ingr: r["demand"] = r["goals"][0][1] / r["moves"]
print("\n## 2 隐含需求速率（目标量 ÷ 步数）按 100 关分桶")
buck = collections.defaultdict(lambda: {"jelly": [], "ingr": [], "moves": []})
for r, j in jelly: buck[(r["level"] - 1) // 100]["jelly"].append(r["demand"])
for r in ingr: buck[(r["level"] - 1) // 100]["ingr"].append(r["demand"])
for r in rows: buck[(r["level"] - 1) // 100]["moves"].append(r["moves"])
drift = []
for b in sorted(buck):
    jm = st.median(buck[b]["jelly"]) if buck[b]["jelly"] else float("nan")
    im = st.median(buck[b]["ingr"]) if buck[b]["ingr"] else float("nan")
    mm = st.median(buck[b]["moves"])
    drift.append((b * 100 + 1, (b + 1) * 100, jm, im, mm))
    print(f"  {b*100+1:4d}-{(b+1)*100:4d}  果冻层/步 {jm:5.2f}  配料/步 {im:4.2f}  步数中位 {mm:.0f}")
summary["drift"] = drift
jr = [(r["demand"], r["rank"], r["moves"]) for r, j in jelly if r["rank"]]
rho_d = stats.spearmanr([x[0] for x in jr], [x[1] for x in jr]); rho_m = stats.spearmanr([x[2] for x in jr], [x[1] for x in jr])
ir = [(r["demand"], r["rank"], r["moves"]) for r in ingr if r["rank"]]
rho_di = stats.spearmanr([x[0] for x in ir], [x[1] for x in ir]); rho_mi = stats.spearmanr([x[2] for x in ir], [x[1] for x in ir])
print(f"  果冻关 n={len(jr)}：需求速率 vs 评级 ρ={rho_d.correlation:.3f}(p={rho_d.pvalue:.1e})；步数 vs 评级 ρ={rho_m.correlation:.3f}(p={rho_m.pvalue:.1e})")
print(f"  配料关 n={len(ir)}：需求速率 vs 评级 ρ={rho_di.correlation:.3f}(p={rho_di.pvalue:.1e})；步数 vs 评级 ρ={rho_mi.correlation:.3f}(p={rho_mi.pvalue:.1e})")
summary["rank_corr"] = {"jelly_demand": rho_d.correlation, "jelly_moves": rho_m.correlation, "ingr_demand": rho_di.correlation,
                        "ingr_moves": rho_mi.correlation, "n_jelly": len(jr), "n_ingr": len(ir)}
print("  果冻关按评级档：需求速率中位数 / 步数中位数")
by_rank = collections.defaultdict(list)
for d, k, m in jr: by_rank[k].append((d, m))
rank_table = []
for k in range(1, 10):
    v = by_rank.get(k, [])
    if v:
        rank_table.append((k, DIFF_ZH[k - 1], len(v), st.median([x[0] for x in v]), st.median([x[1] for x in v])))
        print(f"    {k} {DIFF_ZH[k-1]:6s} n={len(v):3d}  {st.median([x[0] for x in v]):.2f} 层/步  步数 {st.median([x[1] for x in v]):.0f}")
summary["jelly_by_rank"] = rank_table

fig, axs = plt.subplots(1, 2, figsize=(12, 4.4))
ax = axs[0]
lv = [r["level"] for r, j in jelly]; dm = [r["demand"] for r, j in jelly]; rk = [r["rank"] or 0 for r, j in jelly]
sc = ax.scatter(lv, dm, c=rk, cmap="plasma", s=14, alpha=.75, vmin=1, vmax=9)
order = np.argsort(lv); lv_s = np.array(lv)[order]; dm_s = np.array(dm)[order]
w = 41; med = [np.median(dm_s[max(0, i - w // 2):i + w // 2 + 1]) for i in range(len(dm_s))]
ax.plot(lv_s, med, color=ICE, lw=2, label="滚动中位数（41 关窗）")
ax.set_xlabel("关卡序号"); ax.set_ylabel("果冻层数 ÷ 步数（每步须清的果冻层）")
ax.set_title("果冻关隐含需求速率随关卡序号漂移", color=INK, fontsize=12)
cb = fig.colorbar(sc, ax=ax, pad=.01); cb.set_label("社区难度评级", color=MUTED)
cb.ax.yaxis.set_tick_params(color=MUTED); plt.setp(cb.ax.get_yticklabels(), color=MUTED)
ax.legend(frameon=False, loc="upper left"); style(ax)
ax = axs[1]
ks = [t[0] for t in rank_table]
ax.plot(ks, [t[3] for t in rank_table], color=GOLD, marker="o", lw=2.2, label="需求速率中位数（层/步）")
ax.set_xticks(ks); ax.set_xticklabels([DIFF_ZH[k - 1] for k in ks], rotation=30, fontsize=9)
ax.set_ylabel("果冻层/步")
ax.set_title(f"需求速率 vs 评级 Spearman ρ={rho_d.correlation:.2f}；步数 vs 评级 ρ={rho_m.correlation:.2f}", color=INK, fontsize=11.5)
ax3 = ax.twinx(); ax3.plot(ks, [t[4] for t in rank_table], color=BLUE, marker="s", lw=1.6, ls="--", label="步数中位数（右轴）")
ax3.set_ylabel("步数"); ax3.tick_params(colors=MUTED); ax3.spines["top"].set_visible(False)
h1, l1 = ax.get_legend_handles_labels(); h2, l2 = ax3.get_legend_handles_labels()
ax.legend(h1 + h2, l1 + l2, frameon=False, loc="upper left"); style(ax)
fig.tight_layout(); fig.savefig(os.path.join(OUT, "m3_demand_rate.png"), dpi=170); plt.close(fig)

# ---------- 3. 卡点间隔与峰后回落 ----------
hard_lv = [r["level"] for r in rated if r["rank"] >= 7 and r["level"] >= 21]
gaps = np.diff(hard_lv)
n_rated21 = sum(1 for r in rated if r["level"] >= 21)
print(f"\n## 3 卡点（评级≥很难）共 {len(hard_lv)} 个 / {n_rated21} 关；间隔中位 {np.median(gaps):.0f} 关，均值 {gaps.mean():.2f}，P25/P75 {np.percentile(gaps,25):.0f}/{np.percentile(gaps,75):.0f}")
byl = {r["level"]: r for r in rated}
after = [byl[l + 1]["rank"] for l in hard_lv if l + 1 in byl]
before = [byl[l - 1]["rank"] for l in hard_lv if l - 1 in byl]
overall = st.mean([r["rank"] for r in rated])
print(f"  卡点前一关均值 {st.mean(before):.2f}，卡点后一关均值 {st.mean(after):.2f}（全体均值 {overall:.2f}）")
run = collections.Counter(); lv_set = set(hard_lv)
for l in hard_lv:
    if l - 1 in lv_set: continue
    n = 1
    while l + n in lv_set: n += 1
    run[n] += 1
print(f"  连续卡点段长度分布 {dict(sorted(run.items()))}")
summary["walls"] = {"count": len(hard_lv), "n_rated": n_rated21, "gap_median": float(np.median(gaps)), "gap_mean": float(gaps.mean()),
                    "gap_p25": float(np.percentile(gaps, 25)), "gap_p75": float(np.percentile(gaps, 75)),
                    "before_mean": st.mean(before), "after_mean": st.mean(after), "overall_mean": overall, "runs": dict(run)}
fig, ax = plt.subplots(figsize=(9, 3.8))
ax.hist(gaps, bins=range(1, 22), color=VIOLET, alpha=.85, edgecolor=SURFACE)
ax.axvline(np.median(gaps), color=GOLD, lw=2, ls="--", label=f"中位间隔 {np.median(gaps):.0f} 关")
ax.set_xlabel("相邻两个卡点（评级≥很难）之间的关数"); ax.set_ylabel("次数")
ax.set_title("卡点间隔分布", color=INK, fontsize=12)
ax.legend(frameon=False); style(ax); fig.tight_layout(); fig.savefig(os.path.join(OUT, "m3_wall_gaps.png"), dpi=170); plt.close(fig)

# ---------- 4. 付费墙密度：每 100 关的难关数 ----------
print("\n## 4 每 100 关：评级≥很难 / ≥极难 / 近乎不可能 的关数")
dens = []
for b in range(0, 1500, 100):
    seg = [r for r in rated if b < r["level"] <= b + 100]
    dens.append((b + 1, b + 100, sum(1 for r in seg if r["rank"] >= 7), sum(1 for r in seg if r["rank"] >= 8), sum(1 for r in seg if r["rank"] >= 9)))
    print(f"  {b+1:4d}-{b+100:4d}  ≥很难 {dens[-1][2]:2d}  ≥极难 {dens[-1][3]:2d}  近乎不可能 {dens[-1][4]:2d}")
summary["wall_density"] = dens
fig, ax = plt.subplots(figsize=(9, 3.8))
x = [d[0] for d in dens]
ax.bar(x, [d[2] for d in dens], width=80, color=BLUE, alpha=.55, label="≥很难")
ax.bar(x, [d[3] for d in dens], width=80, color=GOLD, alpha=.8, label="≥极难")
ax.bar(x, [d[4] for d in dens], width=80, color=VIOLET, label="近乎不可能")
ax.set_xlabel("关卡区间起点"); ax.set_ylabel("每 100 关的关数"); ax.set_title("难关密度随关卡区间的变化", color=INK, fontsize=12)
ax.legend(frameon=False); style(ax); fig.tight_layout(); fig.savefig(os.path.join(OUT, "m3_wall_density.png"), dpi=170); plt.close(fig)

# ---------- 5. 类型占比与混合关 ----------
tc = collections.Counter(r["type"] for r in rows); print("\n## 5 类型占比", dict(tc))
mix_rank = [r["rank"] for r in rated if r["type"] == "Mixed"]; nonmix = [r["rank"] for r in rated if r["type"] != "Mixed"]
print(f"  混合关均值 {st.mean(mix_rank):.2f} vs 单目标关 {st.mean(nonmix):.2f}")
summary["type_share"] = dict(tc); summary["mixed_vs_single"] = {"mixed": st.mean(mix_rank), "single": st.mean(nonmix)}
json.dump(summary, open(os.path.join(HERE, "data/m3_budget_summary.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=float)
print("\ncharts →", OUT)

# ---------- 6. 新鲜感节奏：新元素（障碍/机制）引入间隔 ----------
import re as _re
from novelty_rules import is_intro
intro_lv=sorted(r["level"] for r in rows if is_intro(r["remarks"]))
ig=np.diff(intro_lv)
print(f"\n## 6 新元素引入点 {len(intro_lv)} 个；引入间隔中位 {np.median(ig):.0f} 关，均值 {ig.mean():.1f}")
seg=[]
for b in range(0,1500,300):
    k=[l for l in intro_lv if b<l<=b+300]
    seg.append((b+1,b+300,len(k)))
    print(f"  {b+1:4d}-{b+300:4d}  新元素 {len(k):2d} 个  平均每 {300/max(len(k),1):.0f} 关一个")
summary["novelty"]={"points":intro_lv,"remarks":{l:[r["remarks"] for r in rows if r["level"]==l][0][:100] for l in intro_lv},"gap_median":float(np.median(ig)),"gap_mean":float(ig.mean()),"per300":seg}
json.dump(summary, open(os.path.join(HERE, "data/m3_budget_summary.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=float)
fig, ax = plt.subplots(figsize=(9, 3.4))
ax.eventplot([intro_lv], colors=[GOLD], lineoffsets=[1], linelengths=[0.6], linewidths=1.6)
hl=[r["level"] for r in rated if r["rank"]>=8]
ax.eventplot([hl], colors=[VIOLET], lineoffsets=[0], linelengths=[0.6], linewidths=0.8, alpha=.6)
ax.set_yticks([0,1]); ax.set_yticklabels(["极难以上关","新元素引入关"]); ax.set_xlabel("关卡序号"); ax.set_xlim(0,1510)
ax.set_title("新元素引入点（上）与极难关（下）的分布：新鲜感集中在前 300 关，之后靠难度撑", color=INK, fontsize=11.5)
style(ax); ax.grid(False); fig.tight_layout(); fig.savefig(os.path.join(OUT, "m3_novelty_timeline.png"), dpi=170); plt.close(fig)

# ---------- 7. 稳健性：章起点错开 1–4 关后锯齿应消失 ----------
print("\n## 7 章起点错位检验（offset=0 应显著，其余不应）")
for off in range(0, 5):
    pos_o = collections.defaultdict(list)
    for r in rated:
        if r["level"] >= 21: pos_o[(r["level"] - 21 + off) % 15 + 1].append(r["rank"])
    pk = [x for p in (5, 10, 15) for x in pos_o[p]]; ot = [x for p in range(1, 16) if p not in (5, 10, 15) for x in pos_o[p]]
    print(f"  offset {off}: 5/10/15 均值 {st.mean(pk):.2f} vs 其他 {st.mean(ot):.2f}  p={stats.mannwhitneyu(pk, ot, alternative='greater').pvalue:.1e}")

# ---------- 8. 复核补充（审核后加） ----------
print("\n## 8a 卡点后一关：混杂拆解")
lv_set = set(hard_lv); after_is_wall = [l + 1 in lv_set for l in hard_lv if l + 1 in byl]
print(f"  卡点后一关本身仍是卡点的比例 {100*sum(after_is_wall)/len(after_is_wall):.1f}%")
seg_end_next = [byl[l + 1]["rank"] for l in hard_lv if l + 1 in byl and (l + 1) not in lv_set]
others_nonwall = [r["rank"] for r in rated if r["level"] >= 22 and r["level"] not in lv_set and (r["level"] - 1) not in lv_set]
print(f"  连续卡点段结束后第一关均值 {st.mean(seg_end_next):.2f}（n={len(seg_end_next)}，中位 {st.median(seg_end_next):.0f}）vs 其余非卡点关 {st.mean(others_nonwall):.2f}（n={len(others_nonwall)}）")
pos_wall_rate = {p: sum(1 for x in v if x >= 7) / len(v) for p, v in pos.items()}
exp_rate = st.mean([pos_wall_rate[((l + 1 - 21) % 15) + 1] for l in hard_lv if l + 1 in byl])
print(f"  卡点后一关的位置基线卡点率 {100*exp_rate:.1f}% vs 实际 {100*sum(after_is_wall)/len(after_is_wall):.1f}%")
summary["wall_relief"] = {"after_is_wall": sum(after_is_wall) / len(after_is_wall), "seg_end_next_mean": st.mean(seg_end_next), "n_seg_end": len(seg_end_next), "others_nonwall_mean": st.mean(others_nonwall), "pos_baseline_wall_rate": exp_rate}

print("\n## 8b 逐章检验：'峰后回落'在多少章成立")
byl_all = {r["level"]: r for r in rated}
def chap_ok(a, b):
    ok = tot = 0
    for c in range(99):
        la, lb = 21 + c * 15 + a - 1, 21 + c * 15 + b - 1
        if la in byl_all and lb in byl_all: tot += 1; ok += byl_all[lb]["rank"] < byl_all[la]["rank"]
    return ok / tot, tot
for a, b in ((5, 6), (10, 11), (15, 16)):
    r_, n_ = chap_ok(a, b); print(f"  第{a}关→第{b if b<=15 else '下章1'}关回落的章占比 {100*r_:.0f}%（n={n_}）")
top15 = tot15 = 0
for c in range(99):
    ranks = {p: byl_all[21 + c * 15 + p - 1]["rank"] for p in range(1, 16) if 21 + c * 15 + p - 1 in byl_all}
    if len(ranks) < 12: continue
    tot15 += 1; top15 += max(ranks, key=ranks.get) in (5, 10, 15)
print(f"  全章最高关落在 5/10/15 位的章占比 {100*top15/tot15:.0f}%（n={tot15}）")
summary["per_chapter"] = {"drop_5_6": chap_ok(5, 6)[0], "drop_10_11": chap_ok(10, 11)[0], "drop_15_next1": chap_ok(15, 16)[0], "max_at_peak": top15 / tot15}

print("\n## 8c 果冻关：wiki 记录格数 >81 的异常关及剔除后的区间中位")
anom = [r["level"] for r, j in jelly if sum(n for ic, n in r["goals"]) > 81]
print(f"  异常关 {len(anom)} 个：{anom}")
for b in (6, 7):
    vals = [r["demand"] for r, j in jelly if b * 100 < r["level"] <= (b + 1) * 100 and r["level"] not in anom]
    print(f"  {b*100+1}-{(b+1)*100} 剔除后果冻层/步中位 {st.median(vals):.2f}（原 {drift[b][2]:.2f}）")
summary["jelly_anomalies"] = anom

print("\n## 8d 官方跨档调难度：果冻层数中位 vs 步数中位（按评级档）")
by_rank_layers = collections.defaultdict(list)
for r, j in jelly:
    if r["rank"]: by_rank_layers[r["rank"]].append((j, r["moves"]))
rl = []
for k in range(1, 10):
    v = by_rank_layers.get(k, [])
    if v: rl.append((k, st.median([x[0] for x in v]), st.median([x[1] for x in v]))); print(f"  {k} {DIFF_ZH[k-1]:6s} 层数中位 {rl[-1][1]:5.0f}  步数中位 {rl[-1][2]:.0f}")
rho_layers = stats.spearmanr([j for r, j in jelly if r["rank"]], [r["rank"] for r, j in jelly if r["rank"]])
print(f"  层数 vs 评级 ρ={rho_layers.correlation:.3f}；步数 vs 评级 ρ={rho_m.correlation:.3f}")
summary["layers_vs_moves_by_rank"] = rl

print("\n## 8e 混合关 vs 单目标关，按 300 关分段")
mix_seg = []
for b in range(0, 1500, 300):
    m_ = [r["rank"] for r in rated if b < r["level"] <= b + 300 and r["type"] == "Mixed"]; s_ = [r["rank"] for r in rated if b < r["level"] <= b + 300 and r["type"] not in ("Mixed",)]
    if m_: mix_seg.append((b + 1, b + 300, len(m_), st.mean(m_), st.mean(s_))); print(f"  {b+1}-{b+300} 混合 {st.mean(m_):.2f}（n={len(m_)}） vs 单目标 {st.mean(s_):.2f}")
summary["mixed_by_segment"] = mix_seg
rho_lvl = stats.spearmanr([r["level"] for r in rated], [r["rank"] for r in rated])
print(f"\n  评级 vs 关卡序号 ρ={rho_lvl.correlation:.2f}")
summary["rank_vs_level"] = rho_lvl.correlation
json.dump(summary, open(os.path.join(HERE, "data/m3_budget_summary.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=float)
