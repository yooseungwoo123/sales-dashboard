import requests, json, re, os, datetime

MONDAY_TOKEN = os.environ['MONDAY_TOKEN']
BOARD_ID = 5027844606

TEAMS = {
    'team1': {'name': '영업 1팀', 'members': ['유승우', '황소정', '이현우'], 'color': '#0073ea'},
    'team2': {'name': '영업 2팀', 'members': ['박승제', '정민규', '최태웅'], 'color': '#e2445c'},
    'cheongju': {'name': '청주팀', 'members': ['심승근'], 'color': '#00c875'},
}

COL_SCHED="long_text_mm2emrmb"; COL_RETIRE="long_text_mm2e6ef8"
COL_DIARY="file_mm2epezy"; COL_CALL="file_mm2e8ef6"; COL_ANAL="file_mm2na6f5"
COL_CONFIRM="color_mm2epv27"
FB_TEXTS=["long_text_mm2efqt4","long_text_mm2ep9ja","long_text_mm2eyexa","long_text_mm2ea524","long_text_mm2egjcb","long_text_mm2e8hg2","long_text_mm2enmmk"]
FB_DETAIL=["long_text_mm2eqk00","long_text_mm2etqpp","long_text_mm2ezrjp","long_text_mm2e50ks","long_text_mm2e39vj",None,None]
FB_PHOTOS=["file_mm2efy2b","file_mm2ekbcf","file_mm2en8ax","file_mm2egdeg","file_mm2egmha","file_mm2eqzmt",None]
FB_FILES=["file_mm2ekzfs","file_mm2er3cj","file_mm2e5n7s","file_mm2e7n1k","file_mm2er9xn","file_mm2ed43y",None]

def pf(v): return [s.strip() for s in v.split(',') if s.strip()] if v and isinstance(v,str) else []
def gs(v):
    if not v: return ''
    if isinstance(v,str): return v
    return ''
def ft(url):
    e=(url.split("?")[0].split(".")[-1] or "").lower()
    if e in ["jpg","jpeg","png","gif","webp","heic"]: return "photo"
    if e in ["mp3","m4a","wav","aac","ogg"]: return "audio"
    if e in ["mp4","mov","avi"]: return "video"
    return "doc"
def group(files):
    return [f for f in files if ft(f)=="photo"],[f for f in files if ft(f)=="audio"],[f for f in files if ft(f)=="video"]
def ep(t):
    if not t or not isinstance(t,str): return None
    m=re.search(r'\[([^\]]+)\]',t); return m.group(1) if m else None

def fetch_board():
    query = '''
    query($boardId: ID!) {
      boards(ids: [$boardId]) {
        items_page(limit: 50) {
          items {
            id name
            subitems {
              id name
              column_values {
                id text value
              }
            }
          }
        }
      }
    }'''
    r = requests.post(
        'https://api.monday.com/v2',
        headers={'Authorization': MONDAY_TOKEN, 'Content-Type': 'application/json'},
        json={'query': query, 'variables': {'boardId': str(BOARD_ID)}}
    )
    data = r.json()
    return data['data']['boards'][0]['items_page']['items']

def parse_items(items):
    persons = {}
    for item in items:
        subs = item.get('subitems', [])
        pname = None
        for s in subs:
            cv = {c['id']: c['text'] or c['value'] or '' for c in s.get('column_values', [])}
            for col in [COL_SCHED, COL_RETIRE]:
                t = gs(cv.get(col,''))
                if t:
                    p = ep(t)
                    if p: pname = p; break
            if pname: break
        if not pname: continue
        if pname not in persons: persons[pname] = {'name': pname, 'days': {}}
        for s in subs:
            cv = {c['id']: c['text'] or c['value'] or '' for c in s.get('column_values', [])}
            date_val = gs(cv.get('date0', ''))
            if not date_val: continue
            cfv = gs(cv.get(COL_CONFIRM, ''))
            fbs = []
            for i, col in enumerate(FB_TEXTS):
                txt = gs(cv.get(col, ''))
                if not txt.strip(): continue
                detail = gs(cv.get(FB_DETAIL[i], '')) if FB_DETAIL[i] else ''
                fp = pf(gs(cv.get(FB_PHOTOS[i], ''))) if FB_PHOTOS[i] else []
                ff = pf(gs(cv.get(FB_FILES[i], ''))) if FB_FILES[i] else []
                sched_photos = [f for f in fp if ft(f)=="photo"]
                consult_photos = [f for f in ff if ft(f)=="photo"]
                audios = [f for f in ff if ft(f)=="audio"] + [f for f in fp if ft(f)=="audio"]
                fbs.append({'text':txt,'detail':detail,'sched_photos':sched_photos,'consult_photos':consult_photos,'audios':audios,'idx':i+1})
            d_ph,d_au,d_vi = group(pf(gs(cv.get(COL_DIARY,''))))
            c_ph,c_au,c_vi = group(pf(gs(cv.get(COL_CALL,''))))
            a_ph,a_au,a_vi = group(pf(gs(cv.get(COL_ANAL,''))))
            persons[pname]['days'][date_val] = {
                'weekday': s['name'],
                'diary': {'photos':d_ph,'audios':d_au,'videos':d_vi},
                'call': {'photos':c_ph,'audios':c_au,'videos':c_vi},
                'anal': {'photos':a_ph,'audios':a_au,'videos':a_vi},
                'schedule': gs(cv.get(COL_SCHED,'')),
                'retire': gs(cv.get(COL_RETIRE,'')),
                'feedbacks': fbs, 'confirm': cfv
            }
    return list(persons.values())

def get_today():
    today = datetime.date.today()
    # 월~금만, 주말이면 금요일로
    if today.weekday() >= 5:
        today = today - datetime.timedelta(days=today.weekday()-4)
    return str(today)

def esc(s):
    if not s: return ''
    return s.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;').replace('"','&quot;').replace("'","&#39;")

def img_tag(url):
    return f'<img src="{esc(url)}" style="width:100%;border-radius:8px;border:0.5px solid #e6e9ef;display:block;cursor:pointer;margin-bottom:4px" onclick="openLb(this.src)" loading="lazy" onerror="this.style.display=\'none\'">'

def audio_player(url, aid):
    name = url.split("/")[-1].split("?")[0]
    try:
        import urllib.parse
        name = urllib.parse.unquote(name)
        parts = name.replace('.m4a','').replace('.mp3','').split('_')
        name = '_'.join(parts[2:])[:28] if len(parts)>=3 else name[:28]
    except: name = "녹취"
    return (f'<div style="display:flex;align-items:center;gap:8px;background:#f0fdf4;border:0.5px solid #bbf7d0;border-radius:6px;padding:5px 8px;margin-bottom:3px">'
            f'<button onclick="var a=document.getElementById(\'{aid}\');if(a.paused){{a.play();this.innerHTML=\'&#9646;&#9646;\'}}else{{a.pause();this.innerHTML=\'&#9654;\'}}" '
            f'style="width:24px;height:24px;border-radius:50%;background:#15803d;border:none;cursor:pointer;color:#fff;font-size:10px;flex-shrink:0">&#9654;</button>'
            f'<audio id="{aid}" src="{esc(url)}"></audio>'
            f'<span style="font-size:10px;color:#15803d;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:1">{esc(name)}</span></div>')

def render_card(p, today):
    d = p['days'].get(today, {})
    COLORS={"유승우":("#dbeafe","#1e40af"),"박승제":("#fee2e2","#991b1b"),"황소정":("#dcfce7","#166534"),"정민규":("#fef3c7","#92400e"),"심승근":("#ede9fe","#5b21b6"),"이현우":("#d1fae5","#065f46"),"최태웅":("#fce7f3","#9d174d")}
    bg,tx = next(((v[0],v[1]) for k,v in COLORS.items() if k in p['name']),("#f1f5f9","#334155"))
    ini = re.sub(r'\s*(팀장|부팀장|사원)\s*','',p['name'])[:2]

    def num(t,pat):
        m=re.search(pat,t or ''); return m.group(1) if m else '0'
    retire = d.get('retire','') if d else ''
    confirm = d.get('confirm','') == '컨펌 완료' if d else False
    PAT_N = r'신규\s*[:：]\s*(\d+)'
    PAT_C = r'계약\s*[:：]\s*([\d.]+)'
    PAT_F = r'수임료\s*[:：]\s*([\d.]+)'
    nn = num(retire, PAT_N)
    nc = num(retire, PAT_C)
    nf = num(retire, PAT_F)
    new_b = f'<span style="background:#e8f0fe;color:#1565c0;font-size:10px;padding:2px 8px;border-radius:10px;font-weight:600">신규 {nn}건</span>' if nn!='0' else ''
    con_b = f'<span style="background:#dcfce7;color:#15803d;font-size:10px;padding:2px 8px;border-radius:10px;font-weight:600">계약 {nc}건</span>' if nc!='0' else ''
    fee_b = f'<span style="background:#fef9c3;color:#854d0e;font-size:10px;padding:2px 8px;border-radius:10px;font-weight:600">수임 {nf}</span>' if nf!='0' else ''
    confirm_badge = '<span style="background:#d1fae5;color:#065f46;font-size:10px;padding:2px 8px;border-radius:10px;font-weight:600">&#10003; 컨펌</span>' if confirm else '<span style="background:#f1f5f9;color:#888;font-size:10px;padding:2px 8px;border-radius:10px;border:0.5px solid #ddd">미컨펌</span>'

    if not d:
        return (f'<div style="background:#fff;border:0.5px solid #e6e9ef;border-radius:12px;overflow:hidden;margin-bottom:14px">'
                f'<div style="padding:11px 14px;display:flex;align-items:center;gap:10px;background:#fafbfc">'
                f'<div style="width:34px;height:34px;border-radius:50%;background:{bg};color:{tx};display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:700">{ini}</div>'
                f'<div><div style="font-size:13px;font-weight:700;color:#323338">{esc(p["name"])}</div><div style="font-size:11px;color:#676879">미제출</div></div>'
                f'<div style="margin-left:auto"><span style="background:#f1f5f9;color:#888;font-size:10px;padding:2px 8px;border-radius:10px;border:0.5px solid #ddd">보고 없음</span></div>'
                f'</div></div>')

    diary_photos = d.get('diary',{}).get('photos',[])
    call_videos = d.get('call',{}).get('videos',[])
    anal_photos = d.get('anal',{}).get('photos',[])
    call_audios = d.get('call',{}).get('audios',[])

    photos_row = ''
    if diary_photos or anal_photos:
        l = f'<div style="flex:3;min-width:0"><div style="font-size:10px;font-weight:700;color:#7c3aed;margin-bottom:6px;text-transform:uppercase">&#128218; 다이어리</div>{"".join(img_tag(u) for u in diary_photos)}</div>' if diary_photos else ''
        r = f'<div style="flex:1;min-width:0"><div style="font-size:10px;font-weight:700;color:#0369a1;margin-bottom:6px;text-transform:uppercase">&#128202; 해석학</div>{"".join(img_tag(u) for u in anal_photos)}</div>' if anal_photos else ''
        photos_row = f'<div style="padding:11px 13px;border-bottom:0.5px solid #e6e9ef"><div style="display:flex;gap:10px;align-items:flex-start">{l}{r}</div></div>'

    video_html = ''
    if call_videos:
        vids = ''.join(f'<video controls preload="metadata" src="{esc(u)}" style="width:100%;aspect-ratio:9/16;object-fit:cover;border-radius:8px;border:0.5px solid #e6e9ef;background:#000;display:block"></video>' for u in call_videos)
        aud = ''.join(audio_player(u, f"{ini}_c_au{i}") for i,u in enumerate(call_audios))
        video_html = f'<div style="padding:11px 13px;border-left:0.5px solid #e6e9ef"><div style="font-size:10px;font-weight:700;color:#0891b2;margin-bottom:7px;text-transform:uppercase">&#127909; 통화기록</div>{vids}{aud}</div>'

    col3 = ' 1fr' if video_html else ''
    bm = ';border-right:0.5px solid #e6e9ef' if video_html else ''
    report_row = (f'<div style="display:grid;grid-template-columns:1fr 1fr{col3};border-bottom:0.5px solid #e6e9ef">'
                  f'<div style="padding:11px 13px;border-right:0.5px solid #e6e9ef"><div style="font-size:10px;font-weight:700;color:#0073ea;margin-bottom:7px;text-transform:uppercase">상담일정 보고</div>'
                  f'<div style="font-size:13px;color:#323338;line-height:1.75;white-space:pre-wrap;word-break:break-word">{esc(d.get("schedule","")) or "없음"}</div></div>'
                  f'<div style="padding:11px 13px{bm}"><div style="font-size:10px;font-weight:700;color:#00c875;margin-bottom:7px;text-transform:uppercase">퇴근 보고</div>'
                  f'<div style="font-size:13px;color:#323338;line-height:1.75;white-space:pre-wrap;word-break:break-word">{esc(retire) or "없음"}</div></div>'
                  f'{video_html}</div>')

    pairs_html = ''
    for fb in d.get('feedbacks',[]):
        bm2 = re.search(r'업체명\s*[:：]\s*([^\n]+)', fb['text'])
        biz = bm2.group(1).strip() if bm2 else f"상담 {fb['idx']}"
        aud_h = ''.join(audio_player(u, f"aud_{ini}_fb{fb['idx']}_au{i}") for i,u in enumerate(fb.get('audios',[])))
        has_sched = bool(fb.get('sched_photos') or fb.get('detail'))
        c_imgs = ''.join(img_tag(u) for u in fb.get('consult_photos',[]))

        if has_sched:
            sp_imgs = ''.join(img_tag(u) for u in fb.get('sched_photos',[]))
            left = (f'<div style="display:flex;flex-direction:column;gap:8px">'
                    f'{f"<div style=border:0.5px solid #e6e9ef;border-radius:8px;overflow:hidden><div style=background:#e8f0fe;padding:6px 10px;border-bottom:0.5px solid #e6e9ef;font-size:10px;font-weight:700;color:#1565c0>&#128247; {esc(biz)} 일정사진</div><div style=padding:8px 10px>{sp_imgs}</div></div>" if sp_imgs else ""}'
                    f'{f"<div style=border:0.5px solid #e6e9ef;border-radius:8px;overflow:hidden><div style=background:#e8f0fe;padding:6px 10px;border-bottom:0.5px solid #e6e9ef;font-size:10px;font-weight:700;color:#1565c0>&#128203; {esc(biz)} 상세내용</div><div style=padding:8px 10px;font-size:13px;color:#323338;line-height:1.75;white-space:pre-wrap;word-break:break-word>{esc(fb.get(chr(100)+chr(101)+chr(116)+chr(97)+chr(105)+chr(108),chr(32)))}</div></div>" if fb.get("detail") else ""}'
                    f'<div style="border:0.5px solid #e6e9ef;border-radius:8px;overflow:hidden">'
                    f'<div style="background:#fafbfc;padding:6px 10px;border-bottom:0.5px solid #e6e9ef;font-size:10px;font-weight:700;color:#323338">&#127970; {esc(biz)}</div>'
                    f'<div style="padding:8px 10px;font-size:13px;color:#323338;line-height:1.8;white-space:pre-wrap;word-break:break-word">{esc(fb["text"])}</div>'
                    f'{f"<div style=padding:6px 10px;border-top:0.5px solid #e6e9ef;background:#fafbfc>{aud_h}</div>" if aud_h else ""}'
                    f'</div></div>')
        else:
            left = (f'<div style="border:0.5px solid #e6e9ef;border-radius:8px;overflow:hidden;height:100%">'
                    f'<div style="background:#fafbfc;padding:6px 10px;border-bottom:0.5px solid #e6e9ef;font-size:10px;font-weight:700;color:#323338">&#127970; {esc(biz)}</div>'
                    f'<div style="padding:8px 10px;font-size:13px;color:#323338;line-height:1.8;white-space:pre-wrap;word-break:break-word">{esc(fb["text"])}</div>'
                    f'{f"<div style=padding:6px 10px;border-top:0.5px solid #e6e9ef;background:#fafbfc>{aud_h}</div>" if aud_h else ""}'
                    f'</div>')

        right = (f'<div style="border:0.5px solid #e6e9ef;border-radius:8px;overflow:hidden;height:100%">'
                 f'<div style="background:#fafbfc;padding:6px 10px;border-bottom:0.5px solid #e6e9ef;font-size:10px;font-weight:700;color:#323338">&#128203; {esc(biz)} 상담일지</div>'
                 f'<div style="padding:8px 10px">{c_imgs if c_imgs else "<span style=font-size:10px;color:#ccc>없음</span>"}</div>'
                 f'</div>')

        pairs_html += (f'<div style="display:grid;grid-template-columns:1fr 2fr;gap:10px;margin-bottom:10px">'
                       f'<div>{left}</div><div>{right}</div></div>')

    fb_section = (f'<div style="font-size:10px;font-weight:700;color:#e2445c;margin-bottom:8px;text-transform:uppercase">상담 자가피드백 &amp; 상담일지</div>'
                  f'{pairs_html or "<span style=font-size:12px;color:#ccc>없음</span>"}')

    return (f'<div style="background:#fff;border:0.5px solid #e6e9ef;border-radius:12px;overflow:hidden;margin-bottom:14px">'
            f'<div style="padding:11px 14px;border-bottom:0.5px solid #e6e9ef;display:flex;align-items:center;gap:10px;background:#fafbfc">'
            f'<div style="width:34px;height:34px;border-radius:50%;background:{bg};color:{tx};display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:700;flex-shrink:0">{ini}</div>'
            f'<div><div style="font-size:13px;font-weight:700;color:#323338">{esc(p["name"])}</div><div style="font-size:11px;color:#676879">{d.get("weekday","")}</div></div>'
            f'<div style="margin-left:auto;display:flex;gap:4px;flex-wrap:wrap;justify-content:flex-end">{confirm_badge}{new_b}{con_b}{fee_b}</div>'
            f'</div>{photos_row}{report_row}'
            f'<div style="padding:11px 13px">{fb_section}</div></div>')

def make_html(team_key, persons, today):
    team = TEAMS[team_key]
    now = datetime.datetime.now().strftime('%Y.%m.%d %H:%M')
    cards = ''.join(render_card(p, today) for p in persons)
    total_new = 0; total_contract = 0; total_confirm = 0
    for p in persons:
        d = p['days'].get(today, {})
        if not d: continue
        retire = d.get('retire','')
        m = re.search(r'신규\s*[:：]\s*(\d+)', retire)
        if m: total_new += int(m.group(1))
        m = re.search(r'계약\s*[:：]\s*([\d.]+)', retire)
        if m: total_contract += float(m.group(1))
        if d.get('confirm','') == '컨펌 완료': total_confirm += 1

    return (f'<!DOCTYPE html><html lang="ko"><head><meta charset="UTF-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1.0">'
            f'<title>{team["name"]} 일간 보고</title>'
            f'<style>*{{box-sizing:border-box;margin:0;padding:0}}body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans KR",sans-serif;background:#f5f6f8;color:#323338;font-size:13px}}</style>'
            f'</head><body><div style="padding:12px 14px;max-width:1200px;margin:0 auto">'
            f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:14px;flex-wrap:wrap">'
            f'<div style="font-size:14px;font-weight:700;color:#323338;display:flex;align-items:center;gap:6px">'
            f'<div style="width:8px;height:8px;border-radius:50%;background:{team["color"]}"></div>'
            f'{team["name"]} 일간 보고 &mdash; {today}'
            f'<span style="font-size:11px;color:#676879;margin-left:6px">업데이트 {now}</span></div>'
            f'<div style="margin-left:auto;display:flex;gap:6px;flex-wrap:wrap">'
            f'<div style="background:#fff;padding:4px 10px;border-radius:6px;border:0.5px solid #e6e9ef;font-size:11px;color:#676879">신규 <b style="color:#323338">{total_new}건</b></div>'
            f'<div style="background:#fff;padding:4px 10px;border-radius:6px;border:0.5px solid #e6e9ef;font-size:11px;color:#676879">계약 <b style="color:#323338">{total_contract:.0f}건</b></div>'
            f'<div style="background:#fff;padding:4px 10px;border-radius:6px;border:0.5px solid #e6e9ef;font-size:11px;color:#676879">컨펌 <b style="color:#323338">{total_confirm}/{len(persons)}</b></div>'
            f'</div></div>{cards}</div>'
            f'<div id="lb" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.9);z-index:9999;align-items:center;justify-content:center" onclick="this.style.display=\'none\'">'
            f'<img id="lbi" style="max-width:95vw;max-height:95vh;border-radius:8px;object-fit:contain"></div>'
            f'<script>function openLb(src){{var lb=document.getElementById("lb");document.getElementById("lbi").src=src;lb.style.display="flex";}}'
            f'document.addEventListener("keydown",function(e){{if(e.key==="Escape")document.getElementById("lb").style.display="none";}});</script>'
            f'</body></html>')

print("monday.com 데이터 불러오는 중...")
items = fetch_board()
all_persons = parse_items(items)
today = get_today()
print(f"오늘 날짜: {today}, 팀원 수: {len(all_persons)}")

files = {'team1':'team1.html','team2':'team2.html','cheongju':'cheongju.html'}
for team_key, filename in files.items():
    members = TEAMS[team_key]['members']
    team_persons = [p for p in all_persons if any(m in p['name'] for m in members)]
    html = make_html(team_key, team_persons, today)
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"{TEAMS[team_key]['name']}: {len(team_persons)}명 → {filename} 생성완료")
