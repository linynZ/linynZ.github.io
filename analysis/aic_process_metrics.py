# -*- coding: utf-8 -*-
"""AI Coding 实战过程数据拆解 —— 两份一手日志的度量脚本（v1.1，经独立审核后修订）。

数据源 A：ChronoTraveler 仓库 git 历史（非 merge 提交），--repo 指定本地仓库路径
数据源 B：Claude Code 会话日志 *.jsonl（只做聚合统计，不导出任何对话内容），--logs 指定目录；
          --exclude 排除会话 id 前缀（例如写本文的那个会话，避免自指）

用法：PYTHONUTF8=1 python aic_process_metrics.py --repo <仓库路径> --logs <日志目录> [--exclude id1,id2]
输出：output_aic.txt（本文全部数字）、data/aic_commits.csv（fix 行含主题句与标签；其余行只留前缀/时间/文件数）、
      data/aic_tool_calls.csv、charts/aic_*.png

标注口径（v1.1）：fix 的"缺陷领域"= 作者人工标注，以 REGEX 初标 + LABELS 逐条覆盖的形式固化，便于复核；
"暴露手段"= 人工标注（编译器直接报出 / 其余）。
"""
import argparse, csv, glob, io, json, os, re, statistics as st, subprocess, sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
os.makedirs(os.path.join(HERE, "data"), exist_ok=True); os.makedirs(os.path.join(HERE, "charts"), exist_ok=True)
ap = argparse.ArgumentParser()
ap.add_argument("--repo", default=os.environ.get("AIC_REPO", "."))
ap.add_argument("--logs", default=os.environ.get("AIC_LOGS", ""))
ap.add_argument("--exclude", default=os.environ.get("AIC_EXCLUDE", ""))
A = ap.parse_args()
OUT = []
def P(*a):
    s = " ".join(str(x) for x in a); OUT.append(s); print(s)
def q(a, p): a = sorted(a); return a[min(len(a) - 1, int(p * len(a)))]

# ------------------------------------------------------------------ A. git
def git(*args):
    r = subprocess.run(["git", *args], cwd=A.repo, capture_output=True, encoding="utf-8", errors="replace")
    if r.returncode: sys.exit(f"git failed: {r.stderr}")
    return r.stdout

raw = git("log", "--no-merges", "--date=iso-strict", "--format=@@%h|%ad|%s", "--name-only")
commits = []
for block in raw.split("@@")[1:]:
    head, *files = block.strip("\n").split("\n")
    h, d, s = head.split("|", 2)
    s = re.sub(r"^@\s+", "", s.strip())                     # 两条主题句以 "@ " 开头的笔误
    m = re.match(r"([a-z+\-/]+)(\([^)]*\))?[:：]", s)
    prefix = m.group(1).split("+")[0] if m else "none"
    commits.append(dict(h=h, t=datetime.fromisoformat(d), s=s, files=[f for f in files if f.strip()], prefix=prefix))
commits.sort(key=lambda c: c["t"])
game = [c for c in commits if c["t"].date() <= datetime(2026, 7, 22).date()]   # 游戏本体主开发期；08-10 的 4 条属 NPC Agent 侧
P("=" * 78); P("A. git 过程数据（ChronoTraveler 仓库，非 merge 提交）"); P("=" * 78)
P(f"仓库非 merge 提交 {len(commits)}，{commits[0]['t'].date()} → {commits[-1]['t'].date()}；"
  f"其中游戏本体主开发期（首提交为 ECS 重构前的基线快照，此前约一个月原型期无 git 记录）{len(game)} 条，"
  f"{game[0]['t'].date()} → {game[-1]['t'].date()}，活跃天数 {len(set(c['t'].date() for c in game))}")
pc = Counter(c["prefix"] for c in game)
P("前缀分布（主开发期）：", ", ".join(f"{k} {v}" for k, v in pc.most_common()))
P("说明：提交信息由 agent 生成、作者审阅；fix/feat/polish/tune 的边界由 agent 判断，返工也可能藏在 feat/chore 里（本文不试图还原）。")

# A1. 缺陷领域：正则初标 + 人工逐条覆盖
REGEX = [
    ("编译/API/环境", r"compile|CS0\d{3}|qualify|renamed|node |encoder|编码器|profile|decoder|VP8|H\.264|transcod|vendored|unrunnable|URP|Built-in|magenta|shader|package|codec"),
    ("AI 生成资产质量", r"comfyui|extra-hands|proportion|\brobe\b|outpaint|Hunyuan|answer-position bias|偏置|抠底|splash"),
    ("空间/视觉/布局", r"hover|float|浮空|ground|snap|接地|穿模|spawn|出生点|facing|look|fog|overlap|重叠|floor|placement|grounded|塌缩|seam|winding|culled|ocean|shoreline|beach|horizon|sea |溢出|overflow|height|upright|billboard|lift|raise|clear of|anchor|lane|wall|ramp|plaza|temple|portal ring|立柱|发光|过曝|移出|left of|centre|center|position|size|bounds|crop|压住|皮肤|font|字体|CJK|mirror|orientation|stance|head-up|脱位|交互点|collider|capsule|velocity"),
    ("流程/状态/持久化", r"crash|崩溃|soft-lock|软锁|顺序|replay|重放|repeat|重复|gate|persist|save|存档|timeScale|pause|restore|backfill|clobber|dead-end|loop|leak|never|永远|从未|stuck|reset|self-destruct|re-entry|guard|try/finally|state|状态|事件|volume|un-pause|接线|silent|静默|发不出去|lock|显示|隐藏|show|hide|audio|BGM|cue|theme|chatter|barks|delay|overwrite"),
    ("审核批次（混合）", r"\baudit|审核|\breview\b|pre-ship|封包|correctness batch|compliance"),
    ("文本/术语/本地化", r"terminolog|canon|语序|缩写|\btext\b|文本|wording|术语|i18n|language|中文|English|speaker|台词|统一"),
    ("其他", r"."),
]
# 人工覆盖（独立审核指出的误判逐条改正；"非缺陷" = 数值调整 / 美术升级 / 开发工具功能，移出缺陷统计）
LABELS = {
    "fe86d51": "流程/状态/持久化", "94446fe": "审核批次（混合）", "b9bfdfb": "流程/状态/持久化", "4aae5fb": "空间/视觉/布局",
    "3371929": "流程/状态/持久化", "bf5e378": "流程/状态/持久化", "b93c775": "文本/术语/本地化", "18fb1aa": "流程/状态/持久化",
    "81b6353": "流程/状态/持久化", "f3da6c2": "空间/视觉/布局", "c1b7b70": "流程/状态/持久化", "d679769": "空间/视觉/布局",
    "b1e1570": "审核批次（混合）", "ad2a650": "审核批次（混合）", "c48a042": "审核批次（混合）", "6a8a7d5": "审核批次（混合）",
    "cd366e3": "审核批次（混合）", "9c8d47a": "审核批次（混合）",
    "b21893b": "非缺陷", "aa9835b": "非缺陷", "9507885": "非缺陷",
}
COMPILER = {"76f3f76", "f5ecc43", "81038c1", "22177ad", "d7a36c0"}     # 编译器 / 测试程序集直接报出的
def classify(c):
    if c["h"] in LABELS: return LABELS[c["h"]]
    for k, pat in REGEX:
        if re.search(pat, c["s"], re.I): return k
    return "其他"
fixes_all = [c for c in game if c["prefix"] == "fix"]
for c in fixes_all: c["cat"] = classify(c)
fixes = [c for c in fixes_all if c["cat"] != "非缺陷"]
cat = Counter(c["cat"] for c in fixes)
P(f"\nA1. 缺陷领域：fix 提交 {len(fixes_all)} 条，剔除 {len(fixes_all)-len(fixes)} 条非缺陷（数值调整 / 美术升级 / 工具功能）后 {len(fixes)} 条")
P("   （作者人工标注，以正则初标 + 逐条覆盖的形式固化在脚本里；混合型提交按主要内容归一类）")
for k, v in cat.most_common(): P(f"  {k:<12} {v:>4}  {100*v/len(fixes):5.1f}%")
chains = []; last = None
for c in fixes:
    if last and c["cat"] == last["cat"] and set(c["files"]) & set(last["files"]) and (c["t"] - last["t"]) <= timedelta(days=3):
        chains[-1].append(c)
    else:
        chains.append([c])
    last = c
dcat = Counter(ch[0]["cat"] for ch in chains)
P(f"  按缺陷链去重（同类别 + 与上一条 fix 共享文件 + 间隔 ≤3 天的连续 fix 合并）：{len(chains)} 条链")
for k, v in dcat.most_common(): P(f"  {k:<12} {v:>4}  {100*v/len(chains):5.1f}%")
longest = max(chains, key=len)
P(f"  最长链 {len(longest)} 条 fix：{longest[0]['s'][:44]}… → {longest[-1]['s'][:44]}…")
n_comp = sum(1 for c in fixes if c["h"] in COMPILER); n_state = cat["流程/状态/持久化"]
P(f"\nA1b. 暴露手段（人工标注）：编译器 / 测试程序集直接报出 {n_comp} 条 = {100*n_comp/len(fixes):.0f}%；"
  f"可由测试 / 运行时断言覆盖的流程状态类 {n_state} 条 = {100*n_state/len(fixes):.0f}%；"
  f"其余 {len(fixes)-n_comp-n_state} 条 = {100*(len(fixes)-n_comp-n_state)/len(fixes):.0f}% 依赖目视 / 实机走查（空间视觉、资产质量、文本、环境链路、混合批次）")

# A2. 引入到修复间隔
def interval(mode, skip_docs):
    last_touch = {}; out = []
    for c in game:
        fl = [f for f in c["files"] if not (skip_docs and (f.endswith(".md") or f.startswith("docs/")))]
        if c["prefix"] == "fix" and c.get("cat") not in (None, "非缺陷"):
            prev = [last_touch[f] for f in fl if f in last_touch]
            if prev:
                t0 = max(prev) if mode == "max" else min(prev)
                out.append(((c["t"] - t0).total_seconds() / 3600, c["cat"]))
        for f in fl:
            if c["prefix"] != "fix": last_touch[f] = c["t"]
    return out
P("\nA2. 引入到修复间隔（fix 所触文件距其上一次非 fix 改动的小时数；发现时刻不可观测，此量既非上界也非下界，只用于类别间相对比较）")
P(f"  {'口径':<26} {'n':>4} {'中位':>8} {'P75':>8} {'≤24h':>6}")
res = {}
for mode, sd, name in [("max", False, "最近触碰（含 docs）"), ("max", True, "最近触碰（剔除 docs）"), ("min", False, "最早触碰（含 docs）"), ("min", True, "最早触碰（剔除 docs）")]:
    v = interval(mode, sd); hrs = [x[0] for x in v]; res[name] = v
    P(f"  {name:<26} {len(hrs):>4} {st.median(hrs):>7.1f}h {q(hrs,.75):>7.1f}h {100*sum(1 for x in hrs if x<=24)/len(hrs):>5.0f}%")
cats_order = ["空间/视觉/布局", "流程/状态/持久化", "编译/API/环境", "AI 生成资产质量", "文本/术语/本地化", "审核批次（混合）"]
P("  类别中位（h），四种口径：")
ratio = {}
for k in cats_order:
    row = []
    for name, v in res.items():
        hv = [h for h, kk in v if kk == k]; row.append(st.median(hv) if hv else float("nan"))
    ratio[k] = row
    P(f"  {k:<14}" + "".join(f"{x:>10.1f}h" for x in row) + f"   n={len([1 for h,kk in res['最近触碰（含 docs）'] if kk==k])}")
r_sv = [ratio["流程/状态/持久化"][i] / ratio["空间/视觉/布局"][i] for i in range(4)]
P(f"  流程状态 ÷ 空间视觉 的中位比：{' / '.join(f'{x:.1f}×' for x in r_sv)}")
hrs_main = [x[0] for x in res["最近触碰（剔除 docs）"]]
bins = [0, 1, 3, 8, 24, 72, 168, 720, 10000]; labels = ["<1h", "1–3h", "3–8h", "8–24h", "1–3d", "3–7d", "1–4w", ">4w"]
cnt, _ = np.histogram(hrs_main, bins=bins)
P("  直方（剔除 docs、最近触碰口径）：" + ", ".join(f"{l} {n}" for l, n in zip(labels, cnt)))

# A3. 节奏
hours = Counter(c["t"].hour for c in game)
blocks = []; cur = [game[0]]
for a, b in zip(game, game[1:]):
    if (b["t"] - a["t"]) > timedelta(hours=2): blocks.append(cur); cur = [b]
    else: cur.append(b)
blocks.append(cur)
multi = [b for b in blocks if len(b) > 1]
blen = [(b[-1]["t"] - b[0]["t"]).total_seconds() / 3600 for b in multi]
bl = max(multi, key=lambda b: (b[-1]["t"] - b[0]["t"]).total_seconds()); bc = max(blocks, key=len)
P(f"\nA3. 节奏（提交自带时区 +08:00；提交间隔 >2 h 切块）：{len(blocks)} 块，其中 ≥2 提交的 {len(multi)} 块时长中位 {st.median(blen):.1f} h、块内提交中位 {st.median(len(b) for b in multi):.0f}；"
  f"最长块 {(bl[-1]['t']-bl[0]['t']).total_seconds()/3600:.1f} h（{len(bl)} 提交，{bl[0]['t'].date()}）；提交最多的块 {len(bc)} 提交（{(bc[-1]['t']-bc[0]['t']).total_seconds()/3600:.1f} h，{bc[0]['t'].date()}）；"
  f"日提交最高 {max(Counter(c['t'].date() for c in game).values())}")
night = sum(v for h, v in hours.items() if h >= 22 or h < 6)
P(f"  22:00–06:00 提交占 {100*night/len(game):.0f}%（按提交记录时区）")

# A4. 审核相关提交
aud = re.compile(r"\baudit|审核|\breview\b|走查|playtest|pre-ship|封包", re.I)
audit_all = [c for c in game if aud.search(c["s"]) and not re.search(r"preview", c["s"], re.I)]
audit_fix = [c for c in fixes if aud.search(c["s"])]
P(f"\nA4. 提交信息含 audit / 审核 / review / 走查 / playtest / 封包 的提交 {len(audit_all)} 条（{100*len(audit_all)/len(game):.0f}%，其中论文评审类 docs 提交 {sum(1 for c in audit_all if c['prefix']=='docs')} 条）；fix 中 {len(audit_fix)} 条 = fix 的 {100*len(audit_fix)/len(fixes):.0f}%")

# A5
human = [c for c in fixes if re.search(r"\bQ\d{1,2}\b|实机|走查|playtest|user (Play|report|hand|verification|moved|tuned)|用户", c["s"], re.I)]
P(f"\nA5. 提交信息明确写「由作者本人实机验证 / 走查发现」的 fix {len(human)} 条 = {100*len(human)/len(fixes):.0f}%（下限：只数写明来源的，且取决于 agent 是否写明）")
P("  其中：" + ", ".join(f"{k} {v}" for k, v in Counter(c["cat"] for c in human).most_common()))

with io.open(os.path.join(HERE, "data/aic_commits.csv"), "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f); w.writerow(["hash", "time", "prefix", "label", "compiler_detectable", "n_files", "subject(fix only)"])
    for c in game:
        w.writerow([c["h"], c["t"].isoformat(), c["prefix"], c.get("cat", ""), c["h"] in COMPILER, len(c["files"]), c["s"] if c["prefix"] == "fix" else ""])

# ------------------------------------------------------------------ B. 会话日志
P("\n" + "=" * 78); P("B. 会话日志聚合（Claude Code *.jsonl；只统计，不导出内容）"); P("=" * 78)
tool_stats = defaultdict(lambda: [0, 0]); err_cat = Counter(); sessions = []; versions = Counter()
ERR_TAXO = [
    ("编辑守卫：未先读就写", r"has not been read"),
    ("编辑守卫：读后文件被改", r"modified since read"),
    ("编码 / 转义", r"Unicode|unicodeescape|invalid escape|codec|��"),
    ("路径 / 文件不存在", r"Cannot find path|cannot access|No such file|does not exist|not found in file"),
    ("网络 / 代理（用户侧环境）", r"Exit code (7|28|35)|Socket is closed|HTTP 000|curl"),
    ("权限 / 护栏 / 用户拒绝", r"classifier|is blocked|protected|rejected|Blocked:"),
    ("脚本语法 / 运行时", r"SyntaxError|Traceback|unexpected EOF|parser error"),
    ("依赖 / 命令缺失", r"command not found|No module|not recognized"),
    ("其他 / 仅退出码", r"."),
]
excl = tuple(x for x in A.exclude.split(",") if x)
if A.logs:
    files = [f for f in sorted(glob.glob(os.path.join(A.logs, "*.jsonl"))) if not os.path.basename(f).startswith(excl)]
    id2name = {}
    for f in files:
        s = dict(user_text=0, tools=0, errors=0, interrupts=0, agents=0, t0=None, t1=None, compacts=0)
        for line in open(f, encoding="utf-8", errors="ignore"):
            try: d = json.loads(line)
            except Exception: continue
            ts = d.get("timestamp")
            if ts: s["t0"] = s["t0"] or ts; s["t1"] = ts
            if d.get("isCompactSummary"): s["compacts"] += 1
            if d.get("type") == "assistant" and d.get("version"): versions[d["version"]] += 1
            m = d.get("message")
            if not isinstance(m, dict): continue
            c = m.get("content")
            is_user = d.get("type") == "user" and not d.get("isMeta")
            if isinstance(c, str): texts = [c]
            elif isinstance(c, list): texts = [x.get("text", "") for x in c if isinstance(x, dict) and x.get("type") == "text"]
            else: texts = []
            if is_user:
                for tx in texts:
                    if re.search(r"<command-name>|<local-command", tx): continue
                    s["user_text"] += 1
                    if "[Request interrupted by user" in tx: s["interrupts"] += 1
            if not isinstance(c, list): continue
            for x in c:
                if not isinstance(x, dict): continue
                if x.get("type") == "tool_use":
                    tool_stats[x.get("name")][0] += 1; s["tools"] += 1; id2name[x.get("id")] = x.get("name")
                    if x.get("name") == "Agent": s["agents"] += 1
                if x.get("type") == "tool_result" and x.get("is_error"):
                    s["errors"] += 1
                    n = id2name.get(x.get("tool_use_id"))
                    if n: tool_stats[n][1] += 1
                    cc = x.get("content"); txt = cc if isinstance(cc, str) else " ".join(y.get("text", "") for y in cc if isinstance(y, dict))
                    for k, pat in ERR_TAXO:
                        if re.search(pat, txt): err_cat[k] += 1; break
        sessions.append(s)
    T = sum(v[0] for v in tool_stats.values()); E = sum(v[1] for v in tool_stats.values()); U = sum(s["user_text"] for s in sessions)
    I = sum(s["interrupts"] for s in sessions)
    P(f"会话 {len(sessions)} 个（按启动目录归档，任务混杂：NPC Agent 接入、作品集与拆解案、文档、少量本机运维；已排除 {len(excl)} 个写本文的自指会话），"
      f"{min(s['t0'] for s in sessions)[:10]} → {max(s['t1'] for s in sessions)[:10]}；工具版本 {', '.join(sorted(versions))}")
    P(f"用户文本消息 {U}（已剔除 isMeta 与斜杠命令回显），工具调用 {T}，出错 {E}（{100*E/T:.1f}%），用户打断 {I}（{100*I/U:.1f}%），"
      f"子代理派遣 {sum(s['agents'] for s in sessions)}，上下文压缩 {sum(s['compacts'] for s in sessions)} 次")
    P(f"每条用户消息平均 {T/U:.1f} 次工具调用（无参照值，只作本项目描述）")
    P("\nB1. 工具调用与出错率")
    for n, (u, e) in sorted(tool_stats.items(), key=lambda x: -x[1][0]):
        if u >= 5: P(f"  {n:<16} {u:>5}  err {e:>3}  {100*e/u:5.1f}%")
    P("\nB2. 错误分类（正则命中第一类）")
    for k, v in err_cat.most_common(): P(f"  {k:<28} {v:>3}  {100*v/E:5.1f}%")
    g1 = err_cat["编辑守卫：未先读就写"]; g2 = err_cat["编辑守卫：读后文件被改"]; enc = err_cat["编码 / 转义"]
    P(f"  → 接口摩擦 = 编辑守卫 {g1}+{g2} + 编码/转义 {enc} = {g1+g2+enc} 条 = {100*(g1+g2+enc)/E:.0f}%（每千次调用 {1000*(g1+g2+enc)/T:.0f} 次）；"
      f"其中「未先读就写」{g1} 条是可自动补读的那一类；PowerShell 出错多为 5.1 版语法不兼容（模型知识适配问题，不计入摩擦）")
    with io.open(os.path.join(HERE, "data/aic_tool_calls.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f); w.writerow(["tool", "calls", "errors"])
        for n, (u, e) in sorted(tool_stats.items(), key=lambda x: -x[1][0]): w.writerow([n, u, e])
    P("\nB3. 会话规模（按工具调用数，前 5）")
    for s in sorted(sessions, key=lambda x: -x["tools"])[:5]:
        P(f"  {s['t0'][:10]}  用户消息 {s['user_text']:>3}  工具 {s['tools']:>4}  错 {s['errors']:>2}  打断 {s['interrupts']}  子代理 {s['agents']}")
else:
    P("(未提供 --logs，跳过 B)")

# ------------------------------------------------------------------ charts
try:
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    plt.rcParams["font.family"] = ["Microsoft YaHei", "SimHei", "sans-serif"]; plt.rcParams["axes.unicode_minus"] = False
    BG, GOLD, BLUE, VIOLET, INK = "#100e26", "#e3c07a", "#4fb3e8", "#9d8ff0", "#d9d6ea"
    def style(ax):
        ax.set_facecolor(BG); [s.set_color("#3a3660") for s in ax.spines.values()]
        ax.tick_params(colors=INK); ax.title.set_color(INK); ax.xaxis.label.set_color(INK); ax.yaxis.label.set_color(INK)
    fig, ax = plt.subplots(figsize=(8, 4.2), facecolor=BG); style(ax)
    ks = [k for k, _ in cat.most_common()]; vs = [cat[k] for k in ks]; ds = [dcat[k] for k in ks]
    y = np.arange(len(ks))
    ax.barh(y - 0.2, vs, 0.4, color=BLUE, label="按提交")
    ax.barh(y + 0.2, ds, 0.4, color=GOLD, label="按缺陷链去重")
    ax.set_yticks(y); ax.set_yticklabels(ks); ax.invert_yaxis(); ax.legend(facecolor=BG, labelcolor=INK, edgecolor="#3a3660")
    for i, (v, d) in enumerate(zip(vs, ds)):
        ax.text(v + .5, i - .2, str(v), va="center", color=INK, fontsize=9); ax.text(d + .5, i + .2, str(d), va="center", color=INK, fontsize=9)
    ax.set_title(f"图 1  {len(fixes)} 条缺陷 fix 的领域分布（按提交 vs 按缺陷链去重 {len(chains)} 条）"); ax.set_xlim(0, max(vs) * 1.2)
    fig.tight_layout(); fig.savefig(os.path.join(HERE, "charts/aic_fix_taxonomy.png"), dpi=150, facecolor=BG); plt.close(fig)
    fig, ax = plt.subplots(figsize=(8, 4), facecolor=BG); style(ax)
    ax.bar(labels, cnt, color=BLUE)
    for i, v in enumerate(cnt): ax.text(i, v + .5, str(v), ha="center", color=INK, fontsize=9)
    ax.set_title(f"图 2  引入到修复间隔（剔除 docs、最近触碰口径，n={len(hrs_main)}）：中位 {st.median(hrs_main):.1f} h；注意 3–7 天的第二峰"); ax.set_ylabel("fix 提交数")
    fig.tight_layout(); fig.savefig(os.path.join(HERE, "charts/aic_fix_latency.png"), dpi=150, facecolor=BG); plt.close(fig)
    fig, ax = plt.subplots(figsize=(8, 3.4), facecolor=BG); style(ax)
    ax.bar(range(24), [hours[h] for h in range(24)], color=[VIOLET if (h >= 22 or h < 6) else GOLD for h in range(24)])
    ax.set_xticks(range(0, 24, 2)); ax.set_title("图 3  提交按小时分布（提交记录时区 +08:00；紫 = 22:00–06:00）"); ax.set_ylabel("提交数")
    fig.tight_layout(); fig.savefig(os.path.join(HERE, "charts/aic_cadence.png"), dpi=150, facecolor=BG); plt.close(fig)
    if A.logs and err_cat:
        fig, ax = plt.subplots(figsize=(8, 4.4), facecolor=BG); style(ax)
        ks = [k for k, _ in err_cat.most_common()]; vs = [err_cat[k] for k in ks]
        ax.barh(ks[::-1], vs[::-1], color=[GOLD if ("守卫" in k or "编码" in k) else BLUE for k in ks][::-1])
        for i, v in enumerate(vs[::-1]): ax.text(v + .3, i, str(v), va="center", color=INK, fontsize=9)
        ax.set_title(f"图 4  {E} 次工具出错的分类：金色 = 接口摩擦（守卫 + 编码 / 转义）"); ax.set_xlim(0, max(vs) * 1.25)
        fig.tight_layout(); fig.savefig(os.path.join(HERE, "charts/aic_tool_errors.png"), dpi=150, facecolor=BG); plt.close(fig)
    P("\ncharts → charts/aic_*.png")
except Exception as e:
    P("charts skipped:", e)

io.open(os.path.join(HERE, "output_aic.txt"), "w", encoding="utf-8").write("\n".join(OUT) + "\n")
