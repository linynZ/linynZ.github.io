# -*- coding: utf-8 -*-
"""关卡包设计过程中的对照变体（把正文引用的"第一版"数字入库，可复现）。

变体：同样 32 层果冻（两侧各 4 列 × 3 行单层 + 底行双层）放在
  A) 满盘、底部三行            B) H 形棋盘、底部三行（第一版 L8）
  C) H 形棋盘、中段三行（定稿 L8） D) L4 前版：果冻 20 层放两个对角 + 5 格横墙
用法：PYTHONUTF8=1 python m3_level_pack_variants.py [--n 500] → data/output_m3_variants.txt / data/m3_variants.json
"""
import argparse, json, os, sys, time
from multiprocessing import Pool
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from match3_sim import simulate  # noqa: E402

CAP = 45


def full(): return np.full((9, 9), True)


def h_mask():
    m = np.zeros((9, 9), bool); m[:, 0:4] = True; m[:, 5:9] = True; m[3:6, 4] = True; return m


def jelly_rows(r0, r1, double_row):
    j = np.zeros((9, 9), int); j[r0:r1, 0:4] = 1; j[r0:r1, 5:9] = 1; j[double_row, 0:4] = 2; j[double_row, 5:9] = 2; return j


def variants():
    V = []
    V.append(("A 满盘·底部三行 32 层", dict(colors=6, moves=CAP, mask=full().tolist(), goal={"type": "jelly", "layout": jelly_rows(6, 9, 8).tolist()})))
    f = np.zeros((9, 9), int); f[4, 4] = 1
    V.append(("B H形·底部三行 32 层（第一版 L8）", dict(colors=6, moves=CAP, mask=h_mask().tolist(), goal={"type": "jelly", "layout": jelly_rows(6, 9, 8).tolist()}, blockers={"frosting": f.tolist()})))
    V.append(("C H形·中段三行 32 层（定稿 L8）", dict(colors=6, moves=CAP, mask=h_mask().tolist(), goal={"type": "jelly", "layout": jelly_rows(3, 6, 5).tolist()}, blockers={"frosting": f.tolist()})))
    j = np.zeros((9, 9), int); j[0:3, 0:3] = 1; j[6:9, 6:9] = 1; j[0, 0] = 2; j[8, 8] = 2
    f4 = np.zeros((9, 9), int); f4[4, 2:7] = 1
    V.append(("D L4 前版·对角 20 层 + 横墙", dict(colors=6, moves=CAP, mask=full().tolist(), goal={"type": "jelly", "layout": j.tolist()}, blockers={"frosting": f4.tolist()})))
    j2 = np.zeros((9, 9), int); j2[3:6, 0:3] = 1; j2[3:6, 6:9] = 1; j2[3:6, 0] = 2; j2[3:6, 8] = 2
    f5 = np.zeros((9, 9), int); f5[2:7, 4] = 1
    V.append(("E L4 定稿·侧带 24 层 + 竖墙", dict(colors=6, moves=CAP, mask=full().tolist(), goal={"type": "jelly", "layout": j2.tolist()}, blockers={"frosting": f5.tolist()})))
    return V


def run(args):
    name, cfg, n, seed = args
    t0 = time.perf_counter()
    r = simulate(cfg, n, seed, "greedy", CAP)
    comp = r["completion_moves"]
    curve = {m: len([c for c in comp if c is not None and c <= m]) / len(comp) for m in range(5, CAP + 1)}
    m50 = next((m for m in range(5, CAP + 1) if curve[m] >= 0.5), None)
    return name, curve, m50, time.perf_counter() - t0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--n", type=int, default=500); ap.add_argument("--procs", type=int, default=5); a = ap.parse_args()
    with Pool(a.procs) as p: res = p.map(run, [(nm, cfg, a.n, 11 + i) for i, (nm, cfg) in enumerate(variants())])
    out = {}
    lines = []
    for name, curve, m50, dt in res:
        line = f"{name:34s} 22步 {curve[22]:.2f}  30步 {curve[30]:.2f}  45步 {curve[45]:.2f}  M50={m50}  ({dt:.0f}s)"
        print(line); lines.append(line); out[name] = dict(curve=curve, m50=m50)
    json.dump(out, open(os.path.join(HERE, "data/m3_variants.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    open(os.path.join(HERE, "data/output_m3_variants.txt"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
