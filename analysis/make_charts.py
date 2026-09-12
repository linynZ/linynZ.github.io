# -*- coding: utf-8 -*-
"""拆解案配图生成器（v1.1）—— 全部数据与正文/各计算脚本同源，运行即可复现。

用法: python make_charts.py   （输出到 ./charts/）
配色: #b57f22 金 / #2f96cc 蓝 / #a259e8 紫（已过 CVD 六项校验，暗面 #100e26）
"""
import math
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

GOLD, BLUE, VIOLET = "#b57f22", "#2f96cc", "#a259e8"
SURFACE = "#100e26"
INK, MUTED = "#cdc9e0", "#a09ac0"
GRID = (157 / 255, 143 / 255, 240 / 255, 0.16)

plt.rcParams.update({
    "font.family": ["Microsoft YaHei", "SimHei", "sans-serif"],
    "axes.unicode_minus": False,
    "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE,
    "savefig.facecolor": SURFACE,
    "text.color": INK,
    "axes.labelcolor": MUTED,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "axes.edgecolor": (1, 1, 1, 0.12),
    "font.size": 11,
})

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "charts")
os.makedirs(OUT, exist_ok=True)


def style_ax(ax):
    ax.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)


def save(fig, name):
    path = os.path.join(OUT, name)
    fig.savefig(path, dpi=160, bbox_inches="tight", pad_inches=0.35)
    plt.close(fig)
    print("saved", path)


# ---------------------------------------------------------------- 1. 鸣潮战斗
# E(n) 与 wuwa_combat_math.py §1 同源：CR=0.05+0.084n, CD=1.5+0.168(8-n)
def chart_combat():
    ns = list(range(0, 9))
    es = [1 + (0.05 + 0.084 * n) * (0.5 + 0.168 * (8 - n)) for n in ns]
    fig, ax = plt.subplots(figsize=(8.6, 4.6))
    ax.plot(ns, es, color=GOLD, linewidth=2, marker="o", markersize=7,
            markerfacecolor=GOLD, markeredgecolor=SURFACE, markeredgewidth=1.5)
    i = es.index(max(es))
    ax.plot(ns[i], es[i], marker="o", markersize=11, markerfacecolor="none",
            markeredgecolor=INK, markeredgewidth=1.6)
    ax.annotate(f"最优：{ns[i]} 条给暴击率\nE = {es[i]:.5f}（D/CR ≈ 2）",
                xy=(ns[i], es[i]), xytext=(ns[i] + 0.4, es[i] - 0.012),
                fontsize=10.5, color=INK)
    ax.annotate("全暴伤（CV 相同，收益 74.2%）", xy=(0, es[0]),
                xytext=(0.25, es[0] + 0.004), fontsize=9.5, color=MUTED)
    ax.set_xlabel("预算 8 条中给暴击率的条数（其余给暴伤）")
    ax.set_ylabel("暴击期望乘区 E")
    ax.set_title("固定词条预算下的双爆分配：极值在 D = 2·CR（《鸣潮》§4.1）",
                 color=INK, fontsize=12.5, pad=12)
    style_ax(ax)
    save(fig, "wuwa_crit_alloc.png")


# ---------------------------------------------------------------- 2. 鸣潮声骸
# 与 wuwa_echo_cost.py §3 同源（表格五点均为脚本输出值），交叉点 57.2%
def chart_echo():
    xs = [0, 25, 50, 75, 150]
    y43 = [3.3489, 3.8721, 4.3954, 4.9186, 6.4884]
    y44 = [2.8918, 3.6148, 4.3377, 5.0607, 7.2295]
    fig, ax = plt.subplots(figsize=(8.6, 4.6))
    ax.plot(xs, y43, color=GOLD, linewidth=2, marker="o", markersize=6,
            markeredgecolor=SURFACE, markeredgewidth=1.2, label="43311")
    ax.plot(xs, y44, color=BLUE, linewidth=2, marker="o", markersize=6,
            markeredgecolor=SURFACE, markeredgewidth=1.2, label="44111")
    ax.axvline(57.2, color=INK, linewidth=1, linestyle=(0, (4, 4)), alpha=0.55)
    ax.annotate("交叉点 57.2%", xy=(57.2, 6.7), xytext=(61, 6.7),
                fontsize=10.5, color=INK)
    ax.annotate("单人 / 弱增伤队\n→ 43311", xy=(14, 5.6), fontsize=9.5, color=MUTED)
    ax.annotate("成型强增伤队\n→ 44111", xy=(103, 4.2), fontsize=9.5, color=MUTED)
    ax.text(151.5, y43[-1], "43311", color=GOLD, fontsize=10.5, va="center")
    ax.text(151.5, y44[-1], "44111", color=BLUE, fontsize=10.5, va="center")
    ax.set_xlim(-4, 170)
    ax.set_xlabel("外部增伤总量（队友 buff / 武器 / 套装，%）")
    ax.set_ylabel("相对伤害（同一基准）")
    ax.set_title("43311 vs 44111：最优配置由队伍环境决定（《声骸》§5.3）",
                 color=INK, fontsize=12.5, pad=12)
    ax.legend(loc="upper left", frameon=False, labelcolor=INK)
    style_ax(ax)
    save(fig, "wuwa_echo_crossover.png")


# ---------------------------------------------------------------- 3. 崩铁阈值
# 与 hsr_relic_math.py §1 同源：N(s)=floor(W·s/10000)，W=150/250/350（轮制）
def chart_hsr_staircase():
    fig, ax = plt.subplots(figsize=(8.6, 4.8))
    windows = [(150, "首轮 150 AV", GOLD), (250, "前两轮 250 AV", BLUE),
               (350, "前三轮 350 AV", VIOLET)]
    speeds = [s / 10 for s in range(1000, 1810)]
    for w, label, color in windows:
        ys = [math.floor(w * s / 10000) for s in speeds]
        ax.step(speeds, ys, where="post", color=color, linewidth=2)
        ax.text(181, math.floor(w * 180 / 10000), label, color=color,
                fontsize=10, va="center")
    for x, w, note in ((133.33, 150, "133.3\n首轮两动"),
                       (142.86, 350, "142.9\n三轮五动"),
                       (160.0, 250, "160.0\n两轮四动")):
        y = round(w * x / 10000)
        ax.plot(x, y, marker="o", markersize=8, markerfacecolor="none",
                markeredgecolor=INK, markeredgewidth=1.5)
        ax.annotate(note, xy=(x, y), xytext=(x - 6.5, y + 0.55),
                    fontsize=9, color=INK, ha="center")
    ax.set_xlim(100, 196)
    ax.set_xlabel("面板速度")
    ax.set_ylabel("窗口内行动次数 N(s)")
    ax.set_title("配速阈值 = floor 的断点：三个魔法数字全部从轮制落出（《遗器》§4.1）",
                 color=INK, fontsize=12.5, pad=12)
    style_ax(ax)
    save(fig, "hsr_threshold_staircase.png")


# ---------------------------------------------------------------- 4. 崩铁口径
# 与 hsr_relic_math.py §3/§3b 同源
def chart_hsr_expectation():
    tiers = ["可用", "良品", "高分", "完美"]
    strict = [1100, 1442, 10626, 70400]
    fixed = [110, 158, 1794, 17600]
    ys = list(range(len(tiers)))[::-1]
    fig, ax = plt.subplots(figsize=(8.6, 4.2))
    for y, s, f in zip(ys, strict, fixed):
        ax.plot([f, s], [y, y], color=(1, 1, 1, 0.25), linewidth=1.6, zorder=1)
        ax.annotate(f"{s / f:.1f}×", xy=(math.sqrt(s * f), y), xytext=(0, 7),
                    textcoords="offset points", ha="center", fontsize=9, color=MUTED)
    ax.scatter(strict, ys, s=90, color=GOLD, edgecolor=SURFACE, linewidth=1.5,
               zorder=3, label="严格口径（单路径）")
    ax.scatter(fixed, ys, s=90, color=BLUE, edgecolor=SURFACE, linewidth=1.5,
               zorder=3, label="修正口径（全路径）")
    for y, s, f in zip(ys, strict, fixed):
        ax.annotate(f"{s:,}", xy=(s, y), xytext=(8, -3), textcoords="offset points",
                    fontsize=9.5, color=INK)
        ax.annotate(f"{f:,}", xy=(f, y), xytext=(-8, -3), textcoords="offset points",
                    fontsize=9.5, color=INK, ha="right")
    ax.set_xscale("log")
    ax.set_xlim(28, 130000)
    ax.set_yticks(ys)
    ax.set_yticklabels(tiers)
    ax.set_xlabel("期望件数（对数轴）")
    ax.set_title("路径漏算把期望高估 4~10 倍：严格 vs 修正口径（《遗器》§5–6）",
                 color=INK, fontsize=12.5, pad=12)
    ax.legend(loc="upper right", frameon=False, labelcolor=INK)
    style_ax(ax)
    save(fig, "hsr_expectation.png")


if __name__ == "__main__":
    chart_combat()
    chart_echo()
    chart_hsr_staircase()
    chart_hsr_expectation()
    print("done.")
