# -*- coding: utf-8 -*-
"""《天涯明月刀》端游 · 身份与日常时间预算拆解案 · 计算脚本（v1.0）

数据来自 data/tianya_sources.md：2023-04 官方《升级宝典与必做日常》清单、各身份次数上限（2017/2023）、
有据可查的时长（缉拿 20 分钟/次 2018；论剑场均 61 s 2015；王府乱斗 7.5 分钟/局 2023；合璧 10 分钟/局 2022；剑荡窗口 2 h）、
神兵材料需求与周产出（2018 / 2025）、神池问影保底（2025/2026）。
**时长中标 est 的是作者估计**（公开资料没有任何"完整日常 X 分钟"口径），正文明示；换参数重跑即可。
用法：PYTHONUTF8=1 python tianya_daily_budget.py → 终端 + charts/ty_daily_*.png + data/ty_daily_summary.json
"""
import json, os
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
OUT = os.path.join(HERE, "charts"); S = {}


def style(ax):
    ax.grid(True, color=GRID, linewidth=.8); ax.set_axisbelow(True)
    for s in ("top", "right"): ax.spines[s].set_visible(False)


# ---------- 1. 每日 / 每周 必做清单（2023 官方）与时长 ----------
# (名称, 分钟, 来源/est, 独立窗口数, 是否可被"减负令/APP"买掉)
DAILY = [
    ("帮派委任前 10 次", 15, "est", 1, False),
    ("势力日常 2 个", 10, "est", 1, False),
    ("师妹排课 / 游历", 3, "est", 1, False),
    ("别业收水果 / 茶话会", 5, "est", 1, False),
    ("天波府 或 羽林宫", 15, "est", 1, False),
    ("门派打坐（可存 3 日）", 5, "est·挂机", 1, True),
    ("怪物阅历（可叠 7 日）", 10, "est", 1, True),
    ("每日必买 ×2 + 商城免费抽", 2, "est", 2, False),
    ("游戏外礼包（助手 / 同人 SHOW 签到）", 2, "est·手机", 2, False),
]
WEEKLY = [
    ("话本 6 本（每周刷新）", 6 * 20, "est 20 分/本", 1),
    ("论剑周常 5 场", 5 * (61 / 60 + 2), "61 s/场 官方 + est 2 分排队", 1),
    ("合璧之战周常（二四六）", 3 * 10, "10 分/局 官方", 1),
    ("战场挑战 / 王府乱斗（一三五）", 3 * 7.5, "7.5 分/局 官方", 1),
    ("同心周常 / 宅邸 3 泡澡 3 拜访", 15, "est", 2),
    ("周三枭野争锋 / 周六天地风云 / 周日天下镖", 3 * 40, "est 40 分/场", 3),
    ("八个周购商店", 10, "est", 8),
]
IDENT = {  # 身份：每日次数上限 × 单次时长
    "捕快·缉拿": (4, 20, "4 次/日 官方；20 分/次 2018 攻略", 1),
    "镖师·押镖（游戏内）": (10, 3, "10 次/日 官方；est 3 分/次", 1),
    "镖师·押镖（天刀助手 APP）": (10, 0.5, "APP 可完成 官方；est 0.5 分/次", 0),
    "游侠·怜花宝藏（5 人）": (8, 6, "8 次/日 官方；est 6 分/次含组队", 1),
    "杀手·悬赏令": (13, 3, "13 次/日 2017；est 3 分/次", 1),
    "乐伶 / 文士·演奏创作": (1, 15, "est", 1),
    "厨师·采集烹饪": (1, 10, "est", 1),
    "猎户·狩猎": (1, 15, "半小时刷猎物 官方；est", 1),
}
d_min = sum(x[1] for x in DAILY); w_min = sum(x[1] for x in WEEKLY); w_daily = w_min / 7
print("## 1 时间预算（分钟）")
print(f"  每日必做 9 项合计 {d_min:.0f} 分钟（{sum(1 for x in DAILY if x[2].startswith('est'))}/9 为估计值）")
print(f"  每周内容合计 {w_min:.0f} 分钟 → 摊到每日 {w_daily:.0f} 分钟")
for name, (n, m, src, win) in IDENT.items(): print(f"  身份 {name:22s} {n:2d} 次 × {m:4.1f} 分 = {n*m:5.1f} 分/日   [{src}]")
profiles = {
    "轻度：只做必做（打坐/阅历用减负令）": d_min - 15,
    "中度：必做 + 周常摊薄 + 一个轻身份（押镖 APP）": d_min + w_daily + 5,
    "中度：必做 + 周常摊薄 + 一个重身份（捕快）": d_min + w_daily + 80,
    "重度：以上全做 + 两身份（捕快+莲花）+ 帮会/论剑加练 60": d_min + w_daily + 80 + 48 + 60,
}
print("  画像（分钟/日）：")
for k, v in profiles.items(): print(f"    {k:40s} {v:5.0f} 分 ≈ {v/60:.1f} h")
print("  用户锚点：中度、每天 1–2 小时、日常全做 + 身份 → 模型给中度 2.0（轻身份）–3.2 h（重身份），口述区间只覆盖到轻身份档（见正文讨论）")
S["daily_min"] = d_min; S["weekly_min"] = w_min; S["profiles"] = profiles
S["ident"] = {k: dict(n=v[0], per=v[1], total=v[0] * v[1], src=v[2]) for k, v in IDENT.items()}

# ---------- 2. 身份效率：单位时间的"稀缺产出" ----------
# 产出稀缺度（作者按 2023 官方产出描述的定性打分 1–5：砭石/心法残页/紫神兵材料=高，银两/碎银=低）
SCARCE = {"捕快·缉拿": 4, "镖师·押镖（游戏内）": 2, "镖师·押镖（天刀助手 APP）": 2, "游侠·怜花宝藏（5 人）": 4, "杀手·悬赏令": 4, "乐伶 / 文士·演奏创作": 3, "厨师·采集烹饪": 3, "猎户·狩猎": 3}
print("\n## 2 身份：日耗时 vs 产出稀缺度（稀缺度为作者定性打分 1–5，见正文）")
eff = {}
for k, (n, m, src, win) in IDENT.items():
    t = n * m; e = SCARCE[k] / max(t, 0.5) * 10; eff[k] = e
    print(f"  {k:22s} 日耗时 {t:5.1f} 分  稀缺度 {SCARCE[k]}  效率 {e:5.2f}/10 分")
S["ident_eff"] = eff

# ---------- 3. 打卡窗口计数（与 Gossip Harbor 活动疲劳案同口径：一天要打开的独立界面 / 动作） ----------
daily_win = sum(x[3] for x in DAILY); weekly_win = sum(x[3] for x in WEEKLY)
ident_win = 1
print("\n## 3 打卡窗口")
print(f"  每日必做窗口 {daily_win} 个（含 2 个手机 APP、2 个商城动作）；周常窗口 {weekly_win} 个（含 8 个商店）→ 摊到每日 {weekly_win/7:.1f}")
print(f"  中度玩家一天要打开的独立窗口 ≈ {daily_win + ident_win + weekly_win/7:.1f} 个；对照 Gossip Harbor 需操作窗口日均 5.7 个（本作品集活动疲劳案）")
S["windows"] = {"daily": daily_win, "weekly": weekly_win, "per_day_mid": daily_win + ident_win + weekly_win / 7, "gh_ref": 5.7}

# ---------- 4. 养成周期：一件紫色神兵 ----------
need = {"缘材·初": 29640, "缘材·进": 296, "金碎银": 8160, "质料": 240}   # 2018 整件紫神兵（三质料）
free_chu = {"话本 6 本/周（101–115 本，2025）": 2750, "金质帮派礼盒 20/周（2025）": 240, "潜龙之渊海战 3 次/周（2018）": 360, "帮派商店周上限（需 10,220 帮贡）": 1120}
free_jin = {"修为商店 5/周（2025）": 5, "神魄商店：周活跃 700 档 500 神魄 + 势力日常 70/周 ÷ 50": 570 / 50}
paid_jin = {"商城每周 50 个（阶梯价，最后 10 个 3,000 绑点/个）": 50}
chu_free = sum(free_chu.values()); chu_free_noguild = chu_free - 1120
jin_free = sum(free_jin.values()); jin_paid = jin_free + sum(paid_jin.values())
print("\n## 4 一件紫色神兵的周期（材料需求 2018；周产出 2018/2025 混合口径）")
print(f"  缘材·初 需 {need['缘材·初']}：免费周产 {chu_free:.0f}（不含帮派商店 {chu_free_noguild:.0f}）→ {need['缘材·初']/chu_free:.1f}–{need['缘材·初']/chu_free_noguild:.1f} 周")
print(f"  缘材·进 需 {need['缘材·进']}：免费周产 {jin_free:.1f} → {need['缘材·进']/jin_free:.1f} 周；加商城 50/周 → {need['缘材·进']/jin_paid:.1f} 周")
print(f"  → 免费玩家瓶颈在缘材·进（约 {need['缘材·进']/jin_free:.0f} 周 ≈ {need['缘材·进']/jin_free/4.3:.1f} 个月），付费可压到 {need['缘材·进']/jin_paid:.1f} 周：付费买掉了 {100*(1-jin_free/jin_paid):.0f}% 的等待时间")
print(f"  时间价格上界：商城最后 10 个 3,000 绑点/个 ↔ 免费口径 1 个缘材·进 ≈ {7/jin_free:.2f} 天的全部日常")
S["ascension"] = {"need": need, "chu_weeks": [need['缘材·初'] / chu_free, need['缘材·初'] / chu_free_noguild], "jin_weeks_free": need['缘材·进'] / jin_free, "jin_weeks_paid": need['缘材·进'] / jin_paid, "paid_time_saved": 1 - jin_free / jin_paid}

# ---------- 5. 外观抽卡保底：期望抽数 ----------
def exp_draws(p, pity):
    q = 1 - p; return (1 - q ** pity) / p + pity * q ** pity
print("\n## 5 神池问影：限定保底 200 抽（点券池）/ 400 抽（绑点池）下的期望抽数")
gacha = {}
for p in (.005, .01, .02, .04):
    e1, e2 = exp_draws(p, 200), exp_draws(p, 400); gacha[p] = (e1, e2)
    print(f"  基础概率 {100*p:.1f}%：点券池期望 {e1:5.1f} 抽（保底触发率 {100*(1-p)**200:.0f}%）  绑点池期望 {e2:5.1f} 抽")
print("  基础概率未公开；保底把 0.5% 概率下的尾部从无穷截到 200，期望从 200 降到 127——保底的价值主要是砍尾部而非降均值")
S["gacha"] = {f"{100*p:.1f}": v for p, v in gacha.items()}

json.dump(S, open(os.path.join(HERE, "data/ty_daily_summary.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=float)

# ---------- 图 ----------
fig, axs = plt.subplots(1, 2, figsize=(12.5, 4.4))
ax = axs[0]
labels = list(profiles); vals = [v / 60 for v in profiles.values()]
ax.barh([l.split("：")[0] + "\n" + l.split("：")[1][:18] for l in labels], vals, color=[BLUE, GOLD, GOLD, VIOLET])
ax.axvspan(1, 2, color=ICE, alpha=.12); ax.text(1.5, -0.55, "用户口述 1–2 h", color=ICE, fontsize=9, ha="center")
for i, v in enumerate(vals): ax.text(v + .05, i, f"{v:.1f} h", va="center", color=INK, fontsize=9)
ax.invert_yaxis(); ax.set_xlabel("每日时间（小时，含估计项）"); ax.set_title("四种画像的每日时间预算", color=INK, fontsize=12); style(ax)
ax = axs[1]
names = list(IDENT); ts = [IDENT[k][0] * IDENT[k][1] for k in names]; sc = [SCARCE[k] for k in names]
ax.scatter(ts, sc, s=80, color=GOLD)
offs = {"乐伶 / 文士·演奏创作": (6, 10), "猎户·狩猎": (6, -12), "厨师·采集烹饪": (-38, 8)}
for k, t, s in zip(names, ts, sc): ax.annotate(k.split("·")[0] + ("(APP)" if "APP" in k else ""), (t, s), textcoords="offset points", xytext=offs.get(k, (6, 4)), fontsize=8.5, color=INK)
ax.set_xlabel("日耗时（分钟，次数上限 × 单次估时）"); ax.set_ylabel("产出稀缺度（作者定性 1–5）"); ax.set_title("身份：押镖被 APP 挪出游戏，捕快最重", color=INK, fontsize=12); style(ax)
fig.tight_layout(); fig.savefig(os.path.join(OUT, "ty_daily_budget.png"), dpi=170); plt.close(fig)

fig, ax = plt.subplots(figsize=(9, 3.8))
wk = np.arange(0, 21)
ax.plot(wk, wk * jin_free, color=BLUE, lw=2.2, label=f"免费：{jin_free:.1f} 个/周")
ax.plot(wk, wk * jin_paid, color=GOLD, lw=2.2, label=f"加商城 50/周：{jin_paid:.1f} 个/周")
ax.axhline(need["缘材·进"], color=ICE, ls="--", lw=1); ax.text(0.2, need["缘材·进"] + 8, "一件紫神兵需 296 个缘材·进", color=ICE, fontsize=9)
ax.set_xlabel("周"); ax.set_ylabel("累计缘材·进"); ax.set_title(f"养成周期：免费 {need['缘材·进']/jin_free:.0f} 周，付费 {need['缘材·进']/jin_paid:.1f} 周——付费买的是时间", color=INK, fontsize=12)
ax.legend(frameon=False, fontsize=9); style(ax)
fig.tight_layout(); fig.savefig(os.path.join(OUT, "ty_daily_ascension.png"), dpi=170); plt.close(fig)
print("\ncharts →", OUT)
