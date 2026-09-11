# -*- coding: utf-8 -*-
"""
Gossip Harbor（柠檬微趣 Microfun 合成游戏）fandom wiki 活动（Events）抓取 → data/gh_events.csv
用法：  python gh_events_scrape.py            # 有缓存直接解析；无缓存则抓取
        python gh_events_scrape.py --refresh  # 强制重新抓取所有页
（Windows 请先 set PYTHONUTF8=1 / export PYTHONUTF8=1，避免 gbk 打印报错）

网络：本机直连 fandom.com 不通（含代理直连、api.php、archive.ph 均 000/404），唯一可用镜像 = Wayback：
  curl -s -m 90 -L --compressed -x http://127.0.0.1:21000 -o out.html \
       "https://web.archive.org/web/<year>id_/https://gossip-harbor.fandom.com/wiki/<PageName>"
  快照覆盖极稀疏：CDX 索引 (web.archive.org/cdx/search/cdx?url=gossip-harbor.fandom.com/wiki/*) 只列出约 60 个内容页，
  总览页 /wiki/Events 列出的 37 个活动只有 3 个有独立页快照（Beat_the_Heat_Wipeout / Big_Bubble_Bargains / Easter_Egg_Hunt）。
  抓取遵守：请求间隔 ≥1.2s，失败重试 3 次递增等待，年份 2024→2025→2023→2026 依次回退（2024id_ 实际解析到最近快照 2025-11）。

字段规则：只填页面明确写了的内容；推断放 notes；推不出的留空。
CURATED 表中的字段来自人工阅读缓存 HTML（data/gh_html/，快照 2025-05 ~ 2026-03），来源页在 notes 中用缩写标注。
"""
import csv, html, os, re, subprocess, sys, time, urllib.parse
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
CACHE = os.path.join(DATA, "gh_html")
os.makedirs(CACHE, exist_ok=True)
PROXY = "http://127.0.0.1:21000"
WIKI = "https://gossip-harbor.fandom.com/wiki/"
SNAPSHOT_YEARS = ["2024", "2025", "2023", "2026"]
REFRESH = "--refresh" in sys.argv

# ---------------------------------------------------------------------------
# 页面清单：(slug, 展示名, 总览页分类[多分类用;], 子类型, 来源)
#   来源 overview   = /wiki/Events 总览页列出
#        discovered = 从已存档页面（Multilevel_Events / 主页 What's New / Update_Log / Card_Collection_Event）发现、且有页快照
#        log_only   = 仅见于 Update_Log / 主页 What's New，wiki 上有页但 Wayback 无快照（用于活动时间线/密度）
# ---------------------------------------------------------------------------
PAGES = [
    # Coins
    ("Beat_the_Heat_Wipeout", "Beat the Heat Wipeout", "Coins", "", "overview"),
    ("Lori%E2%80%99s_Dough_Derby", "Lori's Dough Derby", "Coins", "", "overview"),
    ("Ziva%27s_Goldrush", "Ziva's Goldrush", "Coins", "", "overview"),
    # Decoration
    ("A_Marionette%27s_Mission", "A Marionette's Mission", "Decoration", "", "overview"),
    ("An_Egyptian_Excursion", "An Egyptian Excursion", "Decoration", "", "overview"),
    ("Easter_Jamboree", "Easter Jamboree", "Decoration", "", "overview"),
    ("The_Lost_City_of_Heron_Keys", "The Lost City of Heron Keys", "Decoration", "", "overview"),
    ("The_Masked_Tenor", "The Masked Tenor", "Decoration", "", "overview"),
    # Merging / Cloudy
    ("Lavender_Season", "Lavender Season", "Merging", "Cloudy", "overview"),
    ("Tony%27s_Farmyard_Deeds", "Tony's Farmyard Deeds", "Merging", "Cloudy", "overview"),
    ("Tony%E2%80%99s_Fruit_Farm", "Tony's Fruit Farm", "Merging", "Cloudy", "overview"),
    # Merging / Multilevel
    ("Dinosaur_Discovery", "Dinosaur Discovery", "Merging", "Multilevel", "overview"),
    ("Hilarious_Hijinks", "Hilarious Hijinks", "Merging", "Multilevel", "overview"),
    ("Sensational_Sportsfest", "Sensational Sportsfest", "Merging", "Multilevel", "overview"),
    ("Springtide_Gardens", "Springtide Gardens", "Merging", "Multilevel", "overview"),
    # Merging / Digging
    ("Forest_Forager", "Forest Forager", "Merging", "Digging(Scrolling)", "overview"),
    ("Rose_Garden_Romance", "Rose Garden Romance", "Merging", "Digging(Scrolling)", "overview"),
    ("Seaside_Sandscaping", "Seaside Sandscaping", "Merging", "Digging(Scrolling)", "overview"),
    # Merging / Single level
    ("Cinco_de_Mayo_Party", "Cinco de Mayo Party", "Merging", "Single level", "overview"),
    ("Down_the_Rabbit_Hole", "Down the Rabbit Hole", "Merging", "Single level", "overview"),
    ("Easter_Egg_Hunt", "Easter Egg Hunt", "Merging", "Single level", "overview"),
    # Order
    ("Galactic_Grand_Prix", "Galactic Grand Prix", "Order;Random", "", "overview"),
    ("Mutineer_Mayhem", "Mutineer Mayhem", "Order;Random", "", "overview"),
    # Other (+Random)
    ("24-Hour_Player_Competitions", "24-Hour Player Competitions", "Other;Random", "", "overview"),
    ("Big_Drop_Rush", "Big Drop Rush", "Other;Random", "", "overview"),
    ("Bingo", "Bingo", "Other;Random", "", "overview"),
    ("Clay_Color_Combos", "Clay Color Combos", "Other;Random", "", "overview"),
    ("Fruit_Roulette", "Fruit Roulette", "Other;Random", "", "overview"),
    ("Gazebo_Garden_Pools", "Gazebo Garden Pools", "Other;Random", "", "overview"),
    ("Lucky_River", "Lucky River", "Other;Random", "", "overview"),
    ("Restaurant_Goals", "Restaurant Goals", "Other", "", "overview"),
    ("Sky-High_Scramble", "Sky-High Scramble", "Other;Random", "", "overview"),
    # Purchasing (+Random)
    ("Big_Bubble_Bargains", "Big Bubble Bargains", "Purchasing;Random", "", "overview"),
    ("Disco_Party", "Disco Party", "Purchasing;Random", "", "overview"),
    ("Rare_Card_Deal", "Rare Card Deal", "Purchasing;Random", "", "overview"),
    # Rare and Obsolete
    ("Coconut%27s_Sky_Journey", "Coconut's Sky Journey", "Rare and Obsolete", "", "overview"),
    ("Rare_and_Obsolete_Events", "Kitchen Merging Events (类型, 总览页未列具体活动名)", "Rare and Obsolete", "Kitchen Merging", "overview"),
    # 已存档但总览页未列出的活动页
    ("Purrfect_Pet_Party", "Purrfect Pet Party", "Merging", "Multilevel", "discovered"),
    ("Tony%E2%80%99s_Bravery_Test", "Tony's Bravery Test", "Merging", "Cloudy", "discovered"),
    ("Fortune_Favors_the_Bold", "Fortune Favors the Bold", "Decoration", "", "discovered"),
    ("Tidal_Beats_Fest", "Tidal Beats Fest", "", "", "discovered"),
    ("Card_Collection_Event", "Card Collection Event", "", "", "discovered"),
    ("Seasons", "Seasons (赛季通行证)", "", "", "discovered"),
    ("Endless_Energy", "Endless Energy", "", "", "discovered"),
    # 仅见于 Update_Log / What's New，wiki 有页但无快照
    ("Purrfect_Progress", "Purrfect Progress", "Merging", "", "log_only"),
    ("The_Dark_Zone", "The Dark Zone", "", "", "log_only"),
    ("A_Spectral_Shindig", "A Spectral Shindig", "", "", "log_only"),
    ("All_Hallows_Haunts", "All Hallows Haunts", "", "", "log_only"),
    ("Puzzles", "Puzzles", "", "", "log_only"),
    ("The_Mage%E2%80%99s_Fortune", "The Mage's Fortune", "", "", "log_only"),
    ("Flower_Fellowship", "Flower Fellowship", "", "", "log_only"),
    ("Fall_Foliage_Favors", "Fall Foliage Favors", "", "", "log_only"),
    ("Golden_Moon_Banquet", "Golden Moon Banquet", "Decoration", "", "log_only"),
    ("Water_Rival_Race", "Water Rival Race", "", "", "log_only"),
    ("Happy_Campers", "Happy Campers", "", "", "log_only"),
    ("Roadtrip_Dreams", "Roadtrip Dreams", "", "", "log_only"),
    ("Pups_and_Paintings", "Pups and Paintings", "", "", "log_only"),
    ("Scuba_Diving_Summer", "Scuba Diving Summer", "", "", "log_only"),
    ("Barking_Bobbies", "Barking Bobbies", "Decoration", "", "log_only"),
    ("Double_Pack_Party", "Double Pack Party", "", "", "log_only"),
    ("Restaurant_Recon", "Restaurant Recon", "", "", "log_only"),
    ("Tony%E2%80%99s_Panda_Posse", "Tony's Panda Posse", "", "", "log_only"),
    ("The_Joker", "The Joker", "", "", "log_only"),
    ("Heart2Heart", "Heart2Heart", "", "", "log_only"),
    ("Besties%E2%80%99_Shopping_Day", "Besties' Shopping Day", "", "", "log_only"),
    ("Birthday_Party", "Birthday Party", "Card Collection (album)", "", "log_only"),
    ("Triennial_Triumph", "Triennial Triumph", "Decoration", "", "log_only"),
    ("Norman%E2%80%99s_Monster_Hunt", "Norman's Monster Hunt", "", "", "log_only"),
    ("Tony%27s_Vineyard_Ventures", "Tony's Vineyard Ventures", "Merging", "", "log_only"),
    ("Tour_the_Cosmos", "Tour the Cosmos", "Card Collection (album)", "", "log_only"),
    ("Easter_Egg_Quest", "Easter Egg Quest", "", "", "log_only"),
    ("Easter_Festival_Face_Off", "Easter Festival Face Off", "Other", "", "log_only"),
    ("Easter_Get-together", "Easter Get-together", "Card Collection (album)", "", "log_only"),
    ("Joyful_Moments", "Joyful Moments", "Card Collection (album)", "", "log_only"),
    ("Destination_Dreamland", "Destination Dreamland", "", "", "log_only"),
    ("Energy_Challenge", "Energy Challenge", "", "", "log_only"),
    ("Coconut%E2%80%99s_Fishy_Farming", "Coconut's Fishy Farming", "", "", "log_only"),
    ("24-Hour_Decoration_Point_Events", "24-Hour Decoration Point Events", "", "", "log_only"),
    ("Event_Point_Player_Competitions", "Event Point Player Competitions", "", "", "log_only"),
]

# 辅助页（不产生 CSV 行，只用于取证）
AUX_PAGES = ["Events", "Multilevel_Events", "Update_Log", "Event_Calendar", "Tips_and_Tricks",
             "Gossip_Harbor_Wiki", "Raccoon", "Game_Mechanics", "Timers"]

CAT_MAP = {  # 总览页 h2/h3 标题 → (category, subcategory)
    "Coins Events": ("Coins", ""), "Decoration Events": ("Decoration", ""),
    "Merging Events": ("Merging", ""), "Cloudy Events": ("Merging", "Cloudy"),
    "Multilevel Events": ("Merging", "Multilevel"), "Digging Events": ("Merging", "Digging(Scrolling)"),
    "Single level events": ("Merging", "Single level"), "Order Events": ("Order", ""),
    "Other Events": ("Other", ""), "Purchasing Events": ("Purchasing", ""), "Random Events": ("Random", ""),
    "Rare and Obsolete Events": ("Rare and Obsolete", ""), "Kitchen Merging Events": ("Rare and Obsolete", "Kitchen Merging"),
}


# ---------------------------------------------------------------------------
# 抓取与解析工具
# ---------------------------------------------------------------------------
def cache_path(slug):
    name = urllib.parse.unquote(slug).replace("’", "'").replace("/", "_").replace(":", "_")
    return os.path.join(CACHE, name + ".html")


def fetch(slug):
    """Wayback 镜像抓取 + 本地缓存。返回 HTML 或 None（无快照，写 .404 标记文件避免重复请求）。"""
    path = cache_path(slug)
    if os.path.exists(path) and not REFRESH and os.path.getsize(path) > 2000:
        return open(path, encoding="utf-8", errors="ignore").read()
    miss = path + ".404"
    if os.path.exists(miss) and not REFRESH:
        return None
    for year in SNAPSHOT_YEARS:
        url = f"https://web.archive.org/web/{year}id_/{WIKI}{slug}"
        for attempt in range(3):
            time.sleep(1.2 + attempt * 2)
            tmp = path + ".tmp"
            r = subprocess.run(["curl", "-s", "-m", "90", "-L", "--compressed", "-x", PROXY,
                                "-o", tmp, "-w", "%{http_code}", url], capture_output=True, text=True)
            code = r.stdout.strip()
            if code == "200" and os.path.exists(tmp) and os.path.getsize(tmp) > 2000:
                txt = open(tmp, encoding="utf-8", errors="ignore").read()
                if "mw-parser-output" in txt:
                    os.replace(tmp, path)
                    print(f"  [ok] {slug} ({year}, {os.path.getsize(path)} B)")
                    return txt
            if code == "404":
                break  # 该年份无快照 → 换年份
            print(f"  [retry {attempt + 1}] {slug} {year} code={code}")
        if os.path.exists(path + ".tmp"):
            os.remove(path + ".tmp")
    open(miss, "w").write("no wayback snapshot\n")
    print(f"  [no snapshot] {slug}")
    return None


def strip(s):
    s = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", s, flags=re.S)
    s = re.sub(r"</(p|li|tr|h[1-6]|div|table|dd|dt)>", "\n", s)
    s = re.sub(r"</t[dh]>", " | ", s)
    s = re.sub(r"<br\s*/?>", "\n", s)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s).replace("\xa0", " ")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n\s*\n+", "\n", s)
    return s.strip()


def body_of(doc):
    m = re.search(r'<div class="[^"]*mw-parser-output[^"]*"[^>]*>', doc)
    if not m:
        return ""
    rest = doc[m.end():]
    ends = [e for e in (rest.find(x) for x in ("Saved in parser cache", "NewPP limit report",
            '<div class="page-footer', 'id="mw-data-after-content"', 'class="global-footer"')) if e > 0]
    return rest[:min(ends)] if ends else rest


def first_paragraph(doc):
    body = body_of(doc)
    body = re.sub(r"<(aside|table)[^>]*>.*?</\1>", " ", body, flags=re.S)
    for p in re.findall(r"<p>(.*?)</p>", body, flags=re.S):
        t = re.sub(r"\s+", " ", strip(p)).strip()
        if len(t) > 25:
            return t[:400]
    return ""


def infobox_pairs(doc):
    """portable-infobox / wikia-infobox 键值对（本 wiki 活动页均无信息框，保留以备重跑）"""
    body = body_of(doc)
    out = []
    for m in re.finditer(r'<(aside|table)[^>]*class="[^"]*(?:portable-infobox|wikia-infobox|infobox)[^"]*"[^>]*>(.*?)</\1>', body, re.S):
        frag = m.group(2)
        for k, v in re.findall(r'<h3[^>]*pi-data-label[^>]*>(.*?)</h3>\s*<div[^>]*pi-data-value[^>]*>(.*?)</div>', frag, re.S):
            out.append((strip(k), strip(v)))
        for k, v in re.findall(r"<th[^>]*>(.*?)</th>\s*<td[^>]*>(.*?)</td>", frag, re.S):
            out.append((strip(k), strip(v)))
    return out


def parse_overview_descs(doc):
    body = body_of(doc)
    parts = re.split(r"(<h[23][^>]*>.*?</h[23]>)", body, flags=re.S)
    descs = []
    for i in range(1, len(parts), 2):
        h = re.sub(r"\[.*?\]\s*$", "", strip(parts[i])).strip()
        if h not in CAT_MAP:
            continue
        sec = re.sub(r"<ul>.*?</ul>", " ", parts[i + 1], flags=re.S)  # 去掉活动链接列表，留说明文字
        sec = re.sub(r"<figure.*?</figure>", " ", sec, flags=re.S)
        text = re.sub(r"\s+", " ", strip(sec)).strip()
        descs.append((h, CAT_MAP[h], text))
    return descs


# ---------------------------------------------------------------------------
# 人工阅读缓存页面后提取的字段（只写页面明确说明的内容；推断标 notes）
# 来源缩写：[EV]=总览页 Events, [TT]=Tips_and_Tricks, [UL]=Update_Log, [EC]=Event_Calendar,
#          [MP]=主页 What's New/Event Calendar(2025-11-01 快照), [ML]=Multilevel_Events, [PG]=活动自身页面
# ---------------------------------------------------------------------------
COIN_DUR = "3-4 days (Fri 10:00 GMT start → Mon 10:00 GMT end [MP]; Event_Calendar 页写 Tue 10:00 [EC])"
MERGE_REWARD = "道具等级里程碑奖励(金块/硬币/能量/宝石碎片, 主道具 lv5 起)+图鉴每新发现道具 +1 能量; 完成活动给卡包 [ML][TT]"
MERGE_NOTE = "合成活动时长页面未写; 同一时间只能有一个合成活动, 结束后可立即开下一个或间隔≥2h [EV]"
OTHER_DUR = "24 hours (分类级描述: Other 类'often 24-hour events' [EV])"
DECO_MECH = "用订单产出的 Decoration Points 按阶段购买公园广场/Quinn 花园的永久装饰; 阶段 2 后获 Cooldown Perk [EV][TT][Timers]"
DECO = dict(duration="", is_competitive="false", competition_form="个人里程碑", reward_structure="按阶段解锁装饰(分类级描述)",
            main_mechanic=DECO_MECH, reuse_count="", first_seen="", requires_purchase="false")
MERGE = dict(duration="", is_competitive="false", competition_form="个人里程碑", reward_structure=MERGE_REWARD,
             reuse_count="", first_seen="", requires_purchase="false")
OTHER = dict(duration=OTHER_DUR, is_competitive="unknown", competition_form="", reward_structure="",
             main_mechanic="", reuse_count="", first_seen="", requires_purchase="false")

CURATED = {
    "Beat the Heat Wipeout": dict(duration=COIN_DUR, is_competitive="true", competition_form="排行榜(每轮与其他玩家赛跑, 前三名)",
        reward_structure="12 轮, 每轮前 1/2/3 名奖励(礼盒/能量/硬币/宝石/箱子), 硬币不跨轮结转 [PG]",
        main_mechanic="厨房板攒硬币达每轮硬币目标(新版 250→1000), 与其他玩家比谁先到 [PG]",
        reuse_count="2", first_seen="", requires_purchase="false",
        notes="reuse=页面并列 New Version/Old Version 两套轮次表; 不每周出现, 可在周五 10am GMT 出现, 与 Lori's Dough Derby/Ziva's Goldrush 轮流占周五档 [PG][MP]; wiki 文章创建 2025-04-24 [UL]"),
    "Lori's Dough Derby": dict(duration=COIN_DUR, is_competitive="false", competition_form="个人里程碑(与 NPC Lori 赛跑, 非玩家对抗)",
        reward_structure="按轮次硬币目标发奖, 硬币可跨轮结转 [TT]",
        main_mechanic="攒硬币与 Lori 赛跑过轮 [TT]", reuse_count="2", first_seen="", requires_purchase="false",
        notes="无页快照; reuse=Update_Log 2025-07-24 记'部分玩家有新版本, 页面数值基于旧版'; 2025-05-01 加了'回归时间表'以追踪复刻 [UL]; 文章创建 2025-04-11"),
    "Ziva's Goldrush": dict(duration=COIN_DUR, is_competitive="true", competition_form="排行榜(与其他玩家赛跑)",
        reward_structure="按轮次硬币目标发奖, 硬币不跨轮结转 [TT]",
        main_mechanic="攒硬币达轮次目标, 与其他玩家赛跑 [TT]", reuse_count="", first_seen="", requires_purchase="false",
        notes="无页快照; 主页 2025-10-24/26 记'正在更新新的奖励与硬币信息'(疑似改版, 未明说) [MP]"),
    "A Marionette's Mission": dict(DECO, notes="无页快照; 公园广场装饰活动 [EV]; 其装饰条目 2025-08-08 建 [UL]"),
    "An Egyptian Excursion": dict(DECO, notes="无页快照; 公园广场 [EV]; 装饰条目 2025-08-07 建 [UL]; Horus's Guard 页确认为其装饰"),
    "Easter Jamboree": dict(DECO, notes="无页快照; Quinn 花园装饰活动(少见类型) [EV]; 文章创建 2025-04-10(复活节档) [UL]"),
    "The Lost City of Heron Keys": dict(DECO, notes="无页快照; 公园广场 [EV]; 文章创建 2025-05-09, 05-12 补齐全部奖励 [UL]"),
    "The Masked Tenor": dict(DECO, notes="无页快照; 公园广场 [EV]; 文章创建 2025-06-10 [UL]; Ghostly Gondola 页确认为其装饰"),
    "Lavender Season": dict(MERGE, main_mechanic="云雾板: 按固定顺序用钥匙道具解锁云区; 主合成物=植物, 用订单给的镰刀收割(最多 4 块地) [EV]",
        notes="无页快照; " + MERGE_NOTE + "; 文章创建 2025-05-12 [UL]"),
    "Tony's Farmyard Deeds": dict(MERGE, main_mechanic="云雾板(动物+地块+镰刀), 总览页配图示例 [EV]", notes="无页快照; " + MERGE_NOTE),
    "Tony's Fruit Farm": dict(MERGE, main_mechanic="云雾板(植物/镰刀) [EV]", notes="无页快照; " + MERGE_NOTE + "; 文章创建 2025-04-04, 2025-09-06 补图 [UL]"),
    "Dinosaur Discovery": dict(MERGE, reward_structure=MERGE_REWARD + "; 阶段 2/3/4 开局铺满硬币/能量/宝石碎片 [ML]",
        main_mechanic="多层板: 4 层, 合出带钥匙标记的道具开门进下一层 [EV]",
        notes="无页快照; 总览页配图'第 4 层也是最后一层'; " + MERGE_NOTE + "; 文章创建 2025-04-25 [UL]"),
    "Hilarious Hijinks": dict(MERGE, main_mechanic="多层板(4 层, 钥匙开门) [EV]", notes="无页快照; " + MERGE_NOTE),
    "Sensational Sportsfest": dict(MERGE, main_mechanic="多层板(4 层, 钥匙开门) [EV]", notes="无页快照; " + MERGE_NOTE + "; 文章创建 2025-05-21 [UL]"),
    "Springtide Gardens": dict(MERGE, main_mechanic="多层板(4 层, 钥匙开门), 总览页配图 [EV]", notes="无页快照; " + MERGE_NOTE),
    "Forest Forager": dict(MERGE, reward_structure="积分制: 达到积分阈值给道具奖励 [EV]",
        main_mechanic="挖掘板: 清完现有道具后板面向下滚动露出更多 [EV]", notes="无页快照; " + MERGE_NOTE + "; 文章创建 2025-05-30 [UL]"),
    "Rose Garden Romance": dict(MERGE, reward_structure="积分制: 达到积分阈值给道具奖励 [EV]", main_mechanic="挖掘板(向下滚动) [EV]", notes="无页快照; " + MERGE_NOTE),
    "Seaside Sandscaping": dict(MERGE, reward_structure="积分制: 达到积分阈值给道具奖励 [EV]", main_mechanic="挖掘板(向下滚动) [EV]", notes="无页快照; " + MERGE_NOTE),
    "Cinco de Mayo Party": dict(MERGE, main_mechanic="单层板: 用订单给的可合成物与板上预置道具合成到顶级即结束 [EV]",
        notes="无页快照; " + MERGE_NOTE + "; 文章创建 2025-05-04 [UL]; Raccoon 页提到'Cinco de Mayo Party Points'即订单给活动点"),
    "Down the Rabbit Hole": dict(MERGE, main_mechanic="单层板 [EV]", notes="无页快照; " + MERGE_NOTE + "; 文章创建 2025-06-10 [UL]"),
    "Easter Egg Hunt": dict(MERGE, reward_structure="蛋链 lv5-7 产金块/硬币/能量 [PG]; " + MERGE_REWARD,
        main_mechanic="单层板: 胡萝卜链+彩蛋链两条合成链 [PG][EV]",
        notes="有页快照但仅道具等级表, 无时长/日期; 文章创建 2025-04-13 [UL]; " + MERGE_NOTE),
    "Galactic Grand Prix": dict(duration="", is_competitive="unknown", competition_form="", reward_structure="",
        main_mechanic="订单活动: 完成指定订单 [EV]; 随机活动(不提前 24h 预告) [EV]", reuse_count="", first_seen="", requires_purchase="false",
        notes="无页快照; 文章创建 2025-04-15 [UL]"),
    "Mutineer Mayhem": dict(duration="<24 hours (随机类说明: Raccoon orders 与 Mutineer Mayhem 不足 24h [EV])", is_competitive="unknown", competition_form="", reward_structure="",
        main_mechanic="限时特殊订单活动, 3 个版本各有一套可能订单组合 [UL 2025-05-27]; 到达时段 Tue/Wed/Thu 00:00-02:00 GMT [MP][EC]",
        reuse_count="3", first_seen="", requires_purchase="false",
        notes="无页快照; reuse=Update_Log 记 3 个版本; 每周最多 3 个到达时段 [MP]"),
    "24-Hour Player Competitions": dict(duration="24 hours (活动名即 24 小时 [EV])", is_competitive="true", competition_form="排行榜(玩家竞赛, 按名次发奖)",
        reward_structure="按名次奖励 [UL 2025-04-20: '奖励与名次基于当期 Easter Festival Face Off, 待验证']",
        main_mechanic="24 小时内完成订单/攒积分与其他玩家比名次 [EV]", reuse_count="", first_seen="", requires_purchase="false",
        notes="无页快照; 具体实例名 Easter Festival Face Off(2025-04) [UL]; wiki 另有 Event_Point_Player_Competitions 页(无快照)"),
    "Big Drop Rush": dict(OTHER, reward_structure="完成订单/积分给奖励(分类级) [EV]", notes="无页快照; 文章创建 2025-05-27 [UL]; 随机活动"),
    "Bingo": dict(OTHER, reward_structure="完成订单/积分给奖励(分类级) [EV]", main_mechanic="可从厨房板进入的活动界面 [TT]", notes="无页快照; 文章创建 2025-06-15 [UL]; 随机活动"),
    "Clay Color Combos": dict(OTHER, reward_structure="按轮次(所需颜料瓶数/要上色的动物)发奖 [UL 2025-05-18]",
        main_mechanic="收集颜料瓶给陶土动物雕像上色, 分轮推进 [UL]", notes="无页快照; Update_Log 2025-05-18 记有轮次/颜料/动物/奖励表, 2025-07-23 加全部雕像图"),
    "Fruit Roulette": dict(OTHER, main_mechanic="可从厨房板进入的活动界面 [TT]", notes="无页快照; 文章创建 2025-06-06 [UL]; 随机活动"),
    "Gazebo Garden Pools": dict(OTHER, notes="无页快照; Event_Calendar: 周四 2am/合成活动最后 24 小时出现(待验证) [EC]"),
    "Lucky River": dict(OTHER, notes="无页快照; 文章创建 2025-04-15 [UL]; Tips 页有空标题段"),
    "Restaurant Goals": dict(duration="1 week (结束后立刻重开 [EV]; 周一/二 2am GMT 重置 [MP][EC])", is_competitive="false", competition_form="个人里程碑",
        reward_structure="多条目标(含收集 N 个 Epic/Rare 卡包、'完成一次购买'等)+里程碑奖励, 完成总奖励几乎必含 Epic Pack [TT][Card_Collection_Event]",
        main_mechanic="周任务清单: 完成订单/收卡包/登录等目标 [TT]", reuse_count="", first_seen="", requires_purchase="false",
        notes="无页快照; 目标之一是'make a purchase'(可跳过该项拿其余奖励) [TT]; 常驻每周循环"),
    "Sky-High Scramble": dict(OTHER, notes="无页快照; 2025-07-23 更新 [UL]; 随机活动"),
    "Big Bubble Bargains": dict(duration="24 hours [PG]", is_competitive="false", competition_form="无", reward_structure="无奖励结构(泡泡道具折扣) [PG]",
        main_mechanic="24 小时内厨房板泡泡(bubble)道具打折出售 [PG]", reuse_count="3", first_seen="", requires_purchase="true",
        notes="reuse=页面到达时段表每周 3 档(Tue 2am / Wed 10 GMT 与 1 GMT / Sat 2am GMT), 非版本数; 分类=需真钱 [EV]; 随机活动"),
    "Disco Party": dict(duration="(非 24 小时, 分类说明将其列为例外 [EV])", is_competitive="false", competition_form="无", reward_structure="抽奖(转盘): Coconut 送 1 次免费转保底 25 能量, 其余转需付费 [EV]",
        main_mechanic="付费转盘抽奖 [EV]", reuse_count="", first_seen="", requires_purchase="true",
        notes="无页快照; 2025-08-16 概率与奖励从 wiki 移除, 改链接 Microfun 概率公示 [UL]"),
    "Rare Card Deal": dict(duration="", is_competitive="false", competition_form="无", reward_structure="付费购买稀有卡(分类级) [EV]",
        main_mechanic="真钱购买 [EV]", reuse_count="", first_seen="", requires_purchase="true", notes="无页快照; 文章创建 2025-08-24 [UL]; 随机活动"),
    "Coconut's Sky Journey": dict(duration="", is_competitive="unknown", competition_form="", reward_structure="", main_mechanic="",
        reuse_count="", first_seen="", requires_purchase="", notes="无页快照; 总览页'已不再出现'的活动 [EV]"),
    "Kitchen Merging Events (类型, 总览页未列具体活动名)": dict(duration="", is_competitive="unknown", competition_form="", reward_structure="",
        main_mechanic="在游戏初期脏乱厨房板的复制板上做合成, 为平时不点单的角色(Sophia/Quinn)做订单 [EV]", reuse_count="", first_seen="", requires_purchase="",
        notes="已淘汰活动类型; Rare_and_Obsolete_Events 分类页无快照, 无具体活动名"),
    # discovered
    "Purrfect Pet Party": dict(MERGE, reward_structure="Cat Care Tools 链 lv5-12、Furry Friends 链 lv5-6 等级奖励(与通用多层活动表一致) [PG]",
        main_mechanic="多层板合成活动 [PG]", notes="总览页未列; 文章创建 2025-11-02 [MP]; 主页记'单层与多层合成活动奖励相同'"),
    "Tony's Bravery Test": dict(MERGE, reward_structure="Giggling Ghosts lv5-10 / Mystic Manuals lv4-8 等级奖励, 箱子/幽灵坩埚给道具 [PG]",
        main_mechanic="云雾板合成活动(万圣节题材: 幽灵/魔法书/蜘蛛饼干, 用镰刀挖墓) [PG]", notes="总览页未列; 文章创建 2025-10-23 [MP]"),
    "Fortune Favors the Bold": dict(DECO, reward_structure="8 个阶段, 每阶段 3 件装饰(共 24 件) [PG]", main_mechanic="公园广场装饰活动 [PG]; " + DECO_MECH,
        first_seen="2026-02", notes="页面原文'was the February 2026 decoration event for the Park Square' → 装饰活动按月一档; 快照 2026-03-27"),
    "Tidal Beats Fest": dict(duration="", is_competitive="true", competition_form="排行榜(分 Newcomer/Apprentice 等段位阶段, 各阶段前三名)",
        reward_structure="每阶段 1st/2nd/3rd 名奖励(Fancy Order Case/刮刮卡/能量 75-150) [PG]", main_mechanic="页面未写玩法, 仅奖励表",
        reuse_count="", first_seen="", requires_purchase="false", notes="总览页未列; 文章创建 2025-10-25 [MP]; 类型未写(疑似玩家竞赛类)"),
    "Card Collection Event": dict(duration="over a month [PG]", is_competitive="false", competition_form="个人里程碑",
        reward_structure="集齐 9 张/套得奖; 集满相册可再刷 Prestige Album(第二轮)得 Generous Pack; 重复卡在 Star Store 换包 [PG]",
        main_mechanic="通过订单/活动/Restaurant Goals/Seasons 获得卡包集卡 [PG]", reuse_count="4", first_seen="", requires_purchase="false",
        notes="总览页未列(归 Game Mechanics); reuse=已知相册名: Easter Get-together、Joyful Moments [PG] + Tour the Cosmos、Birthday Party [UL]; 期间未用重复卡不结转"),
    "Seasons (赛季通行证)": dict(duration="1 month [PG]", is_competitive="false", competition_form="个人里程碑",
        reward_structure="免费轨+VIP Pass/Super Pass 付费轨; 45 级积分里程碑(lv2=110 … lv42=7000); 免费轨固定送 1 Energy Chest, VIP 送 150 能量 [PG]",
        main_mechanic="24 小时限时任务(赚硬币/服务顾客/花宝石)+累计合成 100 次得积分升级 [PG]", reuse_count="2", first_seen="", requires_purchase="false",
        notes="总览页未列(归 Game Mechanics); reuse=页面截图 Sep-Oct 2025 与 Oct-Nov 2025 两季; 奖励每季变动(2025-06-24 起不再固定) [UL]; 付费通行证可选"),
    "Endless Energy": dict(duration="", is_competitive="false", competition_form="个人里程碑",
        reward_structure="15 轮阶梯: 免费卡包/能量与付费能量交替, 100 能量售价 10→20→40→80→160 宝石 [PG]",
        main_mechanic="花宝石买能量并解锁后续免费奖励 [PG]; 周二/三 00:00 GMT 出现 [PG]", reuse_count="", first_seen="", requires_purchase="false",
        notes="总览页未列; 需消耗宝石(游戏内货币, 可付费获得)但非强制真钱; 有卡牌活动期间奖励换成卡包 [PG]; 文章创建 2025-04-15 [UL]"),
    # log_only（时间线证据）
    "Purrfect Progress": dict(notes="页面 2025-10-19~20 创建, 10-21 补齐全部目标与奖励 [UL]; 主页记其奖励与单层/多层合成活动相同 → 合成活动"),
    "The Dark Zone": dict(notes="页面 2025-10-19~20 创建 [UL]"),
    "A Spectral Shindig": dict(notes="页面 2025-10-17~18 创建(万圣节档) [UL]"),
    "All Hallows Haunts": dict(notes="页面 2025-10-23 创建 [MP]"),
    "Puzzles": dict(notes="2025-10-23 创建, 10-24 补齐'第一个 puzzle'全部奖励 [MP]"),
    "The Mage's Fortune": dict(notes="2025-10-25 创建 [MP]"),
    "Flower Fellowship": dict(notes="2025-10-10~16 更新(与 Cloudy/Digging Events 页同批更新, 类型未明) [UL]"),
    "Fall Foliage Favors": dict(notes="2025-09-18~10-07 创建(同批更新 Digging Event 页, 类型未明) [UL]"),
    "Golden Moon Banquet": dict(notes="2025-09-18~10-07 '添加了若干装饰' → 装饰活动(中秋档) [UL]"),
    "Water Rival Race": dict(is_competitive="true", competition_form="排行榜(轮次含 1st place 奖励)",
        notes="2025-08-28 创建, 08-29 '除第 1 轮与第 7 轮一个 1st place 奖励外全部奖励已加' → ≥7 轮按名次 [UL]; 主页 10-26 记其活动点计算方式与其他活动不同"),
    "Happy Campers": dict(notes="2025-09-13 创建 [UL]"),
    "Roadtrip Dreams": dict(notes="2025-09-07 创建 [UL]"),
    "Pups and Paintings": dict(notes="2025-09-05 创建 [UL]"),
    "Scuba Diving Summer": dict(notes="2025-09-04 '全部 undersea buddies 已加' [UL]"),
    "Barking Bobbies": dict(notes="2025-08-28 创建, 09-04 '其装饰条目已加' → 装饰活动 [UL]"),
    "Double Pack Party": dict(notes="2025-08-24 与 Rare Card Deal 同日创建(类型未明) [UL]"),
    "Restaurant Recon": dict(notes="2025-08-11 创建; 08-15 '寿司全部奖励已加, 缺最后 trinket'; 08-21 全部道具配图(类型未明) [UL]"),
    "Tony's Panda Posse": dict(notes="2025-08-20 创建(Tony 系列此前均为云雾板, 本活动类型未明) [UL]"),
    "The Joker": dict(notes="2025-08-17 创建 [UL]"),
    "Heart2Heart": dict(notes="2025-08-17 创建 [UL]"),
    "Besties' Shopping Day": dict(notes="2025-08-12 创建, '多数玩家没有拿到这个活动'(疑似分组投放/AB 测试) [UL]"),
    "Birthday Party": dict(notes="2025-08-11 创建, 08-15 '加了若干卡' → 卡牌收集相册(3 周年档) [UL]"),
    "Triennial Triumph": dict(notes="2025-08-08 创建, 08-09 '阶段 1-3 全部装饰已建' → 装饰活动(3 周年) [UL]; Luminous Ducks 页确认为其装饰"),
    "Norman's Monster Hunt": dict(notes="2025-07-26 创建, 07-27~28 '更多积分信息' → 积分制 [UL]"),
    "Tony's Vineyard Ventures": dict(notes="2025-07-17 创建(活动尚未开始), 07-27~28 '活动已结束…活动复用 sprite' → 合成活动 [UL]"),
    "Tour the Cosmos": dict(notes="2025-07-14 加卡图 → 卡牌收集相册 [UL]"),
    "Easter Egg Quest": dict(notes="2025-04-17 '新活动 Easter Egg Quest' 创建 [UL]"),
    "Easter Festival Face Off": dict(is_competitive="true", competition_form="排行榜", notes="Update_Log 2025-04-20: 24-Hour Player Competitions 的当期实例"),
    "Easter Get-together": dict(notes="见 Card_Collection_Event 页'Past and Current' 列表 → 卡牌相册"),
    "Joyful Moments": dict(notes="见 Card_Collection_Event 页'Past and Current' 列表 → 卡牌相册"),
    "Destination Dreamland": dict(notes="2025-07-04 创建 [UL]"),
    "Energy Challenge": dict(notes="2025-04-15 创建 [UL]"),
    "Coconut's Fishy Farming": dict(notes="2025-06-16 创建 [UL]"),
    "24-Hour Decoration Point Events": dict(duration="24 hours (活动名)", notes="2025-10-14 创建, 10-28 补等级与积分 [UL][MP]; Tips 页: 24 小时装饰活动用 token 换奖励, 剩余 token 不结转"),
    "Event Point Player Competitions": dict(is_competitive="true", competition_form="排行榜", notes="仅见 Multilevel_Events 页链接; wiki 有页, 无快照"),
}

FIELDS = ["event_name", "category", "subcategory", "duration", "is_competitive", "competition_form", "reward_structure",
          "main_mechanic", "reuse_count", "first_seen", "requires_purchase", "source_url", "notes", "page_status"]


def main():
    print("== 抓取辅助页")
    aux = {p: fetch(p) for p in AUX_PAGES}
    descs = parse_overview_descs(aux["Events"] or "")
    with open(os.path.join(DATA, "gh_event_categories.txt"), "w", encoding="utf-8") as f:
        f.write("Gossip Harbor wiki /wiki/Events 各分类说明（Wayback 快照 2025-11-01，原文英文）\n\n")
        for h, (cat, sub), text in descs:
            f.write(f"## {h}  [category={cat}; subcategory={sub}]\n{text}\n\n")
        f.write("## 补充: 主页 Event Calendar（2025-11-01 快照）\n"
                "Sunday: possibly Banana Peel (2-2:30am) | Monday: possibly Banana Peel; Restaurant Goals ends and starts again (2am GMT); "
                "Beat the Heat Wipeout, Lori's Dough Derby, or Ziva's Goldrush ends (10am) | Tuesday: possibly Raccoon Rascals; Mutineer Mayhem (12-2am GMT) | "
                "Wednesday: possibly Mutineer Mayhem | Thursday: possibly Banana Peel, possibly Mutineer Mayhem | "
                "Friday: possibly Raccoon Rascals; Beat the Heat Wipeout, Lori's Dough Derby, or Ziva's Goldrush begins (10am) | Saturday: (空)\n")
    print(f"  分类说明 {len(descs)} 段 → data/gh_event_categories.txt")

    print("== 抓取活动页")
    rows = []
    for slug, name, cat, sub, origin in PAGES:
        doc = fetch(slug)
        row = {k: "" for k in FIELDS}
        row.update(event_name=name, category=cat, subcategory=sub, source_url=WIKI + slug)
        cur = CURATED.get(name, {})
        row.update({k: v for k, v in cur.items() if k in FIELDS})
        if doc:
            row["page_status"] = "archived_page"
            para = first_paragraph(doc)
            if para and not row["main_mechanic"]:
                row["main_mechanic"] = para[:200]
            ib = infobox_pairs(doc)
            if ib:
                row["notes"] = (row["notes"] + "; infobox: " + "; ".join(f"{k}={v}" for k, v in ib[:8])).strip("; ")
        else:
            row["page_status"] = "overview_only(no_snapshot)" if origin == "overview" else "log_only(no_snapshot)"
        if origin == "log_only":
            row["notes"] = ("总览页未列出; " + row["notes"]).strip()
        rows.append(row)

    out = os.path.join(DATA, "gh_events.csv")
    with open(out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    print(f"→ {out}: {len(rows)} 行")

    print("\n== 摘要")
    print("page_status:", dict(Counter(r["page_status"] for r in rows)))
    print("category:", dict(Counter(r["category"] or "(空)" for r in rows)))
    print("is_competitive:", dict(Counter(r["is_competitive"] or "(空)" for r in rows)))
    print("duration 非空:", sum(1 for r in rows if r["duration"]), "/", len(rows))
    print("reuse_count 非空:", [(r["event_name"], r["reuse_count"]) for r in rows if r["reuse_count"]])
    print("first_seen 非空:", [(r["event_name"], r["first_seen"]) for r in rows if r["first_seen"]])


if __name__ == "__main__":
    main()
