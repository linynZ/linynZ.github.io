# -*- coding: utf-8 -*-
"""校准结果的补充统计（审核后加）：模拟通关率 vs 目标量÷步数 的秩相关、控制该量后的偏相关、Spearman 自助置信区间。
读 data/m3_calibration.json，不重跑模拟。用法：PYTHONUTF8=1 python m3_calibration_stats.py
"""
import json, os
import numpy as np
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
d = json.load(open(os.path.join(HERE, "data/m3_calibration.json"), encoding="utf-8"))
levels = d["levels"]
for l in levels: l["gk"] = l["group"] + ("/" + l["jelly_mode"] if l.get("jelly_mode") else "")
groups = sorted(set(l["gk"] for l in levels))
key = "gk"
rng = np.random.default_rng(0)


def partial_spearman(x, y, z):
    rx, ry, rz = stats.rankdata(x), stats.rankdata(y), stats.rankdata(z)
    def resid(a, b):
        b1 = np.polyfit(b, a, 1); return a - np.polyval(b1, b)
    return stats.spearmanr(resid(rx, rz), resid(ry, rz)).correlation


out = {}
for g in groups:
    L = [l for l in levels if l[key] == g]
    win = np.array([l["win_rate"] for l in L]); rank = np.array([l["rank"] for l in L])
    gpm = np.array([sum(int(x) for x in str(l["goal_nums"]).split("|") if x) / l["moves"] for l in L])
    rho_wr = stats.spearmanr(win, rank).correlation
    rho_wg = stats.spearmanr(win, gpm).correlation
    rho_gr = stats.spearmanr(gpm, rank).correlation
    part = partial_spearman(win, rank, gpm)
    boots = []
    for _ in range(2000):
        idx = rng.integers(0, len(L), len(L)); boots.append(stats.spearmanr(win[idx], rank[idx]).correlation)
    lo, hi = np.nanpercentile(boots, [2.5, 97.5])
    out[g] = dict(n=len(L), rho_win_rank=rho_wr, rho_win_goalpermove=rho_wg, rho_goalpermove_rank=rho_gr, partial_win_rank_given_gpm=part, ci95=[lo, hi])
    print(f"[{g}] n={len(L)}  ρ(win,rank)={rho_wr:.3f} 95%CI[{lo:.2f},{hi:.2f}]  ρ(win,goal/move)={rho_wg:.3f}  ρ(goal/move,rank)={rho_gr:.3f}  偏相关 ρ(win,rank|goal/move)={part:.3f}")
json.dump(out, open(os.path.join(HERE, "data/m3_calibration_stats.json"), "w", encoding="utf-8"), indent=1)
