# -*- coding: utf-8 -*-
"""三消新章「十关关卡包」· 设计验证脚本（v1.0）

思路：棋盘 / 目标 / 障碍由策划手工设计（本文件 LEVELS），**步数不拍脑袋**——
对每关用 match3_sim 贪心机器人跑 N 局、取"完成步数"经验分布，反解出达到目标通关率所需的最小步数，
再报告该步数下的实际通关率、近失率（败局中估算只差 1–3 步的比例）。

用法：PYTHONUTF8=1 python m3_level_pack.py [--n 300] [--procs 16]
输出：data/m3_level_pack.json、charts/m3_level_pack_staircase.png、data/m3_level_pack_boards.md
"""
import argparse, json, os, sys, time
from multiprocessing import Pool
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from match3_sim import simulate  # noqa: E402

CAP = 45  # 跑超额步数，任意步数上限下的通关率都从完成步分布读出


def full(v=True): return np.full((9, 9), v, dtype=bool)


def rect(r0, r1, c0, c1):
    m = np.zeros((9, 9), dtype=bool); m[r0:r1, c0:c1] = True; return m


# ---------------------------------------------------------------------------
# 十关设计。节奏：教学 → 巩固 → 新元素 → 卡点 → 喘息 → 组合 → 组合 → 卡点 → 喘息 → 章末难关
# 每关：name / intent / target_win（设计通关率）/ colors / mask / goal / frosting
# ---------------------------------------------------------------------------
def build_levels():
    L = []
    # L1 教学：中央 5×6 单层果冻，五色，无障碍
    j = np.zeros((9, 9), dtype=int); j[2:7, 2:8] = 1
    L.append(dict(name="L1 灯塔初醒", intent="教学关：只教一件事——消除果冻上的糖果。果冻集中在视线中央，五色，任何消除都有反馈。",
                  target_win=0.90, colors=5, mask=full().tolist(), goal={"type": "jelly", "layout": j.tolist()}))
    # L2 巩固：果冻扩到 6×6，六色
    j = np.zeros((9, 9), dtype=int); j[2:8, 2:8] = 1
    L.append(dict(name="L2 潮间带", intent="巩固关：同一机制放大面积，切到六色，让玩家第一次感到'步数是有限的'。",
                  target_win=0.80, colors=6, mask=full().tolist(), goal={"type": "jelly", "layout": j.tolist()}))
    # L3 新元素：糖霜出场（单层），围一圈，果冻在圈内
    j = np.zeros((9, 9), dtype=int); j[2:7, 2:7] = 1
    f = np.zeros((9, 9), dtype=int); f[1, 1:8] = 1; f[7, 1:8] = 1; f[2:7, 1] = 1; f[2:7, 7] = 1
    L.append(dict(name="L3 冻住的礁石", intent="新元素关：糖霜单独出场，只有一层、只围一圈，目标（圈内 25 格果冻）小到不会分散注意力。学会'挨着消就能化冰'。",
                  target_win=0.75, colors=5, mask=full().tolist(), goal={"type": "jelly", "layout": j.tolist()}, frosting=f.tolist()))
    # L4 章中卡点：左右侧带果冻（外列双层）+ 单层糖霜竖墙
    j = np.zeros((9, 9), dtype=int); j[3:6, 0:3] = 1; j[3:6, 6:9] = 1; j[3:6, 0] = 2; j[3:6, 8] = 2
    f = np.zeros((9, 9), dtype=int); f[2:7, 4] = 1
    L.append(dict(name="L4 双潮汇", intent="章中卡点：果冻分成左右两条侧带（最外一列双层），中间一道 5 格竖向糖霜墙把棋盘切成左右两半，逼玩家在两个战场间分配步数。设计通关率 35%。",
                  target_win=0.35, colors=6, mask=full().tolist(), goal={"type": "jelly", "layout": j.tolist()}, frosting=f.tolist()))
    # L5 喘息：颜色收集
    L.append(dict(name="L5 拾贝", intent="喘息关：换目标类型（收集 60 个蓝色），无障碍，五色。卡点之后必须给一关'随便玩玩都能过'。",
                  target_win=0.85, colors=5, mask=full().tolist(), goal={"type": "order_color", "color": 0, "amount": 60}))
    # L6 组合：配料 + 漏斗形掩码
    m = full(); m[0:3, 0] = m[0:3, 8] = False; m[0:5, 1] = m[0:5, 7] = False
    L.append(dict(name="L6 漏斗湾", intent="组合关：第二种目标类型（3 个配料落底）叠加第一次出现的异形棋盘（漏斗），教'配料只会沿着列往下走'。",
                  target_win=0.65, colors=5, mask=m.tolist(), goal={"type": "ingredients", "amount": 3, "concurrent": 2}))
    # L7 组合：果冻 + 散点糖霜
    j = np.zeros((9, 9), dtype=int); j[1:8, 1:8] = 1
    f = np.zeros((9, 9), dtype=int)
    for r, c in [(2, 2), (2, 6), (4, 4), (6, 2), (6, 6), (1, 4), (7, 4), (4, 1), (4, 7), (3, 3)]: f[r, c] = 1
    j[f > 0] = 0
    L.append(dict(name="L7 冰点星图", intent="组合关：大面积单层果冻 + 10 个散点糖霜，糖霜下面没有果冻，但它们卡住下落路径，考验'先化哪块冰'的顺序判断。",
                  target_win=0.55, colors=6, mask=full().tolist(), goal={"type": "jelly", "layout": j.tolist()}, frosting=f.tolist()))
    # L8 第二卡点：H 形棋盘 + 两柱中段果冻（底行双层）+ 桥心一格糖霜
    m = np.zeros((9, 9), dtype=bool); m[:, 0:4] = True; m[:, 5:9] = True; m[3:6, 4] = True
    j = np.zeros((9, 9), dtype=int); j[3:6, 0:4] = 1; j[3:6, 5:9] = 1; j[5, 0:4] = 2; j[5, 5:9] = 2
    f = np.zeros((9, 9), dtype=int); f[4, 4] = 1
    L.append(dict(name="L8 断桥", intent="第二卡点：H 形棋盘，两根四宽柱子中段 3 行铺果冻（最下一行双层），中间横梁只有一格宽、中点一块糖霜——两侧几乎独立，条纹糖跨区是唯一捷径。设计通关率 30%，是本章付费点。",
                  target_win=0.30, colors=6, mask=m.tolist(), goal={"type": "jelly", "layout": j.tolist()}, frosting=f.tolist()))
    # L9 喘息：颜色收集
    L.append(dict(name="L9 退潮", intent="喘息关：再给一关低压力颜色收集（45 个），五色。卡点后的第二次减压，也是章末难关前的蓄力。",
                  target_win=0.85, colors=5, mask=full().tolist(), goal={"type": "order_color", "color": 1, "amount": 45}))
    # L10 章末难关：四个 4×4 小区各 3×3 果冻（区心双层）+ 单层糖霜十字
    j = np.zeros((9, 9), dtype=int)
    for r0, c0 in [(0, 0), (0, 5), (5, 0), (5, 5)]: j[r0 + 1:r0 + 4, c0 + 1:c0 + 4] = 1; j[r0 + 2, c0 + 2] = 2
    f = np.zeros((9, 9), dtype=int); f[4, 0:9] = 1; f[0:9, 4] = 1
    j[f > 0] = 0
    L.append(dict(name="L10 灯塔之夜", intent="章末难关：四个 4×4 小区各铺 3×3 果冻、区中心一格双层，一个单层糖霜十字把棋盘切成四块——每个小区只有 16 格，连锁几乎不可能，必须靠特效跨区。设计通关率 20%。",
                  target_win=0.20, colors=6, mask=full().tolist(), goal={"type": "jelly", "layout": j.tolist()}, frosting=f.tolist()))
    return L


def cfg_of(lv):
    c = {"colors": lv["colors"], "moves": CAP, "mask": lv["mask"], "goal": lv["goal"]}
    if lv.get("frosting"): c["blockers"] = {"frosting": lv["frosting"]}
    return c


def run_one(args):
    idx, lv, n, seed = args
    t0 = time.perf_counter()
    r = simulate(cfg_of(lv), n, seed, policy="greedy", max_moves=CAP)
    comp = [c for c in r["completion_moves"]]
    rr = simulate(cfg_of(lv), max(100, n // 3), seed + 1000, policy="random", max_moves=CAP)
    comp_r = [c for c in rr["completion_moves"]]
    return idx, comp, r["trajectories"], time.perf_counter() - t0, comp_r


def near_miss(trajs, moves):
    """败局中，用最后 5 步的平均推进量估算还差几步，差 1–3 步记近失。"""
    nm = tot = 0
    for t in trajs:
        if len(t) <= moves and t[-1] == 0: continue
        rem = t[moves] if len(t) > moves else t[-1]
        if rem == 0: continue
        tot += 1
        window = t[max(0, moves - 5):moves + 1]
        rate = (window[0] - window[-1]) / max(1, len(window) - 1)
        if rate > 0 and 1 <= rem / rate <= 3: nm += 1
    return nm / tot if tot else 0.0, tot


def board_ascii(lv):
    mask = np.array(lv["mask"]); g = lv["goal"]
    jelly = np.array(g["layout"]) if "layout" in g else np.zeros((9, 9), dtype=int)
    fr = np.array(lv.get("frosting") or np.zeros((9, 9), dtype=int))
    rows = []
    for r in range(9):
        s = ""
        for c in range(9):
            if not mask[r, c]: s += "  "
            elif fr[r, c] > 0: s += f"#{fr[r, c]}"
            elif jelly[r, c] == 2: s += "▓▓"
            elif jelly[r, c] == 1: s += "░░"
            else: s += "··"
        rows.append(s)
    return "\n".join(rows)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--n", type=int, default=300); ap.add_argument("--procs", type=int, default=16); ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    levels = build_levels()
    tasks = [(i, lv, a.n, a.seed + i) for i, lv in enumerate(levels)]
    t0 = time.perf_counter()
    with Pool(a.procs) as p: results = p.map(run_one, tasks)
    out = []
    for idx, comp, trajs, dt, comp_r in sorted(results):
        lv = levels[idx]
        done = np.array([c for c in comp if c is not None])
        curve = {m: len([c for c in comp if c is not None and c <= m]) / len(comp) for m in range(5, CAP + 1)}
        target = lv["target_win"]
        moves = next((m for m in range(5, CAP + 1) if curve[m] >= target), None)
        if moves is None: moves = CAP
        nm, nfail = near_miss(trajs, moves)
        m50 = next((m for m in range(5, CAP + 1) if curve[m] >= 0.5), None)
        curve_r = {m: len([c for c in comp_r if c is not None and c <= m]) / len(comp_r) for m in range(5, CAP + 1)}
        se = (curve[moves] * (1 - curve[moves]) / len(comp)) ** 0.5
        g = lv["goal"]; amount = int(np.array(g["layout"]).sum()) if "layout" in g else g["amount"]
        rec = dict(idx=idx + 1, name=lv["name"], intent=lv["intent"], colors=lv["colors"], goal_type=g["type"], goal_amount=amount,
                   frosting_cells=int((np.array(lv.get("frosting") or 0) > 0).sum()), frosting_layers=int(np.array(lv.get("frosting") or 0).sum()),
                   playable_cells=int(np.array(lv["mask"]).sum()), target_win=target, moves=moves, win_at_moves=curve[moves],
                   win_minus2=curve.get(moves - 2, 0.0), win_plus5=curve.get(min(CAP, moves + 5), 1.0), m50=m50, slack=(moves / m50 if m50 else None),
                   demand_rate=amount / moves, near_miss=nm, n_fail=nfail, n=a.n, elapsed_s=dt, curve=curve, board=board_ascii(lv), random_win=curve_r[moves], random_win_plus5=curve_r.get(min(CAP, moves + 5), 1.0), n_random=len(comp_r), se=se, curve_random=curve_r)
        out.append(rec)
        print(f"{rec['name']:12s} 目标{target:.2f} → 步数 {moves:2d}（实际 {curve[moves]:.2f}，−2 步 {rec['win_minus2']:.2f}，+5 步 {rec['win_plus5']:.2f}）"
              f" ±{1.96*se:.2f} M50={m50} slack={rec['slack'] and round(rec['slack'],2)} 随机策略 {curve_r[moves]:.2f}(+5步 {rec['random_win_plus5']:.2f}) 需求速率 {rec['demand_rate']:.2f}/步 近失 {nm:.2f}（败局 {nfail}） {dt:.0f}s", flush=True)
    print(f"总耗时 {time.perf_counter()-t0:.0f}s")
    json.dump(dict(n=a.n, seed=a.seed, cap=CAP, levels=out), open(os.path.join(HERE, "data/m3_level_pack.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    with open(os.path.join(HERE, "data/m3_level_pack_boards.md"), "w", encoding="utf-8") as f:
        for rec in out:
            f.write(f"### {rec['name']}\n\n```\n{rec['board']}\n```\n\n")
    # 阶梯图
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    GOLD, BLUE, VIOLET, ICE = "#b57f22", "#2f96cc", "#a259e8", "#9fd8f0"; SURFACE, INK, MUTED = "#100e26", "#cdc9e0", "#a09ac0"
    plt.rcParams.update({"font.family": ["Microsoft YaHei", "SimHei", "sans-serif"], "axes.unicode_minus": False, "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
                         "savefig.facecolor": SURFACE, "text.color": INK, "axes.labelcolor": MUTED, "xtick.color": MUTED, "ytick.color": MUTED, "axes.edgecolor": (1, 1, 1, .12), "font.size": 11})
    fig, ax = plt.subplots(figsize=(10, 4.4))
    xs = [r["idx"] for r in out]
    ax.bar(xs, [r["target_win"] for r in out], color=BLUE, alpha=.35, width=.6, label="设计通关率（目标）")
    ax.plot(xs, [r["win_at_moves"] for r in out], color=GOLD, marker="o", lw=2.2, label="模拟通关率（反解步数下）")
    ax.plot(xs, [r["win_minus2"] for r in out], color=VIOLET, marker="v", lw=1.2, ls="--", label="少给 2 步")
    ax.plot(xs, [r["win_plus5"] for r in out], color=ICE, marker="^", lw=1.2, ls="--", label="多给 5 步（≈一次加步付费）")
    ax.plot(xs, [r["random_win"] for r in out], color="#e07a7a", marker="x", lw=1.2, ls=":", label="随机策略（'随便玩玩'下限）")
    for r in out: ax.annotate(f"{r['moves']}步", (r["idx"], r["win_at_moves"]), textcoords="offset points", xytext=(0, 8), ha="center", fontsize=9, color=INK)
    ax.set_xticks(xs); ax.set_xticklabels([r["name"].split(" ")[0] for r in out]); ax.set_ylim(0, 1.05); ax.set_ylabel("通关率")
    ax.set_title("十关关卡包：通关率阶梯（卡点 L4 / L8 / L10 显著低于相邻关）", color=INK, fontsize=12)
    ax.grid(True, color=(157/255, 143/255, 240/255, .16)); ax.set_axisbelow(True)
    for s in ("top", "right"): ax.spines[s].set_visible(False)
    ax.legend(frameon=False, ncol=3, fontsize=8.5, loc="upper right")
    fig.tight_layout(); fig.savefig(os.path.join(HERE, "charts/m3_level_pack_staircase.png"), dpi=170)


if __name__ == "__main__":
    main()
