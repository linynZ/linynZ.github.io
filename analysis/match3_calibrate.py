#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
match3_calibrate.py —— 用 match3_sim 对 Candy Crush Saga 社区难度评级做校准实验

用法（analysis 目录下）：PYTHONUTF8=1 python match3_calibrate.py [--n 300] [--per-rank 8] [--seed 42] [--procs N]

实验设计
1. Jelly 组：type=Jelly 且 goal_nums 单值的关卡，按 difficulty_rank 1–9 每档随机抽 8 关（seed 固定）。
   cfg：moves = 关卡真实步数；果冻数 = goal_nums（≤81 单层随机分布，>81 部分格双层）；
   颜色数：关卡号 ≤100 用 5 色，否则 6 色（**假设**，wiki 数据无逐关颜色数）；9×9 无掩码、无障碍。
   附加敏感性（icon 口径）：goal_icons 为 "Double jelly" 的关卡按每格双层构造（372/405 关如此）。
2. Order 组：type=Order 且 goal_icons 只含 "<颜色>candy order.png" 的关卡，每档抽 ≤8 关（全库仅 31 关），order_color。
3. 每关 n=300 局；输出每档平均模拟通关率、Spearman(模拟通关率, difficulty_rank)、散点+档均值图。
4. 松紧系数：M50 = 让模拟通关率 ≥50% 所需的最少步数；slack = moves/M50；各档 slack 中位数。
   实现说明：贪心策略与剩余步数无关，因此"给足步数跑一次、记录每局完成步"后，
   任意步数上限下的通关率都能由完成步分布直接读出——二分搜索退化为在经验 CDF 上找中位数，结果完全等价。
   步数上限 cap = max(3×moves, moves+30)；若到 cap 仍不足 50% 完成，M50 记为 None（slack 上界 = moves/cap）。
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from multiprocessing import Pool

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from match3_sim import simulate, stats_at  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
CSV = os.path.join(HERE, 'data', 'cc_levels.csv')
OUT_JSON = os.path.join(HERE, 'data', 'm3_calibration.json')
OUT_PNG = os.path.join(HERE, 'charts', 'm3_sim_vs_rating.png')
RANK_NAMES = {1: 'Very easy', 2: 'Easy', 3: 'Somewhat easy', 4: 'Medium', 5: 'Somewhat hard',
              6: 'Hard', 7: 'Very hard', 8: 'Extremely hard', 9: 'Nearly impossible'}


# ----------------------------------------------------------------------------
# 抽样与构造
# ----------------------------------------------------------------------------
def load_rows():
    with open(CSV, encoding='utf-8') as f:
        return list(csv.DictReader(f))


def pick_levels(rows, per_rank, seed):
    rng = np.random.default_rng(seed)
    jelly = [r for r in rows if r['type'] == 'Jelly' and r['goal_nums'].strip() and '|' not in r['goal_nums']
             and r['difficulty_rank'].strip() and 'jelly' in r['goal_icons'].lower()]
    order = [r for r in rows if r['type'] == 'Order' and r['goal_nums'].strip() and '|' not in r['goal_nums']
             and r['difficulty_rank'].strip()
             and all(x.strip().lower().endswith('candy order.png') for x in r['goal_icons'].split('|'))]
    picked = []
    for group, pool in (('Jelly', jelly), ('Order', order)):
        for rank in range(1, 10):
            cand = [r for r in pool if int(r['difficulty_rank']) == rank]
            k = min(per_rank, len(cand))
            idx = rng.choice(len(cand), size=k, replace=False) if k else []
            for i in sorted(int(x) for x in idx):
                picked.append((group, cand[i]))
    return picked, len(jelly), len(order)


def colors_for(level):
    return 5 if level <= 100 else 6     # 假设：≤100 关 5 色，之后 6 色


def build_cfg(group, r, jelly_mode='spec'):
    level = int(r['level'])
    moves = int(r['moves'])
    amount = int(r['goal_nums'])
    cfg = {'size': (9, 9), 'colors': colors_for(level), 'moves': moves}
    if group == 'Jelly':
        cfg['goal'] = {'type': 'jelly', 'amount': amount}
        if jelly_mode == 'icon' and 'double' in r['goal_icons'].lower():
            cfg['goal']['layers'] = 2
    else:
        cfg['goal'] = {'type': 'order_color', 'color': 0, 'amount': amount}
    return cfg


# ----------------------------------------------------------------------------
# 并行执行
# ----------------------------------------------------------------------------
def run_one(job):
    key, cfg, n, seed = job
    moves = cfg['moves']
    cap = max(3 * moves, moves + 30)
    res = simulate(cfg, n, seed, policy='greedy', max_moves=cap)
    comp = [c for c in res['completion_moves'] if c is not None]
    comp.sort()
    # 二分等价：最小的 M 使 P(完成步 ≤ M) ≥ 0.5
    m50 = comp[(n + 1) // 2 - 1] if len(comp) >= (n + 1) // 2 else None
    curve = {M: sum(1 for c in comp if c <= M) / n for M in
             sorted({moves, max(1, moves // 2), moves + 5, moves + 10, cap})}
    out = {
        'win_rate': res['win_rate'],
        'avg_moves_left': res['avg_moves_left'],
        'near_miss_rate': res['near_miss_rate'],
        'near_miss_of_all': res['near_miss_of_all'],
        'fail_remaining_mean': float(np.mean(res['fail_remaining'])) if res['fail_remaining'] else 0.0,
        'fail_remaining_median': float(np.median(res['fail_remaining'])) if res['fail_remaining'] else 0.0,
        'm50': m50,
        'cap': cap,
        'completion_rate_at_cap': len(comp) / n,
        'win_curve': curve,
        'elapsed_s': res['elapsed_s'],
    }
    out['slack'] = (moves / m50) if m50 else None
    out['slack_upper_bound'] = moves / cap
    return key, out


# ----------------------------------------------------------------------------
# 统计
# ----------------------------------------------------------------------------
def rankdata(x):
    x = np.asarray(x, dtype=float)
    order = np.argsort(x, kind='stable')
    ranks = np.empty(len(x))
    i = 0
    while i < len(x):
        j = i
        while j + 1 < len(x) and x[order[j + 1]] == x[order[i]]:
            j += 1
        ranks[order[i:j + 1]] = (i + j) / 2.0 + 1
        i = j + 1
    return ranks


def spearman(x, y):
    rx, ry = rankdata(x), rankdata(y)
    if rx.std() == 0 or ry.std() == 0:
        return float('nan')
    return float(np.corrcoef(rx, ry)[0, 1])


def per_rank_table(items, field='win_rate'):
    tab = {}
    for rank in range(1, 10):
        vals = [it[field] for it in items if it['rank'] == rank and it[field] is not None]
        tab[rank] = {'n': len(vals), 'mean': float(np.mean(vals)) if vals else None,
                     'median': float(np.median(vals)) if vals else None}
    return tab


# ----------------------------------------------------------------------------
# 出图
# ----------------------------------------------------------------------------
def plot(results, path, n_games=300):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'DejaVu Sans']
    plt.rcParams['axes.unicode_minus'] = False
    colors = {'Jelly': '#2a78d6', 'Order': '#eb6834'}
    groups = [('Jelly', 'spec'), ('Jelly', 'icon'), ('Order', 'spec')]
    titles = {('Jelly', 'spec'): 'Jelly（题设口径：goal_nums 层）',
              ('Jelly', 'icon'): 'Jelly（icon 口径：Double jelly 每格 2 层）',
              ('Order', 'spec'): 'Order（单一颜色收集）'}
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.6), sharey=True)
    rng = np.random.default_rng(0)
    for ax, (g, mode) in zip(axes, groups):
        items = [it for it in results if it['group'] == g and it['jelly_mode'] == mode]
        col = colors[g]
        xs = np.array([it['rank'] for it in items], dtype=float)
        ys = np.array([it['win_rate'] for it in items])
        ax.scatter(xs + rng.uniform(-0.18, 0.18, len(xs)), ys, s=26, color=col, alpha=0.55,
                   edgecolors='white', linewidths=0.6, label=f'单关（每关 n={n_games} 局）', zorder=3)
        tab = per_rank_table(items)
        rk = [r for r in range(1, 10) if tab[r]['mean'] is not None]
        ax.plot(rk, [tab[r]['mean'] for r in rk], color=col, lw=2, marker='o', ms=5,
                label='档均值', zorder=4)
        rho = spearman(xs, ys)
        ax.set_title(f"{titles[(g, mode)]}\nSpearman ρ = {rho:+.2f}（{len(items)} 关）", fontsize=10.5)
        ax.set_xticks(range(1, 10))
        ax.set_xlabel('社区难度档 difficulty_rank（1=Very easy … 9=Nearly impossible）', fontsize=9)
        ax.set_ylim(-0.03, 1.03)
        ax.grid(axis='y', color='#e5e5e5', lw=0.6, zorder=0)
        for s in ('top', 'right'):
            ax.spines[s].set_visible(False)
    axes[0].set_ylabel('贪心机器人模拟通关率', fontsize=9)
    h, l = axes[0].get_legend_handles_labels()
    fig.legend(h, l, frameon=False, fontsize=9, loc='lower center', ncol=2, bbox_to_anchor=(0.5, -0.01))
    fig.suptitle('三消模拟器通关率 vs Candy Crush Saga 社区难度评级（9×9 无障碍无掩码；颜色数按关卡号假设）',
                 fontsize=11)
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    fig.savefig(path, dpi=150)
    plt.close(fig)


# ----------------------------------------------------------------------------
# 主流程
# ----------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--n', type=int, default=300)
    ap.add_argument('--per-rank', type=int, default=8)
    ap.add_argument('--seed', type=int, default=42)
    ap.add_argument('--procs', type=int, default=max(1, min(20, (os.cpu_count() or 2) - 2)))
    ap.add_argument('--no-icon', action='store_true', help='跳过 Jelly 的 icon 口径敏感性')
    ap.add_argument('--plot-only', action='store_true', help='只从已有 JSON 重绘图')
    args = ap.parse_args()
    if args.plot_only:
        with open(OUT_JSON, encoding='utf-8') as f:
            d = json.load(f)
        plot(d['levels'], OUT_PNG, d['meta']['n_games'])
        print('重绘完成', OUT_PNG)
        return

    t0 = time.time()
    rows = load_rows()
    picked, n_jelly_pool, n_order_pool = pick_levels(rows, args.per_rank, args.seed)
    print(f'候选池：Jelly 单值 {n_jelly_pool} 关，Order 单色 {n_order_pool} 关；抽样 {len(picked)} 关')

    jobs, meta = [], {}
    for group, r in picked:
        modes = ['spec'] + (['icon'] if group == 'Jelly' and not args.no_icon else [])
        for mode in modes:
            cfg = build_cfg(group, r, mode)
            key = (group, mode, int(r['level']))
            jobs.append((key, cfg, args.n, args.seed * 100000 + int(r['level'])))
            meta[key] = {'group': group, 'jelly_mode': mode, 'level': int(r['level']),
                         'episode': r['episode'], 'rank': int(r['difficulty_rank']),
                         'difficulty': r['difficulty'], 'moves': int(r['moves']),
                         'goal_nums': int(r['goal_nums']), 'goal_icons': r['goal_icons'],
                         'colors': cfg['colors'], 'remarks': r['remarks'][:80]}
    print(f'共 {len(jobs)} 个模拟任务，每任务 {args.n} 局，{args.procs} 进程 …', flush=True)

    results = []
    with Pool(args.procs) as pool:
        for i, (key, out) in enumerate(pool.imap_unordered(run_one, jobs), 1):
            it = dict(meta[key]); it.update(out)
            results.append(it)
            print(f"  [{i:3d}/{len(jobs)}] {key[0]:5s}/{key[1]:4s} L{key[2]:<5d} rank={it['rank']} "
                  f"moves={it['moves']:2d} goal={it['goal_nums']:3d} win={it['win_rate']:.2f} "
                  f"m50={it['m50']} slack={it['slack'] if it['slack'] is None else round(it['slack'],2)} "
                  f"({it['elapsed_s']:.0f}s)", flush=True)
    results.sort(key=lambda it: (it['group'], it['jelly_mode'], it['rank'], it['level']))
    elapsed = time.time() - t0

    summary = {}
    for g, mode in (('Jelly', 'spec'), ('Jelly', 'icon'), ('Order', 'spec')):
        items = [it for it in results if it['group'] == g and it['jelly_mode'] == mode]
        if not items:
            continue
        xs = [it['rank'] for it in items]
        summary[f'{g}/{mode}'] = {
            'n_levels': len(items),
            'per_rank_win_rate': per_rank_table(items, 'win_rate'),
            'per_rank_slack': per_rank_table(items, 'slack'),
            'per_rank_near_miss': per_rank_table(items, 'near_miss_rate'),
            'spearman_win_vs_rank': spearman(xs, [it['win_rate'] for it in items]),
            'spearman_slack_vs_rank': spearman([it['rank'] for it in items if it['slack'] is not None],
                                               [it['slack'] for it in items if it['slack'] is not None]),
            'spearman_moves_vs_rank': spearman(xs, [it['moves'] for it in items]),
            'spearman_goal_vs_rank': spearman(xs, [it['goal_nums'] for it in items]),
            'spearman_goal_per_move_vs_rank': spearman(xs, [it['goal_nums'] / it['moves'] for it in items]),
            'n_m50_unreached': sum(1 for it in items if it['m50'] is None),
        }

    out = {
        'meta': {'n_games': args.n, 'per_rank': args.per_rank, 'seed': args.seed, 'policy': 'greedy',
                 'board': '9x9, no mask, no blockers', 'colors_rule': 'level<=100 -> 5 colors else 6 (assumption)',
                 'jelly_modes': {'spec': 'goal_nums 个果冻层，≤81 单层随机分布，>81 部分格双层',
                                 'icon': 'goal_icons 含 Double jelly 时 goal_nums 个格子每格双层'},
                 'm50': 'min M s.t. P(completion<=M)>=0.5（等价二分），cap=max(3*moves, moves+30)',
                 'pool_sizes': {'jelly_single_goal': n_jelly_pool, 'order_single_color': n_order_pool},
                 'elapsed_s': elapsed},
        'summary': summary,
        'levels': results,
    }
    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    plot(results, OUT_PNG, args.n)

    # ---- 控制台汇报 ----
    print('\n================ 校准结果 ================')
    for name, s in summary.items():
        print(f'\n[{name}] {s["n_levels"]} 关  Spearman(win,rank)={s["spearman_win_vs_rank"]:+.3f}  '
              f'Spearman(slack,rank)={s["spearman_slack_vs_rank"]:+.3f}  '
              f'Spearman(goal/move,rank)={s["spearman_goal_per_move_vs_rank"]:+.3f}  '
              f'M50 未达 cap 关数={s["n_m50_unreached"]}')
        print(f'{"rank":>4} {"难度":<18} {"n":>2} {"通关率均值":>10} {"slack中位":>9} {"近失率均值":>10}')
        for rk in range(1, 10):
            w, sl, nm = s['per_rank_win_rate'][rk], s['per_rank_slack'][rk], s['per_rank_near_miss'][rk]
            if w['n'] == 0:
                continue
            f = lambda v: '   -  ' if v is None else f'{v:6.3f}'
            print(f'{rk:>4} {RANK_NAMES[rk]:<18} {w["n"]:>2} {f(w["mean"]):>10} {f(sl["median"]):>9} {f(nm["mean"]):>10}')
    print(f'\n总耗时 {elapsed:.0f}s；输出 {OUT_JSON} 与 {OUT_PNG}')


if __name__ == '__main__':
    main()
