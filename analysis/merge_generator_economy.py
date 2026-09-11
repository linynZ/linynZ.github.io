#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
合成游戏（Merge-2）生成器经济模型
作者：赵鹏淦 (Penggan Zhao)

⚠️ 输入是一张**示例权重表**（来自系统策划笔试题面口径），不是任何一款产品的实测配置。
   本脚本的价值在推导方法与结论形态：
     §1 产出概率与折算期望（权重表 → 每次点击的 A1 / B1 等价物期望）
     §2 单位体力价值与稀有棋子定价（折算口径 vs 直掉口径，以及为什么直掉口径是错的）
     §3 "耗 2 体力、产物 +1 级"改动的价值不变性证明，与它真正改变的东西（方差、棋盘占用）
     §4 定价对权重的敏感度
     §5 可观测的体感锚点（进游戏能数出来的数字，用于日后实证校验）
"""

from fractions import Fraction as F

# ---------- 示例权重表 ----------
WEIGHTS = {"A1": 324, "A2": 18, "A3": 18, "B1": 32, "B2": 8}
K = 2                      # 二合：每 K 个 i 级合成一个 i+1 级
COST = 1                   # 每次产出耗体力

SEP = "=" * 78
def banner(t): print("\n" + SEP + "\n" + t + "\n" + SEP)
def fmt(x, nd=4): return f"{float(x):.{nd}f}"

def probs(weights):
    tot = sum(weights.values())
    return {k: F(v, tot) for k, v in weights.items()}

def level_equiv(item, k=K):
    """i 级棋子折算成 1 级等价物的个数 = k^(i-1)"""
    return k ** (int(item[1:]) - 1)

def expected_base_units(weights, family, k=K):
    """每次产出中，family（'A'/'B'）折算成 1 级等价物的期望个数"""
    p = probs(weights)
    return sum(p[it] * level_equiv(it, k) for it in weights if it[0] == family)

def variance_base_units(weights, family, k=K):
    p = probs(weights)
    m = expected_base_units(weights, family, k)
    ex2 = sum(p[it] * level_equiv(it, k) ** 2 for it in weights if it[0] == family)
    return ex2 - m * m

# ---------- §1 ----------
banner("§1 产出概率与折算期望")
p = probs(WEIGHTS)
tot = sum(WEIGHTS.values())
print(f"总权重 = {tot}")
for it, w in WEIGHTS.items():
    print(f"  {it}: weight {w:>4}  ->  P = {w}/{tot} = {fmt(p[it])}")
pA = sum(v for k_, v in p.items() if k_[0] == "A")
pB = 1 - pA
print(f"\nP(产出 A) = {pA} = {fmt(pA)}   P(产出 B) = {fmt(pB)}")
EA = expected_base_units(WEIGHTS, "A")
EB = expected_base_units(WEIGHTS, "B")
print(f"每次产出的 A1 等价物期望 E[A1] = Σ P(A_i)·{K}^(i-1) = {EA} = {fmt(EA)}")
print(f"  交叉验证：条件期望 E[A1|A] = {fmt(EA/pA)} × P(A) {fmt(pA)} = {fmt(EA)}")
print(f"每次产出的 B1 等价物期望 E[B1] = {EB} = {fmt(EB)}")

# ---------- §2 ----------
banner("§2 单位体力价值与稀有棋子定价")
price_B1_fold = COST / EB            # 折算口径：1 个 B1 值多少体力
price_B2_fold = price_B1_fold * K
price_B2_direct = COST / p["B2"]     # 直掉口径：只算直接掉落 B2
print(f"折算口径：B1 = {COST}/{fmt(EB)} = {fmt(price_B1_fold,3)} 体力 -> B2 = ×{K} = {fmt(price_B2_fold,3)} 体力")
print(f"直掉口径：B2 = 1/P(B2) = {fmt(price_B2_direct,3)} 体力   （忽略了 B1 可合成，高估 {fmt(price_B2_direct/price_B2_fold,2)} 倍）")
print("\n折算口径把全部体力记在 B 头上，是 B2 的**上限价**。若 A 也有价值，按价值守恒分摊：")
print("   1 体力 = v_A1·E[A1] + v_B1·E[B1]")
for vA in (F(0), F(1, 4), F(1, 2), F(3, 4)):
    vB1 = (COST - vA * EA) / EB
    print(f"   设 v_A1 = {fmt(vA,2)} 体力 -> v_B1 = {fmt(vB1,3)}  v_B2 = {fmt(vB1*K,3)} 体力")
print("=> B2 的合理定价区间约 [7.7, 16.7] 体力，取决于 A 系的市场价；直掉口径的 50 不在区间内。")

# ---------- §3 ----------
banner("§3 改动：每次耗 2 体力、产物等级 +1 —— 价值不变性证明")
W2 = {k_[0] + str(int(k_[1:]) + 1): v for k_, v in WEIGHTS.items()}   # 全表 +1 级
EB2 = expected_base_units(W2, "B")
EA2 = expected_base_units(W2, "A")
print(f"新表：{W2}")
print(f"每次产出 E[B1] = {fmt(EB2)}（= 原来的 ×{K}），每次耗体力 {2*COST}")
print(f"单位体力 E[B1] = {fmt(EB2/(2*COST))}  vs 原模式 {fmt(EB/COST)}  ->  {'相等' if EB2/(2*COST)==EB/COST else '不等'}")
print(f"因此 B2 定价不变（折算口径仍 {fmt(price_B2_fold,3)} 体力）；直掉口径会误算成 1·2/P(B2') = {fmt(2*COST/p['B2'],1)} 体力，再次说明直掉口径不可靠。")
print("\n真正变化的量（同样花 N 体力）：")
N = 100
var1 = variance_base_units(WEIGHTS, "B") * N            # N 次独立产出
var2 = variance_base_units(W2, "B") * (N / 2)           # N/2 次产出
print(f"   棋子数量：{N} 个 -> {N//2} 个（棋盘占用 / 手动操作次数减半 = 便利性）")
print(f"   B1 等价物总量方差：{fmt(var1,2)} -> {fmt(var2,2)}（×{fmt(var2/var1,2)}，波动更大）")
print("   设计意图反推：这是**便利性售卖**，不是产出加成。若想做成付费加成点，需叠加真实收益，例如：")
for c in (F(9, 5), F(3, 2)):
    gain = (EB2 / c) / (EB / COST) - 1
    print(f"     耗 {fmt(c,1)} 体力（而非 2）-> 单位体力产出 +{fmt(gain*100,1)}%")

# ---------- §4 ----------
banner("§4 定价对权重的敏感度（其余权重不变）")
def price_b2(weights): return COST / expected_base_units(weights, "B") * K
base = price_b2(WEIGHTS)
print(f"基准 B2 = {fmt(base,2)} 体力")
for item, vals in (("B2", (4, 8, 16, 32)), ("B1", (16, 32, 64)), ("A3", (0, 18, 72))):
    row = []
    for v in vals:
        w = dict(WEIGHTS); w[item] = v
        row.append(f"{item}={v}: {fmt(price_b2(w),2)}")
    print("   " + " | ".join(row))
print("=> 同样翻倍，B1 权重对 B2 定价的影响（-35%）大于 B2 自身（-23%）：B1 对 E[B1] 的贡献 0.08 是 B2 贡献 0.04 的两倍；A 系权重只通过总权重分母稀释 B。")

# ---------- §5 ----------
banner("§5 可观测的体感锚点（实证校验用）")
pulls_per_B2 = 1 / (EB / K)
print(f"每 {fmt(pulls_per_B2,1)} 次点击应出现 1 个 B2 等价物（含 2×B1 合成）——进游戏数 200 次点击即可核对。")
print(f"若实测显著多于 {fmt(pulls_per_B2,0)} 次，则真实表中存在保底/伪随机或本表的 B1 权重偏高；显著少于则反之。")
print(f"三合（K=3）下同表：E[A1] = {fmt(expected_base_units(WEIGHTS,'A',3))}，E[B1] = {fmt(expected_base_units(WEIGHTS,'B',3))}，B2 = {fmt(COST/expected_base_units(WEIGHTS,'B',3)*3,2)} 体力。")
