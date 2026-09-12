# -*- coding: utf-8 -*-
"""《天涯明月刀》端游 · 身份与日常时间预算拆解案 · 计算脚本（v1.1，两路审核后修订）

数据来自 data/tianya_sources.md：2023-04 官方《升级宝典与必做日常》清单、各身份次数上限（2017/2023）、
有据可查的时长（缉拿"20 分钟足以" 2018——每次/四次总计两种读法并列；论剑场均 61 s 2015；王府乱斗 7.5 分/局 2023；合璧 10 分/局 2022）、
神兵材料需求（2018）与周产出（2018 / 2025 混合口径）。
**标"估"的时长为作者估计**（公开资料没有"完整日常 X 分钟"口径），正文明示；换参数重跑即可。
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


# ---------- 1. 清单与时长：(名称, 分钟, 是否估计, 独立窗口数) ----------
DAILY = [
    ("帮派委任前 10 次", 15, True, 1), ("势力日常 2 个", 10, True, 1), ("师妹排课 / 游历", 3, True, 1), ("别业收水果 / 茶话会", 5, True, 1),
    ("天波府 或 羽林宫", 15, True, 1), ("门派打坐（可存 3 日；减负令可一键）", 5, True, 1), ("怪物阅历（可叠 7 日；减负令可一键）", 10, True, 1),
    ("每日必买 + 商城免费抽（会员 2 项，非会员 1 项）", 2, True, 2), ("游戏外礼包（助手 / 同人 SHOW 签到）", 2, True, 2),
]
WEEKLY = [   # (名称, 周分钟, 其中估计分钟, 窗口数)
    ("话本 6 本（每周刷新）", 120, 120, 1), ("论剑周常 5 场（61 s/场 2015 官方均值 + 估 2 分排队）", 5 * (61 / 60 + 2), 10, 1),
    ("合璧之战周常（10 分/局 官方，估 3 局）", 30, 0, 1), ("战场挑战 / 王府乱斗（7.5 分/局 官方，估 3 局）", 22.5, 0, 1),
    ("宅邸 3 泡澡 3 拜访", 10, 10, 1), ("周三枭野 / 周六天地风云 / 周日天下镖（估 40 分/场）", 120, 120, 3), ("八个周购商店（同一商店界面页签，记 1 窗口）", 10, 10, 1),
]
IDENT = {   # 身份：(次数上限, 单次分钟, 来源, 窗口)
    "捕快·缉拿（20 分钟按每次读）": (4, 20, "4 次/日 官方；2018 攻略'20 分钟足以'", 1),
    "捕快·缉拿（20 分钟按四次总计读）": (4, 5, "同上；同文称捕快'用时少'", 1),
    "镖师·押镖（游戏内）": (10, 3, "10 次/日 官方；估 3 分/次", 1),
    "镖师·押镖（助手 APP）": (10, 0.5, "APP 有押镖入口（2017/2023 官方）；是否同一配额不明；估", 0),
    "游侠·怜花宝藏（5 人）": (8, 6, "8 次/日 官方；估 6 分/次含组队", 1),
    "杀手·悬赏令": (13, 3, "13 次/日 2017；估 3 分/次", 1),
    "乐伶 / 文士·演奏创作": (1, 15, "估", 1), "厨师·采集烹饪": (1, 10, "估", 1), "猎户·狩猎": (1, 15, "半小时刷猎物 官方；估", 1),
}
d_min = sum(x[1] for x in DAILY); d_est = sum(x[1] for x in DAILY if x[2])
w_min = sum(x[1] for x in WEEKLY); w_est = sum(x[2] for x in WEEKLY); w_daily = w_min / 7
print("## 1 时间预算（分钟）")
print(f"  每日必做 9 项合计 {d_min:.0f}（估计 {d_est:.0f}，即 100%）；每周内容 {w_min:.0f}/周（估计 {w_est:.0f}）→ 摊到每日 {w_daily:.0f}")
for name, (n, m, src, win) in IDENT.items(): print(f"  身份 {name:24s} {n:2d} 次 × {m:4.1f} 分 = {n*m:5.1f} 分/日  [{src}]")
profiles = {
    "轻度：只做必做，打坐/阅历用减负令（估）": d_min - 15,
    "中度：必做 + 周常摊薄 + 轻身份（押镖 APP）": d_min + w_daily + 5,
    "中度：必做 + 周常摊薄 + 重身份（游侠 48；捕快 20–80）": d_min + w_daily + 48,
    "重度：全做 + 两重身份（游侠 + 杀手）+ 帮会/论剑加练 60": d_min + w_daily + 48 + 39 + 60,
}
print("  画像（分钟/日）：")
for k, v in profiles.items(): print(f"    {k:44s} {v:5.0f} 分 ≈ {v/60:.1f} h")
half_d = d_min / 2; half_w = (w_min - w_est + w_est / 2) / 7
half_mid_heavy = half_d + half_w + 48 / 2
keys = list(profiles)
print(f"  作者口述：中度、每天 1–2 h、日常全做 + 身份 → 模型中度 {profiles[keys[1]]/60:.1f}（轻身份）–{profiles[keys[2]]/60:.1f} h（重身份）")
print(f"  敏感性：估计项全部砍半 → 必做 {half_d:.0f} 分，中度重身份档 ≈ {half_mid_heavy/60:.1f} h")
S["daily_min"] = d_min; S["weekly_min"] = w_min; S["profiles"] = profiles; S["half_est_mid_heavy_h"] = half_mid_heavy / 60
S["ident"] = {k: dict(n=v[0], per=v[1], total=v[0] * v[1], src=v[2]) for k, v in IDENT.items()}

# ---------- 2. 身份：日耗时 vs 产出稀缺度（作者定性 1–5） ----------
SCARCE = {"捕快·缉拿（20 分钟按每次读）": 4, "捕快·缉拿（20 分钟按四次总计读）": 4, "镖师·押镖（游戏内）": 2, "镖师·押镖（助手 APP）": 2,
          "游侠·怜花宝藏（5 人）": 4, "杀手·悬赏令": 4, "乐伶 / 文士·演奏创作": 3, "厨师·采集烹饪": 3, "猎户·狩猎": 3}
print("\n## 2 身份：日耗时 vs 产出稀缺度（稀缺度为作者定性打分）")
for k, (n, m, src, win) in IDENT.items(): print(f"  {k:24s} 日耗时 {n*m:5.1f} 分  稀缺度 {SCARCE[k]}")

# ---------- 3. 打卡窗口（口径：需要独立操作决策的入口；同一界面页签记 1；手机 APP 各记 1） ----------
daily_win = sum(x[3] for x in DAILY); weekly_win = sum(x[3] for x in WEEKLY); ident_win = 1
per_day = daily_win + ident_win + weekly_win / 7
print("\n## 3 打卡窗口")
print(f"  每日必做 {daily_win} 个（含 2 个手机 APP、2 个商城动作）；周常 {weekly_win} 个 → 摊到每日 {weekly_win/7:.1f}；中度玩家一天 ≈ {per_day:.1f} 个")
print("  对照：本作品集 Gossip Harbor 活动疲劳案的'需操作窗口'日均 5.7（计数规则：需要独立操作决策的入口）")
S["windows"] = {"daily": daily_win, "weekly": weekly_win, "per_day_mid": per_day, "gh_ref": 5.7}

# ---------- 4. 养成周期：一件紫色神兵（材料需求 2018；周产出 2018/2025 混合口径） ----------
need = {"缘材·初": 29640, "缘材·进": 296, "金碎银": 8160, "质料": 240}
free_chu = {"话本 6 本/周（2025）": 2750, "金质帮派礼盒 20/周（2025）": 240, "潜龙之渊海战 3 次/周（2018）": 360, "财星商会日常/周（2018）": 140, "帮派商店周上限（需 10,220 帮贡，2018）": 1120}
free_jin = {"修为商店 5/周（需月耗 1 亿修为，2025）": 5, "神魄商店：周活跃 700 档 500 神魄 + 势力日常 70/周，50 换 1（2025）": 570 / 50}
paid_jin = 50
chu_free = sum(free_chu.values()); chu_noguild = chu_free - 1120
jin_free = sum(free_jin.values()); jin_paid = jin_free + paid_jin
print("\n## 4 一件紫色神兵的周期（秘匣类随机产出未计）")
print(f"  缘材·初 需 {need['缘材·初']}：可量化免费周产 {chu_free:.0f}（不含帮派商店 {chu_noguild:.0f}）→ {need['缘材·初']/chu_free:.1f}–{need['缘材·初']/chu_noguild:.1f} 周")
print(f"  缘材·进 需 {need['缘材·进']}：可量化免费周产 {jin_free:.1f} → {need['缘材·进']/jin_free:.1f} 周；加商城 50/周 → {need['缘材·进']/jin_paid:.1f} 周（等待时间减少 {100*(1-jin_free/jin_paid):.0f}%）")
print(f"  参照：免费口径 1 个缘材·进 ≈ {7/jin_free:.2f} 天的周活跃 + 势力日常 + 修为商店产出；商城阶梯价末 10 个 3,000 绑点/个是劝退价，不作估值")
S["ascension"] = {"need": need, "chu_weeks": [need['缘材·初'] / chu_free, need['缘材·初'] / chu_noguild], "jin_weeks_free": need['缘材·进'] / jin_free, "jin_weeks_paid": need['缘材·进'] / jin_paid, "paid_time_saved": 1 - jin_free / jin_paid}
json.dump(S, open(os.path.join(HERE, "data/ty_daily_summary.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=float)

# ---------- 图 ----------
fig, axs = plt.subplots(1, 2, figsize=(12.5, 4.4))
ax = axs[0]
labels = list(profiles); vals = [v / 60 for v in profiles.values()]
ax.barh([l.split("：")[0] + "\n" + l.split("：")[1][:20] for l in labels], vals, color=[BLUE, GOLD, GOLD, VIOLET])
ax.axvspan(1, 2, color=ICE, alpha=.12); ax.text(1.5, -0.55, "作者口述 1–2 h", color=ICE, fontsize=9, ha="center")
for i, v in enumerate(vals): ax.text(v + .05, i, f"{v:.1f} h", va="center", color=INK, fontsize=9)
ax.invert_yaxis(); ax.set_xlabel("每日时间（小时，含估计项）"); ax.set_title("四种画像的每日时间预算（估计项占多数）", color=INK, fontsize=12); style(ax)
ax = axs[1]
names = list(IDENT); ts = [IDENT[k][0] * IDENT[k][1] for k in names]; sc = [SCARCE[k] for k in names]
ax.scatter(ts, sc, s=80, color=GOLD)
offs = {"乐伶 / 文士·演奏创作": (6, 10), "猎户·狩猎": (6, -12), "厨师·采集烹饪": (-38, 8), "捕快·缉拿（20 分钟按四次总计读）": (6, -12)}
def short(k):
    base = k.split("·")[0]
    if "APP" in k: return base + "(APP)"
    if "每次读" in k: return base + "(每次读)"
    if "总计读" in k: return base + "(总计读)"
    return base
for k, t, s in zip(names, ts, sc): ax.annotate(short(k), (t, s), textcoords="offset points", xytext=offs.get(k, (6, 4)), fontsize=8.5, color=INK)
ax.set_xlabel("日耗时（分钟，次数上限 × 单次估时）"); ax.set_ylabel("产出稀缺度（作者定性 1–5）"); ax.set_title("身份日耗时 vs 产出稀缺度（捕快两种读法并列）", color=INK, fontsize=12); style(ax)
fig.tight_layout(); fig.savefig(os.path.join(OUT, "ty_daily_budget.png"), dpi=170); plt.close(fig)

fig, ax = plt.subplots(figsize=(9, 3.8))
wk = np.arange(0, 21)
ax.plot(wk, wk * jin_free, color=BLUE, lw=2.2, label=f"可量化免费来源：{jin_free:.1f} 个/周")
ax.plot(wk, wk * jin_paid, color=GOLD, lw=2.2, label=f"加商城 50/周：{jin_paid:.1f} 个/周")
ax.axhline(need["缘材·进"], color=ICE, ls="--", lw=1); ax.text(0.2, need["缘材·进"] + 8, "一件紫神兵需 296 个缘材·进（2018 需求）", color=ICE, fontsize=9)
ax.set_xlabel("周"); ax.set_ylabel("累计缘材·进"); ax.set_title(f"养成周期（混合口径）：免费约 {need['缘材·进']/jin_free:.0f} 周，加商城约 {need['缘材·进']/jin_paid:.1f} 周", color=INK, fontsize=12)
ax.legend(frameon=False, fontsize=9); style(ax)
fig.tight_layout(); fig.savefig(os.path.join(OUT, "ty_daily_ascension.png"), dpi=170); plt.close(fig)
print("\ncharts →", OUT)
