# 赵鹏淦 · 游戏策划作品集 / Penggan Zhao — Game Designer Portfolio

线上地址：https://linynz.github.io

## 内容

- **ChronoTraveler** — 独立设计并完成的二次元回合制 RPG（纽卡斯尔大学游戏工程硕士毕业设计，可玩构建已完成，实机演示见站内视频）
- **Cyber Stealth** — 7 人团队谍报潜行游戏（PC + PS5），负责 UI 架构 / 战役积分评级 / 道具装备实装 / 对话系统
- **策划案 × 5**（`cases/`）— 两份 ChronoTraveler 系统策划案、一份 Cyber Stealth 系统策划案、三消十关关卡包、合成游戏七天活动
- **拆解案 × 8**（`cases/`）— 三消关卡步数预算、鸣潮战斗 / 声骸、崩铁遗器、原神新手关卡、合成生成器经济、天刀战斗属性 / 身份日常
- **引擎与底层** — C++ / OpenGL 渲染课程作业（源码公开：linynZ/CSC8502-final-coursework）、课程框架上的物理 / 网络 / AI 作业
- **LLM NPC Agent 与 AIGC 管线** — chrono-npc-agent（开源）

## analysis/

拆解案与策划案的全部计算脚本、数据与图表（Python：numpy / scipy / matplotlib）。每个脚本可独立重跑，`output_*.txt` 为脚本输出、`charts/` 为图、`data/` 为抓取 / 整理后的数据。说明见 `analysis/README.md`。

单页静态站，无构建步骤；`cases/*.html` 由站外脚本从 Markdown 生成。
