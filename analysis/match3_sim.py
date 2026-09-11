#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
match3_sim.py —— 最小可用三消（match-3）模拟器（Python 3 标准库 + numpy）

用途：为游戏策划拆解案提供"关卡步数 / 目标量 → 机器人通关率"的校准实验底座。
设计原则：YAGNI —— 只实现能跑通结论的最小规则集合。

棋盘与规则（简述）
- 棋盘默认 9×9，可用 bool 掩码裁形；颜色数 5 或 6（可配）。
- 交换相邻两格，必须形成 ≥3 连（或用彩球与普通糖交换）。
- 3 连消除；4 连生成条纹糖（触发时清整行或整列，方向随机）；
  5 连生成彩球（触发时清除一种颜色全部；被动触发时颜色随机）；
  L/T 形（横竖同时 ≥3 且相交）生成包装糖（触发时清 3×3，落定后再爆一次）。
- 重力下落 + 顶部随机补充；连锁消除全部计入。初始棋盘不含现成三连且至少有一步合法交换。
- 目标：jelly（每格 1/2 层果冻，消除该格糖果去一层）；order_color（收集指定颜色 N 个）；
  ingredients（配料从顶部投放，落到所在列段底部即收集）。
- 障碍：frosting（糖霜 1–3 层，占格、不可交换、不下落，被消除波及或相邻消除去一层）。
- 机器人：greedy = 枚举全部合法交换，各模拟一步（含连锁）后按
  (目标推进量, 生成特效数, 总消除数) 字典序打分，同分随机；random = 随机合法交换。

API
    simulate(level_cfg, n_games, seed, policy='greedy', max_moves=None) -> dict
    level_cfg = {
        'size': (9, 9),                # 可选
        'mask': [[True,...],...],      # 可选，bool 矩阵
        'colors': 6,
        'moves': 25,
        'goal': {'type': 'jelly', 'amount': 64}            # 或 'layout': 2D 层数矩阵
              | {'type': 'order_color', 'color': 0, 'amount': 80}
              | {'type': 'ingredients', 'amount': 2, 'concurrent': 1}
        'blockers': {'frosting': 2D 层数矩阵},              # 可选
    }
返回值含：win_rate、avg_moves_left（胜局平均剩余步）、fail_remaining（败局剩余目标量）、
near_miss_rate（败局中"估算仅差 1–3 步"的比例）、completion_moves、trajectories 等。
"""
from __future__ import annotations

import time
import numpy as np

EMPTY = -1          # 空格 / 固定格（掩码外、糖霜）
INGR = 8            # 配料（占格，不可交换、不可消除、不参与匹配）
CB = 9              # 彩球颜色值（不参与线性匹配）
S_NONE, S_STRIPED, S_WRAPPED, S_CB = 0, 1, 2, 3


# ----------------------------------------------------------------------------
# 基础工具
# ----------------------------------------------------------------------------
def find_matches(c, ncolors):
    """返回 (hm, vm)：横向/纵向 ≥3 连的格子掩码。支持 2D 或 3D（批量）。"""
    valid = (c >= 0) & (c < ncolors)
    h3 = (c[..., :, :-2] == c[..., :, 1:-1]) & (c[..., :, 1:-1] == c[..., :, 2:]) & valid[..., :, :-2]
    hm = np.zeros(c.shape, dtype=bool)
    hm[..., :, :-2] |= h3
    hm[..., :, 1:-1] |= h3
    hm[..., :, 2:] |= h3
    v3 = (c[..., :-2, :] == c[..., 1:-1, :]) & (c[..., 1:-1, :] == c[..., 2:, :]) & valid[..., :-2, :]
    vm = np.zeros(c.shape, dtype=bool)
    vm[..., :-2, :] |= v3
    vm[..., 1:-1, :] |= v3
    vm[..., 2:, :] |= v3
    return hm, vm


def _runs(line_mask, line_color):
    """把一条线上的匹配掩码切成 (start, end_exclusive) 的同色连续段。"""
    runs = []
    n = len(line_mask)
    i = 0
    while i < n:
        if line_mask[i]:
            j = i + 1
            while j < n and line_mask[j] and line_color[j] == line_color[i]:
                j += 1
            runs.append((i, j))
            i = j
        else:
            i += 1
    return runs


class _Pairs:
    """预生成所有相邻交换对（按棋盘尺寸缓存）。"""
    _cache = {}

    @classmethod
    def get(cls, rows, cols):
        key = (rows, cols)
        if key not in cls._cache:
            r1, c1, r2, c2 = [], [], [], []
            for r in range(rows):
                for c in range(cols):
                    if c + 1 < cols:
                        r1.append(r); c1.append(c); r2.append(r); c2.append(c + 1)
                    if r + 1 < rows:
                        r1.append(r); c1.append(c); r2.append(r + 1); c2.append(c)
            cls._cache[key] = tuple(np.array(x, dtype=np.int64) for x in (r1, c1, r2, c2))
        return cls._cache[key]


# ----------------------------------------------------------------------------
# 棋盘状态
# ----------------------------------------------------------------------------
class Board:
    __slots__ = ('rows', 'cols', 'ncolors', 'mask', 'color', 'spec', 'jelly', 'frost', 'ingr',
                 'goal', 'collected', 'ingr_to_spawn', 'ingr_concurrent', 'pending_wrapped',
                 'has_frost', '_colidx', '_fixed')

    def __init__(self, cfg, rng):
        rows, cols = cfg.get('size', (9, 9))
        self.rows, self.cols = rows, cols
        self.ncolors = int(cfg.get('colors', 6))
        mask = cfg.get('mask')
        self.mask = np.ones((rows, cols), dtype=bool) if mask is None else np.array(mask, dtype=bool)
        self.color = np.full((rows, cols), EMPTY, dtype=np.int8)
        self.spec = np.zeros((rows, cols), dtype=np.int8)
        self.jelly = np.zeros((rows, cols), dtype=np.int8)
        self.frost = np.zeros((rows, cols), dtype=np.int8)
        self.ingr = np.zeros((rows, cols), dtype=bool)
        self.goal = cfg['goal']
        self.collected = 0
        self.ingr_to_spawn = 0
        self.ingr_concurrent = 1
        self.pending_wrapped = []

        bl = cfg.get('blockers') or {}
        if 'frosting' in bl:
            self.frost = np.array(bl['frosting'], dtype=np.int8) * self.mask
        self.has_frost = bool(self.frost.any())
        self._colidx = np.arange(cols)[None, :]
        self._fixed = None

        g = self.goal
        if g['type'] == 'jelly':
            if 'layout' in g:
                self.jelly = np.array(g['layout'], dtype=np.int8) * self.mask
            else:
                self.jelly = self._random_jelly(int(g['amount']), rng)
        elif g['type'] == 'ingredients':
            self.ingr_to_spawn = int(g['amount'])
            self.ingr_concurrent = int(g.get('concurrent', 1))

        self.fresh_deal(rng)
        if g['type'] == 'ingredients':
            self._spawn_ingredients(rng)

    # -- 初始化 -------------------------------------------------------------
    def _random_jelly(self, amount, rng):
        cells = np.argwhere(self.mask & (self.frost == 0))
        n = len(cells)
        jelly = np.zeros((self.rows, self.cols), dtype=np.int8)
        layers = int(self.goal.get('layers', 1))   # layers=2：amount 个格子每格双层
        order = rng.permutation(n)
        if layers >= 2:
            for k in range(min(amount, n)):
                r, c = cells[order[k]]
                jelly[r, c] = 2
            return jelly
        amount = min(amount, 2 * n)
        for k in range(amount):
            r, c = cells[order[k % n]]
            jelly[r, c] += 1
        return jelly

    def fresh_deal(self, rng):
        """在全部可放糖的格子重新随机发牌，保证无现成三连且至少有一步合法交换。"""
        free = self.mask & (self.frost == 0) & ~self.ingr
        for _ in range(50):
            col = self.color.tolist()
            for r in range(self.rows):
                for c in range(self.cols):
                    if not free[r, c]:
                        continue
                    banned = set()
                    if c >= 2 and col[r][c - 1] == col[r][c - 2] and col[r][c - 1] >= 0:
                        banned.add(col[r][c - 1])
                    if r >= 2 and col[r - 1][c] == col[r - 2][c] and col[r - 1][c] >= 0:
                        banned.add(col[r - 1][c])
                    choices = [x for x in range(self.ncolors) if x not in banned]
                    col[r][c] = choices[int(rng.integers(len(choices)))]
            self.color = np.array(col, dtype=np.int8)
            self.spec[free] = S_NONE
            if len(self.legal_swaps()[0]) > 0:
                return
        # 极端情况下（掩码过碎）允许无解棋盘，由上层再次洗牌

    def _spawn_ingredients(self, rng):
        if self.ingr_to_spawn <= 0:
            return
        while self.ingr.sum() < self.ingr_concurrent and self.ingr_to_spawn > 0:
            top = [c for c in range(self.cols)
                   if self.mask[0, c] and self.frost[0, c] == 0 and not self.ingr[0, c]]
            if not top:
                return
            c = top[int(rng.integers(len(top)))]
            self.color[0, c] = INGR
            self.spec[0, c] = S_NONE
            self.ingr[0, c] = True
            self.ingr_to_spawn -= 1

    def copy(self):
        b = Board.__new__(Board)
        b.rows, b.cols, b.ncolors, b.mask, b.goal = self.rows, self.cols, self.ncolors, self.mask, self.goal
        b.has_frost, b._colidx, b._fixed = self.has_frost, self._colidx, None
        b.color = self.color.copy()
        b.spec = self.spec.copy()
        b.jelly = self.jelly.copy()
        b.frost = self.frost.copy()
        b.ingr = self.ingr.copy()
        b.collected = self.collected
        b.ingr_to_spawn = self.ingr_to_spawn
        b.ingr_concurrent = self.ingr_concurrent
        b.pending_wrapped = list(self.pending_wrapped)
        return b

    # -- 目标 -----------------------------------------------------------------
    def remaining(self):
        t = self.goal['type']
        if t == 'jelly':
            return int(self.jelly.sum())
        if t == 'order_color':
            return max(0, int(self.goal['amount']) - self.collected)
        if t == 'ingredients':
            return max(0, int(self.goal['amount']) - self.collected)
        raise ValueError(t)

    def _ingr_progress(self):
        # 配料所在行号之和（越低越大）+ 已收集数 × 行数
        return int(np.nonzero(self.ingr)[0].sum()) + self.collected * self.rows

    # -- 合法交换 -------------------------------------------------------------
    def legal_swaps(self):
        r1, c1, r2, c2 = _Pairs.get(self.rows, self.cols)
        swappable = self.mask & (self.color >= 0) & ~self.ingr & (self.frost == 0)
        ok = swappable[r1, c1] & swappable[r2, c2]
        r1, c1, r2, c2 = r1[ok], c1[ok], r2[ok], c2[ok]
        n = len(r1)
        if n == 0:
            return np.zeros((0, 4), dtype=np.int64), None
        B = np.repeat(self.color[None], n, axis=0)
        ks = np.arange(n)
        a = self.color[r1, c1]
        b = self.color[r2, c2]
        B[ks, r1, c1] = b
        B[ks, r2, c2] = a
        hm, vm = find_matches(B, self.ncolors)
        match = (hm | vm).reshape(n, -1).any(axis=1)
        cbswap = ((a == CB) & (b < self.ncolors)) | ((b == CB) & (a < self.ncolors))
        legal = match | cbswap
        sel = np.stack([r1, c1, r2, c2], axis=1)[legal]
        return sel, None

    # -- 执行一步 -------------------------------------------------------------
    def apply_swap(self, swap, rng):
        """执行交换并结算所有连锁。返回 stats dict。"""
        r1, c1, r2, c2 = (int(x) for x in swap)
        color, spec = self.color, self.spec
        a, b = int(color[r1, c1]), int(color[r2, c2])
        extra = None
        if a == CB or b == CB:
            if a == CB and b == CB:
                extra = (color >= 0) & (color < self.ncolors)
            elif a == CB:
                extra = (color == b)
                extra[r1, c1] = True
            else:
                extra = (color == a)
                extra[r2, c2] = True
            # 彩球交换：彩球本身随即消失（不再作为特效触发）
            if a == CB:
                spec[r1, c1] = S_NONE
            if b == CB:
                spec[r2, c2] = S_NONE
        color[r1, c1], color[r2, c2] = b, a
        spec[r1, c1], spec[r2, c2] = spec[r2, c2], spec[r1, c1]
        return self.resolve(rng, swap_cells=((r1, c1), (r2, c2)), extra=extra)

    def resolve(self, rng, swap_cells=None, extra=None):
        stats = {'jelly': 0, 'color_counts': np.zeros(self.ncolors, dtype=np.int64),
                 'specials': 0, 'cleared': 0, 'ingr': 0}
        ingr_before = self._ingr_progress() if self.goal['type'] == 'ingredients' else 0
        first = True
        nc = self.ncolors
        while True:
            color = self.color
            hm, vm = find_matches(color, nc)
            R = hm | vm
            if extra is not None:
                R |= extra
                extra = None
            if self.pending_wrapped:
                for (r, c) in self.pending_wrapped:
                    R[max(0, r - 1):r + 2, max(0, c - 1):c + 2] = True
                self.pending_wrapped = []
            if not R.any():
                break
            created = self._make_specials(hm, vm, swap_cells if first else None) if (hm.any() or vm.any()) else []
            R = self._activate(R, rng)
            for (r, c, _k) in created:
                R[r, c] = False
            removed = R & (color >= 0) & ~self.ingr
            # 果冻
            jm = removed & (self.jelly > 0)
            nj = int(jm.sum())
            if nj:
                self.jelly[jm] -= 1
                stats['jelly'] += nj
            # 糖霜：被波及或四邻消除
            if self.has_frost:
                nb = R.copy()
                nb[1:, :] |= R[:-1, :]
                nb[:-1, :] |= R[1:, :]
                nb[:, 1:] |= R[:, :-1]
                nb[:, :-1] |= R[:, 1:]
                fm = nb & (self.frost > 0)
                if fm.any():
                    self.frost[fm] -= 1
                    stats['cleared'] += int(fm.sum())
            # 颜色统计
            cm = removed & (color < nc)
            if cm.any():
                stats['color_counts'] += np.bincount(color[cm], minlength=nc)[:nc]
            stats['cleared'] += int(removed.sum())
            color[removed] = EMPTY
            self.spec[removed] = S_NONE
            for (r, c, k) in created:
                self.spec[r, c] = k
                if k == S_CB:
                    color[r, c] = CB
            stats['specials'] += len(created)
            self._gravity_refill(rng)
            first = False
        if self.goal['type'] == 'order_color':
            self.collected += int(stats['color_counts'][int(self.goal['color'])])
        if self.goal['type'] == 'ingredients':
            stats['ingr'] = self._ingr_progress() - ingr_before
        return stats

    def _make_specials(self, hm, vm, swap_cells):
        color = self.color
        col = color.tolist()
        hml, vml = hm.tolist(), vm.tolist()
        hruns, vruns = [], []
        rows_any = hm.any(axis=1).tolist()
        cols_any = vm.any(axis=0).tolist()
        for r in range(self.rows):
            if rows_any[r]:
                for (s, e) in _runs(hml[r], col[r]):
                    hruns.append([(r, c) for c in range(s, e)])
        if any(cols_any):
            colT = [list(x) for x in zip(*col)]
            vmlT = [list(x) for x in zip(*vml)]
            for c in range(self.cols):
                if cols_any[c]:
                    for (s, e) in _runs(vmlT[c], colT[c]):
                        vruns.append([(r, c) for r in range(s, e)])
        created = []
        used = set()
        swap = set(swap_cells) if swap_cells else set()

        def anchor(cells):
            for x in cells:
                if x in swap:
                    return x
            return cells[len(cells) // 2]

        # 5 连 → 彩球
        for run in hruns + vruns:
            if len(run) >= 5:
                a = anchor(run)
                if a not in used:
                    created.append((a[0], a[1], S_CB))
                    used.update(run)
        # L/T → 包装糖
        vset = {}
        for run in vruns:
            for x in run:
                vset[x] = run
        for run in hruns:
            if any(x in used for x in run):
                continue
            for x in run:
                if x in vset and not any(y in used for y in vset[x]):
                    created.append((x[0], x[1], S_WRAPPED))
                    used.update(run)
                    used.update(vset[x])
                    break
        # 4 连 → 条纹
        for run in hruns + vruns:
            if len(run) == 4 and not any(x in used for x in run):
                a = anchor(run)
                created.append((a[0], a[1], S_STRIPED))
                used.update(run)
        return created

    def _activate(self, R, rng):
        spec, color = self.spec, self.color
        done = set()
        queue = [tuple(x) for x in np.argwhere(R & (spec > 0)).tolist()]
        while queue:
            r, c = queue.pop()
            if (r, c) in done:
                continue
            done.add((r, c))
            k = spec[r, c]
            if k == S_STRIPED:
                if rng.random() < 0.5:
                    R[r, :] = True
                else:
                    R[:, c] = True
            elif k == S_WRAPPED:
                R[max(0, r - 1):r + 2, max(0, c - 1):c + 2] = True
                self.pending_wrapped.append((r, c))
            elif k == S_CB:
                cc = int(rng.integers(self.ncolors))
                R |= (color == cc)
            queue.extend(x for x in (tuple(y) for y in np.argwhere(R & (spec > 0)).tolist()) if x not in done)
        return R

    def _gravity_refill(self, rng):
        if self.has_frost or self._fixed is None:
            self._fixed = ~self.mask | (self.frost > 0)
        fixed = self._fixed
        for _ in range(3):
            occupied = self.color >= 0
            seg = np.cumsum(fixed, axis=0)
            key = seg * 3 + np.where(fixed, 0, np.where(occupied, 2, 1))
            idx = np.argsort(key, axis=0, kind='stable')
            ci = self._colidx
            self.color = self.color[idx, ci]
            self.spec = self.spec[idx, ci]
            if self.goal['type'] != 'ingredients':
                break
            self.ingr = self.ingr[idx, ci]
            if not self.ingr.any():
                break
            # 配料落到列段底部即收集
            below_fixed = np.ones_like(fixed)
            below_fixed[:-1, :] = fixed[1:, :]
            got = self.ingr & below_fixed
            if not got.any():
                break
            self.collected += int(got.sum())
            self.color[got] = EMPTY
            self.ingr[got] = False
        if self.goal['type'] == 'ingredients':
            self._spawn_ingredients(rng)
        empty = (self.color < 0) & ~fixed
        n = int(empty.sum())
        if n:
            self.color[empty] = rng.integers(0, self.ncolors, n, dtype=np.int8)
            self.spec[empty] = S_NONE

    def shuffle(self, rng):
        """无合法交换时洗牌：重发所有普通糖的颜色（保留特效糖、配料、障碍、果冻）。"""
        keep = self.spec > 0
        saved_color = self.color.copy()
        self.fresh_deal(rng)
        self.color[keep] = saved_color[keep]


# ----------------------------------------------------------------------------
# 策略与对局
# ----------------------------------------------------------------------------
def _score(board, stats):
    t = board.goal['type']
    if t == 'jelly':
        prog = stats['jelly']
    elif t == 'order_color':
        prog = int(stats['color_counts'][int(board.goal['color'])])
    else:
        prog = stats['ingr']
    return prog * 10000 + stats['specials'] * 100 + stats['cleared']


def choose_move(board, legal, policy, rng):
    if policy == 'random':
        return legal[int(rng.integers(len(legal)))]
    best, best_s = [], None
    for sw in legal:
        b = board.copy()
        s = _score(board, b.apply_swap(sw, rng))
        if best_s is None or s > best_s:
            best, best_s = [sw], s
        elif s == best_s:
            best.append(sw)
    return best[int(rng.integers(len(best)))]


def play_game(cfg, rng, policy='greedy', max_moves=None):
    """跑一局，返回每步之后的剩余目标量轨迹（长度 ≤ max_moves；提前达成则截断）。"""
    board = Board(cfg, rng)
    if max_moves is None:
        max_moves = int(cfg['moves'])
    traj = []
    for _ in range(max_moves):
        legal, _ = board.legal_swaps()
        tries = 0
        while len(legal) == 0 and tries < 5:
            board.shuffle(rng)
            legal, _ = board.legal_swaps()
            tries += 1
        if len(legal) == 0:
            traj.append(board.remaining())
            continue
        sw = choose_move(board, legal, policy, rng)
        board.apply_swap(sw, rng)
        rem = board.remaining()
        traj.append(rem)
        if rem == 0:
            break
    return traj


def stats_at(trajectories, moves, initial_amount=None):
    """在给定步数上限 moves 下，从轨迹计算通关率 / 剩余步 / 败局剩余目标 / 差几步估计。"""
    wins, moves_left, fail_rem, est_short = 0, [], [], []
    for traj in trajectories:
        t = traj[:moves]
        if t and t[-1] == 0:
            wins += 1
            moves_left.append(moves - len(t))
        else:
            rem = t[-1] if t else (initial_amount if initial_amount is not None else float('nan'))
            fail_rem.append(rem)
            # 最后 5 步平均每步推进量
            if len(t) >= 6:
                rate = (t[-6] - t[-1]) / 5.0
            elif len(t) >= 2:
                rate = (t[0] - t[-1]) / (len(t) - 1)
            else:
                rate = 0.0
            est_short.append(rem / rate if rate > 0 else float('inf'))
    n = len(trajectories)
    fails = n - wins
    near = sum(1 for e in est_short if e <= 3.0)
    return {
        'n_games': n,
        'win_rate': wins / n if n else float('nan'),
        'avg_moves_left': float(np.mean(moves_left)) if moves_left else 0.0,
        'fail_remaining': fail_rem,
        'est_moves_short': [e if e != float('inf') else None for e in est_short],
        'near_miss_rate': near / fails if fails else 0.0,     # 败局中"估算差 1–3 步"的比例
        'near_miss_of_all': near / n if n else 0.0,
    }


def simulate(level_cfg, n_games, seed, policy='greedy', max_moves=None):
    """核心 API。max_moves 用于跑"超额步数"以便后处理任意步数上限（策略与剩余步数无关）。"""
    rng = np.random.default_rng(seed)
    moves = int(level_cfg['moves'])
    cap = max_moves or moves
    t0 = time.perf_counter()
    trajs = [play_game(level_cfg, rng, policy, cap) for _ in range(n_games)]
    dt = time.perf_counter() - t0
    g = level_cfg['goal']
    init_amt = g.get('amount') if 'amount' in g else int(np.array(g.get('layout', 0)).sum())
    out = stats_at(trajs, moves, init_amt)
    out['completion_moves'] = [len(t) if (t and t[-1] == 0) else None for t in trajs]
    out['trajectories'] = trajs
    out['elapsed_s'] = dt
    out['policy'] = policy
    out['moves'] = moves
    out['max_moves'] = cap
    return out


# ----------------------------------------------------------------------------
# 自检
# ----------------------------------------------------------------------------
if __name__ == '__main__':
    cfgs = [
        {'name': 'jelly-64/6c/25m', 'colors': 6, 'moves': 25, 'goal': {'type': 'jelly', 'amount': 64}},
        {'name': 'order-blue80/6c/25m', 'colors': 6, 'moves': 25, 'goal': {'type': 'order_color', 'color': 0, 'amount': 80}},
        {'name': 'ingr-2/6c/25m', 'colors': 6, 'moves': 25, 'goal': {'type': 'ingredients', 'amount': 2, 'concurrent': 1}},
    ]
    mask = np.ones((9, 9), dtype=bool)
    mask[0, 0] = mask[0, 8] = mask[8, 0] = mask[8, 8] = False
    fr = np.zeros((9, 9), dtype=int)
    fr[4, 3:6] = 2
    cfgs.append({'name': 'jelly-40/5c/25m/mask+frost', 'colors': 5, 'moves': 25, 'mask': mask.tolist(),
                 'goal': {'type': 'jelly', 'amount': 40}, 'blockers': {'frosting': fr.tolist()}})
    for cfg in cfgs:
        for pol in ('greedy', 'random'):
            r = simulate(cfg, 50, 1, policy=pol)
            print(f"{cfg['name']:32s} {pol:6s} win={r['win_rate']:.2f} "
                  f"avg_left={r['avg_moves_left']:.1f} near_miss={r['near_miss_rate']:.2f} "
                  f"{r['elapsed_s']*1000/50:.0f} ms/局")
