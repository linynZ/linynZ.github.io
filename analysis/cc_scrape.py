import re,html,json,subprocess,time,os,sys,csv
P='http://127.0.0.1:21000'
clean=lambda x: re.sub(r'\s+',' ',html.unescape(re.sub('<[^>]+>','',x))).strip()
def fetch(page,cache):
    if os.path.exists(cache) and os.path.getsize(cache)>20000: return open(cache,encoding='utf-8',errors='ignore').read()
    url=f'https://web.archive.org/web/2024id_/https://candycrush.fandom.com/wiki/{page}'
    for k in range(4):
        r=subprocess.run(['curl','-s','-m','90','-L','--compressed','-x',P,'-o',cache,url])
        if os.path.exists(cache) and os.path.getsize(cache)>20000:
            return open(cache,encoding='utf-8',errors='ignore').read()
        time.sleep(5*(k+1))
    return ''
# 1. episode order from Reality tables 0,1
t=open('reality.html',encoding='utf-8',errors='ignore').read()
tbs=re.findall(r'<table.*?</table>',t,re.S)
eps=[]
for tb in tbs[:2]:
    for r in re.findall(r'<tr.*?</tr>',tb,re.S):
        if not clean(r).startswith('World'): continue
        for name in re.findall(r'<td[^>]*>.*?<a href="/wiki/([^"#]+)"',r,re.S):
            if name not in eps and not name.startswith('World_'): eps.append(name)
# also from 5 (world table) - skip
N=int(sys.argv[1]) if len(sys.argv)>1 else 100
eps=eps[:N]
json.dump(eps,open('episodes.json','w'),indent=1)
print('episodes',len(eps),eps[:5],eps[-3:],flush=True)
rows=[]
for i,ep in enumerate(eps):
    h=fetch(ep,f'ep_{i+1:03d}.html')
    if not h: print('FAIL',ep,flush=True); continue
    ok=0
    for tb in re.findall(r'<table.*?</table>',h,re.S):
        trs=re.findall(r'<tr.*?</tr>',tb,re.S)
        hdr=[clean(c) for c in re.findall(r'<t[hd][^>]*>(.*?)</t[hd]>',trs[0],re.S)] if trs else []
        if 'Moves' not in hdr or 'Level' not in hdr: continue
        idx={n:j for j,n in enumerate(hdr)}
        for tr in trs[1:]:
            cells=re.findall(r'<t[hd][^>]*>(.*?)</t[hd]>',tr,re.S)
            if len(cells)<len(hdr)-1: continue
            g=lambda n: cells[idx[n]] if n in idx and idx[n]<len(cells) else ''
            lv=clean(g('Level'))
            if not re.fullmatch(r'\d+',lv): continue
            typ=re.findall(r'data-image-name="([^"]+)"',g('Type'))
            mv=re.findall(r'Moves-(\d+)',g('Moves'))
            goal=g('Goal')
            goal_icons=re.findall(r'data-image-name="([^"]+)"',goal)
            goal_nums=re.findall(r':\s*([\d,]+)',clean(goal))
            rows.append(dict(episode_idx=i+1,episode=ep,level=int(lv),type=typ[0] if typ else '',moves=int(mv[0]) if mv else '',
                target=clean(g('Target score')).replace(',',''),goal_text=clean(goal),goal_icons='|'.join(goal_icons),goal_nums='|'.join(goal_nums),remarks=clean(g('Remarks'))[:120]))
            ok+=1
    print(i+1,ep,'levels',ok,flush=True)
    time.sleep(1.0)
with open('levels_raw.csv','w',newline='',encoding='utf-8') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
print('TOTAL',len(rows),flush=True)
# 2. difficulty categories
cats=['Very_easy_levels','Easy_levels','Somewhat_easy_levels','Medium_levels','Somewhat_hard_levels','Hard_levels','Very_hard_levels','Extremely_hard_levels','Nearly_impossible_levels','Insanely_hard_levels','Variable_levels','Considerably_easy_levels','Considerably_hard_levels']
diff={}
for c in cats:
    page=f'Category:{c}'; k=0
    while page and k<12:
        h=fetch(page,f'cat_{c}_{k}.html')
        if not h: print('CAT FAIL',c,flush=True); break
        lv=re.findall(r'href="/wiki/Level_(\d+)"[^>]*title="Level \d+"',h)
        for x in lv: diff.setdefault(int(x),c)
        nxt=re.findall(r'href="(/wiki/Category:[^"]*(?:pagefrom|from)=[^"]*)"[^>]*>\s*Next page',h)
        print(c,k,'levels',len(lv),'next',bool(nxt),flush=True)
        page=html.unescape(nxt[0]).split('/wiki/')[1] if nxt else None; k+=1
        time.sleep(1.0)
json.dump(diff,open('difficulty.json','w'))
print('DIFF',len(diff),flush=True)
