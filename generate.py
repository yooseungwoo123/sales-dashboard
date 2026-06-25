import requests, json, re, os, datetime, calendar, shutil

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
FB_FILES=["file_mm2ekzfs","file_mm2er3cj","file_mm2e5n7s","file_mm2e7n1k",None,"file_mm2er9xn","file_mm2ed43y"]

def pf(v): return [s.strip() for s in v.split(',') if s.strip()] if v and isinstance(v,str) else []
def extract_file_urls(cv_list, col_id):
    """monday.com 파일 컬럼에서 URL 목록 추출"""
    import json as _json
    for c in cv_list:
        if c['id'] != col_id: continue
        # GraphQL FileValue의 files 필드 우선 사용
        files = c.get('files', [])
        if files:
            urls = []
            for f in files:
                asset = f.get('asset', {}) or {}
                url = asset.get('url', '')
                if url: urls.append(url)
            if urls: return urls
        # text 값이 URL인 경우 (쉼표 구분)
        text = (c.get('text') or '').strip()
        if text and 'http' in text:
            urls = [s.strip() for s in text.split(',') if s.strip().startswith('http')]
            if urls: return urls
        # value JSON에서 추출
        val = (c.get('value') or '').strip()
        if val and val.startswith('{'):
            try:
                data = _json.loads(val)
                urls = []
                for f in data.get('files', []):
                    url = (f.get('url') or f.get('assetUrl') or '').strip()
                    if url: urls.append(url)
                if urls: return urls
            except: pass
        return []
    return []
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

REPORT_BOARD_ID = 2048953048
REPORT_COLS = {
    'name': 'short_textm1ml24et',
    'date': 'dateq6xjh4ly',
    'call': 'numberd9oxgtmo',
    'consult': 'numeric_mktap55t',
    'outside': 'numberw0x7lot0',
    'inside': 'numberagnjh5pw',
    'contract': 'numberj3khnt30',
    'fee': 'numbersjugrtqf',
    'baekbaek': 'numberyyenwhu3',
}

def fetch_report_board():
    """영업팀 일간 보고서 보드 전체 데이터 fetch"""
    query = '''
    query($boardId: ID!, $cursor: String) {
      boards(ids: [$boardId]) {
        items_page(limit: 500, cursor: $cursor) {
          cursor
          items {
            column_values {
              id text
            }
          }
        }
      }
    }'''
    all_items = []
    cursor = None
    max_pages = 10  # 최대 10페이지 (5000건)
    for _ in range(max_pages):
        variables = {'boardId': str(REPORT_BOARD_ID)}
        if cursor:
            variables['cursor'] = cursor
        r = requests.post(
            'https://api.monday.com/v2',
            headers={'Authorization': MONDAY_TOKEN, 'Content-Type': 'application/json'},
            json={'query': query, 'variables': variables},
            timeout=30
        )
        data = r.json()
        page = data['data']['boards'][0]['items_page']
        items = page.get('items', [])
        all_items.extend(items)
        cursor = page.get('cursor')
        if not cursor or not items:
            break
    return all_items

def parse_report_items(items):
    """보고서 보드 아이템을 {이름: {날짜: {컬럼: 값}}} 구조로 파싱"""
    data = {}
    for item in items:
        cv = {c['id']: c['text'] or '' for c in item.get('column_values', [])}
        name = cv.get(REPORT_COLS['name'], '').strip()
        date = cv.get(REPORT_COLS['date'], '').strip()
        if not name or not date: continue
        if name not in data: data[name] = {}
        data[name][date] = {
            'call': float(cv.get(REPORT_COLS['call'], '') or 0),
            'consult': float(cv.get(REPORT_COLS['consult'], '') or 0),
            'outside': float(cv.get(REPORT_COLS['outside'], '') or 0),
            'inside': float(cv.get(REPORT_COLS['inside'], '') or 0),
            'contract': float(cv.get(REPORT_COLS['contract'], '') or 0),
            'fee': float(cv.get(REPORT_COLS['fee'], '') or 0),
            'baekbaek': float(cv.get(REPORT_COLS['baekbaek'], '') or 0),
        }
    return data

def fmt_num(v):
    """소수점 불필요하면 정수로"""
    return int(v) if v == int(v) else round(v, 1)

def render_report_section(team_key, report_data, archive_months):
    """영업팀 일간 보고서 섹션 HTML 생성 (월별 탭 연동)"""
    team = TEAMS[team_key]
    members = team['members']
    COLORS = {
        '유승우': ('#dbeafe', '#1e40af'), '황소정': ('#dcfce7', '#166534'),
        '이현우': ('#d1fae5', '#065f46'), '박승제': ('#fee2e2', '#991b1b'),
        '정민규': ('#fef3c7', '#92400e'), '최태웅': ('#fce7f3', '#9d174d'),
        '심승근': ('#ede9fe', '#5b21b6'),
    }

    months_html = ''
    for am in archive_months:
        y, m = am['year'], am['month']
        mid = f'{y}-{m:02d}'
        label = f'{y}년 {m}월'
        is_cur = am['is_current']

        # 해당 월 팀원별 데이터 수집
        members_html = ''
        team_totals = {'call':0,'consult':0,'outside':0,'inside':0,'contract':0,'fee':0,'baekbaek':0}

        for mname in members:
            # report_data에서 이름 매칭 (부분 일치)
            matched_key = next((k for k in report_data if mname in k), None)
            person_data = report_data.get(matched_key, {}) if matched_key else {}

            # 해당 월 날짜만 필터
            month_rows = {d: v for d, v in person_data.items() if d.startswith(f'{y}-{m:02d}')}

            # 합계
            totals = {k: sum(r[k] for r in month_rows.values()) for k in ['call','consult','outside','inside','contract','fee','baekbaek']}
            for k in team_totals: team_totals[k] += totals[k]

            bg, tx = COLORS.get(mname, ('#f1f5f9', '#334155'))
            ini = re.sub(r'\s*(팀장|부팀장|사원|PM)\s*', '', mname)[:2]
            mid2 = f'{mid}-{ini}'

            # 날짜별 행
            rows_html = ''
            wd_names = ['월','화','수','목','금','토','일']
            for d in sorted(month_rows.keys()):
                r = month_rows[d]
                dt = datetime.date.fromisoformat(d)
                dlabel = f'{dt.month}월 {dt.day}일 ({wd_names[dt.weekday()]})'
                rows_html += (f'<tr><td>{dlabel}</td>'
                             f'<td>{fmt_num(r["call"])}</td><td>{fmt_num(r["consult"])}</td>'
                             f'<td>{fmt_num(r["outside"])}</td><td>{fmt_num(r["inside"])}</td>'
                             f'<td>{fmt_num(r["contract"])}</td><td>{fmt_num(r["fee"])}</td>'
                             f'<td>{fmt_num(r["baekbaek"])}</td></tr>')

            rows_html += (f'<tr class="rpt-sum"><td>합계</td>'
                         f'<td>{fmt_num(totals["call"])}</td><td>{fmt_num(totals["consult"])}</td>'
                         f'<td>{fmt_num(totals["outside"])}</td><td>{fmt_num(totals["inside"])}</td>'
                         f'<td>{fmt_num(totals["contract"])}</td><td>{fmt_num(totals["fee"])}</td>'
                         f'<td>{fmt_num(totals["baekbaek"])}</td></tr>')

            members_html += (
                f'<div class="rpt-member">'
                f'<div class="rpt-mhdr" onclick="toggleRpt(\'{mid2}\')">'
                f'<div style="width:26px;height:26px;border-radius:50%;background:{bg};color:{tx};display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:500;flex-shrink:0">{ini}</div>'
                f'<span style="font-size:12px;font-weight:500">{esc(mname)}</span>'
                f'<div style="display:flex;gap:10px;margin-left:auto;margin-right:8px">'
                f'<span class="rpt-badge">상담 <b>{fmt_num(totals["consult"])}</b></span>'
                f'<span class="rpt-badge">계약 <b>{fmt_num(totals["contract"])}</b></span>'
                f'<span class="rpt-badge">수임료 <b>{fmt_num(totals["fee"])}</b></span>'
                f'</div>'
                f'<span class="rpt-chv" id="chv-{mid2}">▾</span>'
                f'</div>'
                f'<div id="rpt-{mid2}" style="display:none;overflow-x:auto">'
                f'<table class="rpt-table"><thead><tr>'
                f'<th>날짜</th><th>전화콜량</th><th>상담수</th><th>외근수</th><th>내근수</th><th>계약수</th><th>수임료</th><th>백백수</th>'
                f'</tr></thead><tbody>{rows_html}</tbody></table>'
                f'</div></div>'
            )

        # 팀 합계
        team_sum_html = (
            f'<div class="rpt-team-sum">'
            f'<div style="font-size:11px;font-weight:500;color:#676879;margin-bottom:8px">{team["name"]} 합계 — {label}</div>'
            f'<div style="display:grid;grid-template-columns:repeat(7,1fr);gap:6px">'
            + ''.join(f'<div style="text-align:center"><div style="font-size:9px;color:#aaa;margin-bottom:2px">{n}</div><div style="font-size:13px;font-weight:500;color:{team["color"]}">{fmt_num(team_totals[k])}</div></div>'
                      for n, k in [('전화콜량','call'),('상담수','consult'),('외근수','outside'),('내근수','inside'),('계약수','contract'),('수임료','fee'),('백백수','baekbaek')])
            + f'</div></div>'
        )

        display = '' if is_cur else 'display:none;'
        months_html += f'<div id="rpt-month-{mid}" style="{display}">{members_html}{team_sum_html}</div>'

    # 월 탭 버튼
    tab_btns = ''
    for am in archive_months:
        y, m = am['year'], am['month']
        mid = f'{y}-{m:02d}'
        label = f'{y}년 {m}월'
        active = 'rpt-mtab-active' if am['is_current'] else ''
        tab_btns += f'<span class="rpt-mtab {active}" onclick="switchRptMonth(\'{mid}\')">{label}</span>'

    cur_mid = f'{archive_months[0]["year"]}-{archive_months[0]["month"]:02d}'

    return (
        f'<div class="rpt-section">'
        f'<div class="rpt-shdr" onclick="toggleRptSection()">'
        f'<span style="font-size:12px;font-weight:500">영업팀 일간 보고서</span>'
        f'<span id="rpt-month-label" style="font-size:10px;color:#aaa;margin-left:4px">— {archive_months[0]["year"]}년 {archive_months[0]["month"]}월</span>'
        f'<span id="rpt-chv-main" style="margin-left:auto;font-size:12px;color:#aaa">▲</span>'
        f'</div>'
        f'<div id="rpt-body">'
        f'<div style="padding:8px 14px 4px;display:flex;gap:6px;flex-wrap:wrap;border-bottom:0.5px solid #e6e9ef">{tab_btns}</div>'
        f'<div style="padding:12px 14px">{months_html}</div>'
        f'</div>'
        f'</div>'
    )

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
            cv_list = s.get('column_values', [])
            cv = {}
            for c in cv_list:
                # text에 URL이 있으면 text, 없으면 value 사용
                text_val = (c.get('text') or '').strip()
                val = (c.get('value') or '').strip()
                cv[c['id']] = text_val if text_val else val
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
                'feedbacks': fbs, 'confirm': cfv,
                **{f'_fp_{i}': gs(cv.get(FB_PHOTOS[i],'')) for i in range(7) if FB_PHOTOS[i]},
                **{f'_fd_{i}': gs(cv.get(FB_DETAIL[i],'')) for i in range(7) if FB_DETAIL[i]},
                **{f'_ff_{i}': gs(cv.get(FB_FILES[i],'')) for i in range(7) if FB_FILES[i]},
            }
    return list(persons.values())

def get_today():
    # 한국시간(KST = UTC+9) 기준
    today = (datetime.datetime.utcnow() + datetime.timedelta(hours=9)).date()
    if today.weekday() >= 5:
        today = today - datetime.timedelta(days=today.weekday()-4)
    return str(today)

def get_weeks_in_month(year, month):
    """해당 월의 주차별 날짜 목록 반환 (월~금, 1주차부터 오름차순)"""
    cal = calendar.Calendar(0)  # 월요일 시작
    weeks = []
    month_days = cal.monthdatescalendar(year, month)
    for week_idx, week in enumerate(month_days):
        weekdays = []
        for day in week:
            if day.weekday() < 5 and day.month == month:
                weekdays.append(day)
        if weekdays:
            weeks.append({'week_num': week_idx + 1, 'days': weekdays})
    return weeks

def get_month_tabs(current_year, current_month):
    """최근 3개월 탭 정보 반환"""
    tabs = []
    for i in range(3):
        m = current_month - i
        y = current_year
        while m <= 0:
            m += 12
            y -= 1
        tabs.append({'year': y, 'month': m, 'is_current': i == 0})
    return tabs

def esc(s):
    if not s: return ''
    return s.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;').replace('"','&quot;').replace("'","&#39;")

def img_tag(url):
    return f'<img src="{esc(url)}" style="width:100%;max-width:100%;border-radius:8px;border:0.5px solid #e6e9ef;display:block;cursor:pointer;margin-bottom:4px;object-fit:cover" onclick="openLb(this.src)" loading="lazy" onerror="this.style.display=\'none\'">'

def audio_player(url, aid):
    name = url.split("/")[-1].split("?")[0]
    try:
        import urllib.parse
        name = urllib.parse.unquote(name)
        parts = name.replace('.m4a','').replace('.mp3','').split('_')
        name = '_'.join(parts[2:])[:28] if len(parts)>=3 else name[:28]
    except: name = "녹취"
    return (
        f'<div class="ap-wrap" data-aid="{aid}" style="background:#f0fdf4;border:0.5px solid #bbf7d0;border-radius:8px;padding:7px 10px;margin-bottom:5px">'
        f'<audio id="{aid}" src="{esc(url)}" preload="metadata"></audio>'
        f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:5px">'
        f'<button id="{aid}_btn" onclick="apToggle(\'{aid}\')" '
        f'style="width:26px;height:26px;border-radius:50%;background:#15803d;border:none;cursor:pointer;color:#fff;font-size:11px;flex-shrink:0;display:flex;align-items:center;justify-content:center">&#9654;</button>'
        f'<button onclick="apSeek(\'{aid}\',-10)" title="10초 뒤로" '
        f'style="width:22px;height:22px;border-radius:50%;background:#bbf7d0;border:none;cursor:pointer;color:#15803d;font-size:9px;flex-shrink:0;display:flex;align-items:center;justify-content:center">-10</button>'
        f'<button onclick="apSeek(\'{aid}\',10)" title="10초 앞으로" '
        f'style="width:22px;height:22px;border-radius:50%;background:#bbf7d0;border:none;cursor:pointer;color:#15803d;font-size:9px;flex-shrink:0;display:flex;align-items:center;justify-content:center">+10</button>'
        f'<span style="font-size:10px;color:#15803d;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{esc(name)}</span>'
        f'<span id="{aid}_time" style="font-size:10px;color:#15803d;white-space:nowrap;font-variant-numeric:tabular-nums">0:00 / 0:00</span>'
        f'</div>'
        f'<div style="position:relative;height:6px;background:#bbf7d0;border-radius:3px;cursor:pointer" onclick="apClick(\'{aid}\',event,this)">'
        f'<div id="{aid}_bar" style="height:100%;width:0%;background:#15803d;border-radius:3px;transition:width 0.1s linear;pointer-events:none"></div>'
        f'</div>'
        f'</div>'
    )

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

    # 자가피드백 개수 기준으로 최대 인덱스 결정 (피드백 없어도 일정사진/상세내용/상담일지 표시)
    max_idx = max(len(d.get('feedbacks', [])), max(
        (i+1 for i in range(7) if
         (FB_PHOTOS[i] and pf(gs(d.get('_raw_fb_photos_'+str(i), '')))) or
         (FB_DETAIL[i] and gs(d.get('_raw_fb_detail_'+str(i), ''))) or
         (FB_FILES[i] and pf(gs(d.get('_raw_fb_files_'+str(i), ''))))
        ), default=0
    )) if False else len(d.get('feedbacks', []))

    # feedbacks 리스트를 인덱스 기반으로 재구성 (없는 슬롯도 포함)
    fb_slots = {fb['idx']: fb for fb in d.get('feedbacks', [])}

    # 각 슬롯별로 일정사진/상세내용/상담일지 직접 파싱
    raw_cv = d.get('_cv', {})

    pairs_html = ''
    rendered = set()

    for fb in d.get('feedbacks', []):
        idx = fb['idx']
        rendered.add(idx)
        bm2 = re.search(r'업체명\s*[:：]\s*([^\n]+)', fb['text'])
        biz = bm2.group(1).strip() if bm2 else f"상담 {idx}"
        aud_h = ''.join(audio_player(u, f"aud_{ini}_fb{idx}_au{i}") for i,u in enumerate(fb.get('audios',[])))
        c_imgs = ''.join(img_tag(u) for u in fb.get('consult_photos',[]))
        sp_imgs = ''.join(img_tag(u) for u in fb.get('sched_photos',[]))
        detail_val = fb.get('detail','')

        sched_row = ''
        if sp_imgs or detail_val:
            sched_row = (f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-bottom:8px">'
                        + (f'<div style="border:0.5px solid #e6e9ef;border-radius:8px;overflow:hidden"><div style="background:#e8f0fe;padding:5px 8px;border-bottom:0.5px solid #e6e9ef;font-size:9px;font-weight:700;color:#1565c0">&#128247; 일정사진</div><div style="padding:6px 8px;max-height:130px;overflow:hidden">{sp_imgs}</div></div>' if sp_imgs else '<div></div>')
                        + (f'<div style="border:0.5px solid #e6e9ef;border-radius:8px;overflow:hidden"><div style="background:#e8f0fe;padding:5px 8px;border-bottom:0.5px solid #e6e9ef;font-size:9px;font-weight:700;color:#1565c0">&#128203; 상세내용</div><div style="padding:6px 8px;font-size:11px;color:#323338;line-height:1.6;white-space:pre-wrap;word-break:break-word">{esc(detail_val)}</div></div>' if detail_val else '<div></div>')
                        + f'</div>')

        fb_box = (f'<div style="border:0.5px solid #e6e9ef;border-radius:8px;overflow:hidden">'
                + f'<div style="background:#fafbfc;padding:6px 10px;border-bottom:0.5px solid #e6e9ef;font-size:10px;font-weight:700;color:#323338">&#127970; {esc(biz)}</div>'
                + f'<div style="padding:8px 10px;font-size:13px;color:#323338;line-height:1.8;white-space:pre-wrap;word-break:break-word">{esc(fb["text"])}</div>'
                + (f'<div style="padding:6px 10px;border-top:0.5px solid #e6e9ef;background:#fafbfc">{aud_h}</div>' if aud_h else '')
                + f'</div>')

        left = f'<div style="display:flex;flex-direction:column;gap:0">{sched_row}{fb_box}</div>'
        right = (f'<div style="border:0.5px solid #e6e9ef;border-radius:8px;overflow:hidden">'
                 f'<div style="background:#fafbfc;padding:6px 10px;border-bottom:0.5px solid #e6e9ef;font-size:10px;font-weight:700;color:#323338">&#128203; {esc(biz)} 상담일지</div>'
                 f'<div style="padding:8px 10px">{c_imgs if c_imgs else "<span style=font-size:10px;color:#ccc>없음</span>"}</div>'
                 f'</div>')
        pairs_html += (f'<div style="display:grid;grid-template-columns:minmax(0,1fr) minmax(0,2fr);gap:10px;margin-bottom:10px;align-items:start">'
                       f'<div style="min-width:0;overflow:hidden">{left}</div><div style="min-width:0;overflow:hidden">{right}</div></div>')

    # 자가피드백은 없지만 일정사진/상세내용/상담일지가 있는 슬롯 추가 표시
    for i, col in enumerate(FB_TEXTS):
        slot_idx = i + 1
        if slot_idx in rendered: continue
        fp_raw = gs(d.get(f'_fp_{i}', ''))
        ff_raw = gs(d.get(f'_ff_{i}', ''))
        detail_val = gs(d.get(f'_fd_{i}', ''))
        fp = pf(fp_raw)
        ff = pf(ff_raw)
        sp_imgs_list = [f for f in fp if ft(f)=="photo"]
        c_imgs_list = [f for f in ff if ft(f)=="photo"]
        sp_imgs = ''.join(img_tag(u) for u in sp_imgs_list)
        c_imgs = ''.join(img_tag(u) for u in c_imgs_list)
        if not (sp_imgs or detail_val or c_imgs): continue

        # 상세내용에서 업체명 파싱 시도
        biz_match = re.search(r'업체명\s*[:：]\s*([^\n]+)', detail_val) if detail_val else None
        biz = biz_match.group(1).strip() if biz_match else f"상담 {slot_idx}"

        sched_row = ''
        if sp_imgs or detail_val:
            sched_row = (f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-bottom:8px">'
                        + (f'<div style="border:0.5px solid #e6e9ef;border-radius:8px;overflow:hidden"><div style="background:#e8f0fe;padding:5px 8px;border-bottom:0.5px solid #e6e9ef;font-size:9px;font-weight:700;color:#1565c0">&#128247; 일정사진</div><div style="padding:6px 8px;max-height:130px;overflow:hidden">{sp_imgs}</div></div>' if sp_imgs else '<div></div>')
                        + (f'<div style="border:0.5px solid #e6e9ef;border-radius:8px;overflow:hidden"><div style="background:#e8f0fe;padding:5px 8px;border-bottom:0.5px solid #e6e9ef;font-size:9px;font-weight:700;color:#1565c0">&#128203; 상세내용</div><div style="padding:6px 8px;font-size:11px;color:#323338;line-height:1.6;white-space:pre-wrap;word-break:break-word">{esc(detail_val)}</div></div>' if detail_val else '<div></div>')
                        + f'</div>')
        fb_box = (f'<div style="border:0.5px solid #e6e9ef;border-radius:8px;overflow:hidden">'
                + f'<div style="background:#fafbfc;padding:6px 10px;border-bottom:0.5px solid #e6e9ef;font-size:10px;font-weight:700;color:#aaa">&#127970; {esc(biz)} <span style="font-size:9px;color:#ccc">(자가피드백 미입력)</span></div>'
                + f'<div style="padding:8px 10px;font-size:12px;color:#ccc">미입력</div>'
                + f'</div>')
        left = f'<div style="display:flex;flex-direction:column;gap:0">{sched_row}{fb_box}</div>'
        right = (f'<div style="border:0.5px solid #e6e9ef;border-radius:8px;overflow:hidden">'
                 f'<div style="background:#fafbfc;padding:6px 10px;border-bottom:0.5px solid #e6e9ef;font-size:10px;font-weight:700;color:#323338">&#128203; {esc(biz)} 상담일지</div>'
                 f'<div style="padding:8px 10px">{c_imgs if c_imgs else "<span style=font-size:10px;color:#ccc>없음</span>"}</div>'
                 f'</div>')
        pairs_html += (f'<div style="display:grid;grid-template-columns:minmax(0,1fr) minmax(0,2fr);gap:10px;margin-bottom:10px;align-items:start">'
                       f'<div style="min-width:0;overflow:hidden">{left}</div><div style="min-width:0;overflow:hidden">{right}</div></div>')

    fb_section = (f'<div style="font-size:10px;font-weight:700;color:#e2445c;margin-bottom:8px;text-transform:uppercase">상담 자가피드백 &amp; 상담일지</div>'
                  f'{pairs_html or "<span style=font-size:12px;color:#ccc>없음</span>"}')

    return (f'<div style="background:#fff;border:0.5px solid #e6e9ef;border-radius:12px;overflow:hidden;margin-bottom:14px">'
            f'<div style="padding:11px 14px;border-bottom:0.5px solid #e6e9ef;display:flex;align-items:center;gap:10px;background:#fafbfc">'
            f'<div style="width:34px;height:34px;border-radius:50%;background:{bg};color:{tx};display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:700;flex-shrink:0">{ini}</div>'
            f'<div><div style="font-size:13px;font-weight:700;color:#323338">{esc(p["name"])}</div><div style="font-size:11px;color:#676879">{d.get("weekday","")}</div></div>'
            f'<div style="margin-left:auto;display:flex;gap:4px;flex-wrap:wrap;justify-content:flex-end">{confirm_badge}{new_b}{con_b}{fee_b}</div>'
            f'</div>{photos_row}{report_row}'
            f'<div style="padding:11px 13px">{fb_section}</div></div>')


def build_nav_js(year, month, today_str, archive_months):
    """주차 네비게이션 + 월 탭 JS/HTML 생성"""
    weeks = get_weeks_in_month(year, month)
    today = (datetime.datetime.utcnow() + datetime.timedelta(hours=9)).date()

    # 월 탭 HTML
    month_tabs_html = ''
    for am in archive_months:
        ay, amm = am['year'], am['month']
        label = f'{ay}년 {amm}월'
        if am['is_current']:
            month_tabs_html += f'<span class="mtab mtab-active">{label}</span>'
        else:
            archive_file = f'archive/{ay}-{amm:02d}/{{team}}.html'
            month_tabs_html += f'<a class="mtab" href="{archive_file}">&#128193; {label}</a>'

    # 주차 행 HTML (1주차 위, 오름차순)
    weeks_html = ''
    for w in weeks:
        wnum = w['week_num']
        day_cells = ''
        for d in w['days']:
            ds = str(d)
            wd_names = ['월','화','수','목','금']
            wd_name = wd_names[d.weekday()]
            date_label = f'{d.month}/{d.day}'
            is_today = (d == today)
            is_future = (d > today)
            if is_future:
                day_cells += f'<div class="dtab dtab-disabled"><span class="dname">{wd_name}</span>{date_label}</div>'
            elif is_today:
                day_cells += f'<div class="dtab dtab-today" onclick="selectDay(this,\'{ds}\')" data-date="{ds}"><span class="dname">{wd_name}</span>{date_label} ●</div>'
            else:
                day_cells += f'<div class="dtab" onclick="selectDay(this,\'{ds}\')" data-date="{ds}"><span class="dname">{wd_name}</span>{date_label}</div>'

        weeks_html += (f'<div class="week-row">'
                       f'<div class="week-label">{wnum}주차</div>'
                       f'<div class="day-cells">{day_cells}</div>'
                       f'</div>')

    return month_tabs_html, weeks_html


def make_html(team_key, persons, today, year, month, archive_months, report_data=None):
    team = TEAMS[team_key]
    now = datetime.datetime.now().strftime('%Y.%m.%d %H:%M')
    # 첫 번째 카드에 first-card 클래스 추가 (nav-section과 직선 연결)
    cards_list = [render_card(p, today) for p in persons]
    if cards_list:
        cards_list[0] = cards_list[0].replace('<div style="background:#fff;border:0.5px solid #e6e9ef;border-radius:12px;', '<div style="background:#fff;border:0.5px solid #e6e9ef;border-top:none;border-radius:0 0 12px 12px;', 1)
    cards = ''.join(cards_list)

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

    month_tabs_html, weeks_html = build_nav_js(year, month, today, archive_months)
    month_tabs_html = month_tabs_html.replace('{team}', team_key)

    # 보고서 섹션
    report_section_html = ''
    if report_data is not None:
        report_section_html = render_report_section(team_key, report_data, archive_months)

    nav_html = f'''
{report_section_html}
<div class="nav-section" id="month-section">
  <div class="nav-section-hdr" onclick="toggleNavSection()">
    <span style="font-size:12px;font-weight:700;color:#323338">&#128197; 일간 업무 보고</span>
    <div style="display:flex;gap:6px;flex-wrap:wrap">{month_tabs_html}</div>
    <span style="margin-left:auto;font-size:10px;color:#aaa">&#128193; 이전 달은 아카이브</span>
    <span id="nav-chv" style="font-size:12px;color:#aaa;margin-left:6px">▲</span>
  </div>
  <div id="nav-body" style="padding:10px 14px 0 14px">
    <div style="font-size:11px;color:#676879;margin-bottom:8px">주차 선택 후 날짜를 클릭하세요</div>
    <div id="week-nav">{weeks_html}</div>
  </div>
</div>
<div id="cards-wrap">{cards}</div>
'''

    nav_css = '''
<style>
.mtab{display:inline-block;padding:3px 12px;border-radius:20px;font-size:11px;border:0.5px solid #e6e9ef;background:#fff;color:#676879;text-decoration:none;cursor:pointer}
.mtab-active{background:#0073ea;color:#fff;border-color:#0073ea}
.nav-section{background:#fff;border:0.5px solid #e6e9ef;border-radius:12px;overflow:hidden;margin-bottom:14px}
.nav-section-hdr{padding:10px 14px;border-bottom:0.5px solid #e6e9ef;background:#fafbfc;display:flex;align-items:center;gap:8px;flex-wrap:wrap;cursor:pointer;user-select:none}
.week-row{display:flex;align-items:stretch;border:0.5px solid #e6e9ef;border-radius:8px;overflow:hidden;margin-bottom:6px}
.week-label{padding:7px 12px;font-size:11px;font-weight:700;color:#676879;background:#fafbfc;border-right:0.5px solid #e6e9ef;min-width:52px;display:flex;align-items:center;cursor:default}
.day-cells{display:flex;flex:1}
.dtab{flex:1;padding:7px 4px;text-align:center;font-size:11px;cursor:pointer;border-right:0.5px solid #e6e9ef;color:#323338;background:#fff;transition:background 0.1s}
.dtab:last-child{border-right:none}
.dtab:hover{background:#f0f4ff}
.dtab-active{background:#0073ea;color:#fff;font-weight:700}
.dtab-today{color:#0073ea;font-weight:700}
.dtab-today.dtab-active{background:#0073ea;color:#fff}
.dtab-disabled{flex:1;padding:7px 4px;text-align:center;font-size:11px;color:#ccc;background:#fafbfc;border-right:0.5px solid #e6e9ef}
.dtab-disabled:last-child{border-right:none}
.dname{display:block;font-size:10px;opacity:0.7}
.rpt-section{background:#fff;border:0.5px solid #e6e9ef;border-radius:12px;overflow:hidden;margin-bottom:14px}
.rpt-shdr{padding:10px 14px;background:#fafbfc;border-bottom:0.5px solid #e6e9ef;display:flex;align-items:center;gap:8px;cursor:pointer;user-select:none}
.rpt-mtab{display:inline-block;padding:3px 12px;border-radius:20px;font-size:11px;border:0.5px solid #e6e9ef;background:#fff;color:#676879;cursor:pointer}
.rpt-mtab-active{background:#0073ea;color:#fff;border-color:#0073ea}
.rpt-member{border:0.5px solid #e6e9ef;border-radius:8px;overflow:hidden;margin-bottom:8px}
.rpt-mhdr{padding:8px 12px;background:#fafbfc;display:flex;align-items:center;gap:8px;cursor:pointer}
.rpt-mhdr:hover{background:#f0f4ff}
.rpt-badge{font-size:10px;color:#676879;white-space:nowrap}
.rpt-badge b{color:#323338}
.rpt-chv{font-size:11px;color:#aaa;transition:transform 0.2s}
.rpt-chv.open{transform:rotate(180deg)}
.rpt-table{width:100%;border-collapse:collapse;font-size:11px}
.rpt-table th{padding:6px 8px;background:#fafbfc;color:#676879;font-weight:400;text-align:center;border-bottom:0.5px solid #e6e9ef;border-right:0.5px solid #e6e9ef;white-space:nowrap}
.rpt-table th:last-child{border-right:none}
.rpt-table td{padding:5px 8px;text-align:center;border-bottom:0.5px solid #e6e9ef;border-right:0.5px solid #e6e9ef;color:#323338}
.rpt-table td:last-child{border-right:none}
.rpt-table td:first-child{text-align:left;color:#676879;white-space:nowrap}
.rpt-table tr:last-child td{border-bottom:none}
.rpt-sum td{background:#e8f0fe;color:#1565c0;font-weight:500}
.rpt-team-sum{background:#fafbfc;border-radius:8px;padding:10px 12px;margin-top:8px;border:0.5px solid #e6e9ef}
</style>
'''

    all_dates = []
    cal = calendar.Calendar(0)
    for week in cal.monthdatescalendar(year, month):
        for d in week:
            if d.weekday() < 5 and d.month == month:
                all_dates.append(str(d))

    cards_by_date = {}
    today_dt = datetime.date.fromisoformat(today)
    for ds in all_dates:
        if datetime.date.fromisoformat(ds) <= today_dt:
            cl = [render_card(p, ds) for p in persons]
            if cl:
                cl[0] = cl[0].replace('<div style="background:#fff;border:0.5px solid #e6e9ef;border-radius:12px;', '<div style="background:#fff;border:0.5px solid #e6e9ef;border-top:none;border-radius:0 0 12px 12px;', 1)
            cards_by_date[ds] = ''.join(cl)

    cards_json = json.dumps(cards_by_date, ensure_ascii=False)

    nav_js = f'''
<script>
var cardsData = {cards_json};
var navOpen = true;
function toggleNavSection(){{
  navOpen=!navOpen;
  var body=document.getElementById('nav-body');
  var chv=document.getElementById('nav-chv');
  body.style.display=navOpen?'':'none';
  chv.textContent=navOpen?'▲':'▼';
}}
function selectDay(el, dateStr) {{
  document.querySelectorAll('.dtab').forEach(function(t) {{
    t.classList.remove('dtab-active');
  }});
  el.classList.add('dtab-active');
  var wrap = document.getElementById('cards-wrap');
  if (cardsData[dateStr]) {{
    wrap.innerHTML = cardsData[dateStr];
    initAudios();
  }} else {{
    wrap.innerHTML = '<div style="text-align:center;padding:40px;color:#aaa;font-size:13px">해당 날짜 데이터가 없습니다</div>';
  }}
}}
var rptOpen=true;
function toggleRptSection(){{
  rptOpen=!rptOpen;
  var body=document.getElementById('rpt-body');
  var chv=document.getElementById('rpt-chv-main');
  body.style.display=rptOpen?'':'none';
  chv.textContent=rptOpen?'▲':'▼';
}}
function switchRptMonth(mid){{
  document.querySelectorAll('.rpt-mtab').forEach(function(t){{t.classList.remove('rpt-mtab-active');}});
  document.querySelectorAll('[id^="rpt-month-"]').forEach(function(el){{el.style.display='none';}});
  var el=document.getElementById('rpt-month-'+mid);
  if(el)el.style.display='';
  event.target.classList.add('rpt-mtab-active');
  var parts=mid.split('-');
  document.getElementById('rpt-month-label').textContent='— '+parts[0]+'년 '+parseInt(parts[1])+'월';
}}
function toggleRpt(mid){{
  var body=document.getElementById('rpt-'+mid);
  var chv=document.getElementById('chv-'+mid);
  if(body.style.display==='none'){{body.style.display='';if(chv)chv.classList.add('open');}}
  else{{body.style.display='none';if(chv)chv.classList.remove('open');}}
}}
function apToggle(aid){{
  var a=document.getElementById(aid);
  var btn=document.getElementById(aid+'_btn');
  if(a.paused){{a.play();btn.innerHTML='&#9646;&#9646;';}}
  else{{a.pause();btn.innerHTML='&#9654;';}}
}}
function apSeek(aid,sec){{
  var a=document.getElementById(aid);
  a.currentTime=Math.max(0,Math.min(a.duration||0,a.currentTime+sec));
}}
function apClick(aid,e,bar){{
  var a=document.getElementById(aid);
  var rect=bar.getBoundingClientRect();
  var ratio=(e.clientX-rect.left)/rect.width;
  a.currentTime=(a.duration||0)*ratio;
}}
function fmtTime(s){{
  if(isNaN(s))return'0:00';
  var m=Math.floor(s/60),sec=Math.floor(s%60);
  return m+':'+(sec<10?'0':'')+sec;
}}
function initAudios(){{
  document.querySelectorAll('audio').forEach(function(a){{
    var aid=a.id;
    a.addEventListener('timeupdate',function(){{
      var bar=document.getElementById(aid+'_bar');
      var time=document.getElementById(aid+'_time');
      if(bar&&a.duration)bar.style.width=(a.currentTime/a.duration*100)+'%';
      if(time)time.textContent=fmtTime(a.currentTime)+' / '+fmtTime(a.duration);
    }});
    a.addEventListener('ended',function(){{
      var btn=document.getElementById(aid+'_btn');
      if(btn)btn.innerHTML='&#9654;';
    }});
    a.addEventListener('loadedmetadata',function(){{
      var time=document.getElementById(aid+'_time');
      if(time)time.textContent='0:00 / '+fmtTime(a.duration);
    }});
  }});
}}
var activeAid=null;
document.addEventListener('keydown',function(e){{
  if(e.key==='Escape')document.getElementById('lb').style.display='none';
  if((e.key==='ArrowRight'||e.key==='ArrowLeft')&&activeAid){{
    e.preventDefault();
    apSeek(activeAid,e.key==='ArrowRight'?10:-10);
  }}
}});
document.addEventListener('click',function(e){{
  var wrap=e.target.closest('.ap-wrap');
  if(wrap)activeAid=wrap.dataset.aid;
}});
function openLb(src){{var lb=document.getElementById("lb");document.getElementById("lbi").src=src;lb.style.display="flex";}}
window.addEventListener('load',initAudios);
</script>
'''

    return (f'<!DOCTYPE html><html lang="ko"><head><meta charset="UTF-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1.0">'
            f'<title>{team["name"]} 일간 보고</title>'
            f'<style>*{{box-sizing:border-box;margin:0;padding:0}}body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans KR",sans-serif;background:#f5f6f8;color:#323338;font-size:13px}}.wrap{{max-width:900px;margin:0 auto;padding:12px 14px}}'
            f'.mtab{{display:inline-block;padding:3px 12px;border-radius:20px;font-size:11px;border:0.5px solid #e6e9ef;background:#fff;color:#676879;text-decoration:none;cursor:pointer}}'
            f'.mtab-active{{background:#0073ea;color:#fff;border-color:#0073ea}}'
            f'.nav-section{{background:#fff;border:0.5px solid #e6e9ef;border-radius:12px 12px 0 0;overflow:hidden;margin-bottom:0;border-bottom:none}}'
            f'.first-card{{border-top:none!important;border-radius:0 0 12px 12px!important;margin-top:0!important}}'
            f'.nav-section-hdr{{padding:10px 14px;border-bottom:0.5px solid #e6e9ef;background:#fafbfc;display:flex;align-items:center;gap:8px;flex-wrap:wrap;cursor:pointer;user-select:none}}'
            f'.week-row{{display:flex;align-items:stretch;border:0.5px solid #e6e9ef;border-radius:8px;overflow:hidden;margin-bottom:6px}}'
            f'.week-label{{padding:7px 12px;font-size:11px;font-weight:700;color:#676879;background:#fafbfc;border-right:0.5px solid #e6e9ef;min-width:52px;display:flex;align-items:center;cursor:default}}'
            f'.day-cells{{display:flex;flex:1}}'
            f'.dtab{{flex:1;padding:7px 4px;text-align:center;font-size:11px;cursor:pointer;border-right:0.5px solid #e6e9ef;color:#323338;background:#fff;transition:background 0.1s}}'
            f'.dtab:last-child{{border-right:none}}'
            f'.dtab:hover{{background:#f0f4ff}}'
            f'.dtab-active{{background:#0073ea;color:#fff;font-weight:700}}'
            f'.dtab-today{{color:#0073ea;font-weight:700}}'
            f'.dtab-today.dtab-active{{background:#0073ea;color:#fff}}'
            f'.dtab-disabled{{flex:1;padding:7px 4px;text-align:center;font-size:11px;color:#ccc;background:#fafbfc;border-right:0.5px solid #e6e9ef}}'
            f'.dtab-disabled:last-child{{border-right:none}}'
            f'.dname{{display:block;font-size:10px;opacity:0.7}}'
            f'.rpt-section{{background:#fff;border:0.5px solid #e6e9ef;border-radius:12px;overflow:hidden;margin-bottom:14px}}'
            f'.rpt-shdr{{padding:10px 14px;background:#fafbfc;border-bottom:0.5px solid #e6e9ef;display:flex;align-items:center;gap:8px;cursor:pointer;user-select:none}}'
            f'.rpt-mtab{{display:inline-block;padding:3px 12px;border-radius:20px;font-size:11px;border:0.5px solid #e6e9ef;background:#fff;color:#676879;cursor:pointer}}'
            f'.rpt-mtab-active{{background:#0073ea;color:#fff;border-color:#0073ea}}'
            f'.rpt-member{{border:0.5px solid #e6e9ef;border-radius:8px;overflow:hidden;margin-bottom:8px}}'
            f'.rpt-mhdr{{padding:8px 12px;background:#fafbfc;display:flex;align-items:center;gap:8px;cursor:pointer}}'
            f'.rpt-mhdr:hover{{background:#f0f4ff}}'
            f'.rpt-badge{{font-size:10px;color:#676879;white-space:nowrap}}'
            f'.rpt-badge b{{color:#323338}}'
            f'.rpt-chv{{font-size:11px;color:#aaa;transition:transform 0.2s}}'
            f'.rpt-chv.open{{transform:rotate(180deg)}}'
            f'.rpt-table{{width:100%;border-collapse:collapse;font-size:11px}}'
            f'.rpt-table th{{padding:6px 8px;background:#fafbfc;color:#676879;font-weight:400;text-align:center;border-bottom:0.5px solid #e6e9ef;border-right:0.5px solid #e6e9ef;white-space:nowrap}}'
            f'.rpt-table th:last-child{{border-right:none}}'
            f'.rpt-table td{{padding:5px 8px;text-align:center;border-bottom:0.5px solid #e6e9ef;border-right:0.5px solid #e6e9ef;color:#323338}}'
            f'.rpt-table td:last-child{{border-right:none}}'
            f'.rpt-table td:first-child{{text-align:left;color:#676879;white-space:nowrap}}'
            f'.rpt-table tr:last-child td{{border-bottom:none}}'
            f'.rpt-sum td{{background:#e8f0fe;color:#1565c0;font-weight:500}}'
            f'.rpt-team-sum{{background:#fafbfc;border-radius:8px;padding:10px 12px;margin-top:8px;border:0.5px solid #e6e9ef}}'
            f'</style>'
            f'</head><body><div class="wrap">'
            f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:14px;flex-wrap:wrap">'
            f'<div style="font-size:14px;font-weight:700;color:#323338;display:flex;align-items:center;gap:6px">'
            f'<div style="width:8px;height:8px;border-radius:50%;background:{team["color"]}"></div>'
            f'{team["name"]} 일간 보고 &mdash; {today}'
            f'<span style="font-size:11px;color:#676879;margin-left:6px">업데이트 {now}</span></div>'
            f'<div style="margin-left:auto;display:flex;gap:6px;flex-wrap:wrap">'
            f'<div style="background:#fff;padding:4px 10px;border-radius:6px;border:0.5px solid #e6e9ef;font-size:11px;color:#676879">신규 <b style="color:#323338">{total_new}건</b></div>'
            f'<div style="background:#fff;padding:4px 10px;border-radius:6px;border:0.5px solid #e6e9ef;font-size:11px;color:#676879">계약 <b style="color:#323338">{total_contract:.0f}건</b></div>'
            f'<div style="background:#fff;padding:4px 10px;border-radius:6px;border:0.5px solid #e6e9ef;font-size:11px;color:#676879">컨펌 <b style="color:#323338">{total_confirm}/{len(persons)}</b></div>'
            f'</div></div>'
            f'{nav_html}'
            f'<div id="lb" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.9);z-index:9999;align-items:center;justify-content:center" onclick="this.style.display=\'none\'">'
            f'<img id="lbi" style="max-width:95vw;max-height:95vh;border-radius:8px;object-fit:contain"></div>'
            f'{nav_js}'
            f'</div></body></html>')


def make_archive_html(team_key, persons, year, month, all_persons_days):
    """월별 아카이브 HTML - 해당 월 전체 데이터 포함"""
    team = TEAMS[team_key]
    now = datetime.datetime.now().strftime('%Y.%m.%d %H:%M')
    weeks = get_weeks_in_month(year, month)

    # 이 달의 모든 평일 날짜 중 첫 번째를 기본 표시
    all_weekdays = []
    for w in weeks:
        for d in w['days']:
            all_weekdays.append(str(d))

    default_date = all_weekdays[-1] if all_weekdays else f'{year}-{month:02d}-01'

    # 날짜별 카드 데이터
    cards_by_date = {}
    for ds in all_weekdays:
        cards_by_date[ds] = ''.join(render_card(p, ds) for p in persons)

    cards_json = json.dumps(cards_by_date, ensure_ascii=False)
    default_cards = cards_by_date.get(default_date, '')

    # 주차 네비게이션
    weeks_html = ''
    for w in weeks:
        wnum = w['week_num']
        day_cells = ''
        for d in w['days']:
            ds = str(d)
            wd_names = ['월','화','수','목','금']
            wd_name = wd_names[d.weekday()]
            date_label = f'{d.month}/{d.day}'
            is_default = (ds == default_date)
            cls = 'dtab dtab-active' if is_default else 'dtab'
            day_cells += f'<div class="{cls}" onclick="selectDay(this,\'{ds}\')" data-date="{ds}"><span class="dname">{wd_name}</span>{date_label}</div>'
        weeks_html += (f'<div class="week-row">'
                       f'<div class="week-label">{wnum}주차</div>'
                       f'<div class="day-cells">{day_cells}</div>'
                       f'</div>')

    nav_css = '''<style>
.week-row{display:flex;align-items:stretch;border:0.5px solid #e6e9ef;border-radius:8px;overflow:hidden;margin-bottom:6px}
.week-label{padding:7px 12px;font-size:11px;font-weight:700;color:#676879;background:#fafbfc;border-right:0.5px solid #e6e9ef;min-width:52px;display:flex;align-items:center}
.day-cells{display:flex;flex:1}
.dtab{flex:1;padding:7px 4px;text-align:center;font-size:11px;cursor:pointer;border-right:0.5px solid #e6e9ef;color:#323338;background:#fff}
.dtab:last-child{border-right:none}
.dtab:hover{background:#f0f4ff}
.dtab-active{background:#0073ea;color:#fff;font-weight:700}
.dtab-disabled{flex:1;padding:7px 4px;text-align:center;font-size:11px;color:#ccc;background:#fafbfc;border-right:0.5px solid #e6e9ef}
.dname{display:block;font-size:10px;opacity:0.7}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans KR",sans-serif;background:#f5f6f8;color:#323338;font-size:13px}
.wrap{max-width:900px;margin:0 auto;padding:12px 14px}
</style>'''

    return (f'<!DOCTYPE html><html lang="ko"><head><meta charset="UTF-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1.0">'
            f'<title>{team["name"]} {year}년 {month}월 아카이브</title>'
            f'{nav_css}'
            f'</head><body><div class="wrap">'
            f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:14px;flex-wrap:wrap">'
            f'<div style="font-size:14px;font-weight:700;color:#323338;display:flex;align-items:center;gap:6px">'
            f'<div style="width:8px;height:8px;border-radius:50%;background:{team["color"]}"></div>'
            f'{team["name"]} {year}년 {month}월 아카이브'
            f'<span style="font-size:11px;color:#676879;margin-left:6px">저장 {now}</span></div>'
            f'<a href="../../{team_key}.html" style="margin-left:auto;font-size:11px;color:#0073ea;text-decoration:none">&#8592; 현재 대시보드</a>'
            f'</div>'
            f'<div style="background:#fff;border:0.5px solid #e6e9ef;border-radius:12px;overflow:hidden;margin-bottom:14px">'
            f'<div style="padding:10px 14px;border-bottom:0.5px solid #e6e9ef;background:#fafbfc">'
            f'<div style="font-size:11px;color:#676879;margin-bottom:8px">날짜를 클릭하세요</div>'
            f'<div>{weeks_html}</div></div></div>'
            f'<div id="cards-wrap">{default_cards}</div>'
            f'<div id="lb" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.9);z-index:9999;align-items:center;justify-content:center" onclick="this.style.display=\'none\'">'
            f'<img id="lbi" style="max-width:95vw;max-height:95vh;border-radius:8px;object-fit:contain"></div>'
            f'<script>'
            f'var cardsData={cards_json};'
            f'function selectDay(el,dateStr){{'
            f'document.querySelectorAll(".dtab").forEach(function(t){{t.classList.remove("dtab-active");}});'
            f'el.classList.add("dtab-active");'
            f'var wrap=document.getElementById("cards-wrap");'
            f'wrap.innerHTML=cardsData[dateStr]||"<div style=text-align:center;padding:40px;color:#aaa;font-size:13px>데이터 없음</div>";'
            f'initAudios();'
            f'}}'
            f'function apToggle(aid){{var a=document.getElementById(aid);var btn=document.getElementById(aid+"_btn");if(a.paused){{a.play();btn.innerHTML="&#9646;&#9646;"}}else{{a.pause();btn.innerHTML="&#9654;"}}}}'
            f'function apSeek(aid,sec){{var a=document.getElementById(aid);a.currentTime=Math.max(0,Math.min(a.duration||0,a.currentTime+sec));}}'
            f'function apClick(aid,e,bar){{var a=document.getElementById(aid);var rect=bar.getBoundingClientRect();a.currentTime=(a.duration||0)*((e.clientX-rect.left)/rect.width);}}'
            f'function fmtTime(s){{if(isNaN(s))return"0:00";var m=Math.floor(s/60),sec=Math.floor(s%60);return m+":"+(sec<10?"0":"")+sec;}}'
            f'function initAudios(){{document.querySelectorAll("audio").forEach(function(a){{var aid=a.id;'
            f'a.addEventListener("timeupdate",function(){{var bar=document.getElementById(aid+"_bar");var time=document.getElementById(aid+"_time");if(bar&&a.duration)bar.style.width=(a.currentTime/a.duration*100)+"%";if(time)time.textContent=fmtTime(a.currentTime)+" / "+fmtTime(a.duration);}});'
            f'a.addEventListener("ended",function(){{var btn=document.getElementById(aid+"_btn");if(btn)btn.innerHTML="&#9654;";}});'
            f'a.addEventListener("loadedmetadata",function(){{var time=document.getElementById(aid+"_time");if(time)time.textContent="0:00 / "+fmtTime(a.duration);}});}});}}'
            f'var activeAid=null;'
            f'document.addEventListener("click",function(e){{var w=e.target.closest(".ap-wrap");if(w)activeAid=w.dataset.aid;}});'
            f'document.addEventListener("keydown",function(e){{'
            f'if(e.key==="Escape")document.getElementById("lb").style.display="none";'
            f'if((e.key==="ArrowRight"||e.key==="ArrowLeft")&&activeAid){{e.preventDefault();apSeek(activeAid,e.key==="ArrowRight"?10:-10);}}'
            f'}});'
            f'function openLb(src){{var lb=document.getElementById("lb");document.getElementById("lbi").src=src;lb.style.display="flex";}}'
            f'window.addEventListener("load",initAudios);'
            f'</script>'
            f'</div></body></html>')


# ── 메인 실행 ──────────────────────────────────────────────
print("monday.com 데이터 불러오는 중...")
items = fetch_board()
all_persons = parse_items(items)
today = get_today()
today_dt = datetime.date.fromisoformat(today)
year = today_dt.year
month = today_dt.month

print(f"오늘 날짜: {today}, 팀원 수: {len(all_persons)}")

# 보고서 보드 데이터 fetch
print("영업팀 일간 보고서 보드 불러오는 중...")
try:
    report_items = fetch_report_board()
    report_data = parse_report_items(report_items)
    print(f"보고서 데이터: {len(report_data)}명")
except Exception as e:
    print(f"보고서 보드 fetch 실패: {e}")
    report_data = {}

# 최근 3개월 탭 정보
archive_months = get_month_tabs(year, month)

files = {'team1':'team1.html','team2':'team2.html','cheongju':'cheongju.html'}
for team_key, filename in files.items():
    members = TEAMS[team_key]['members']
    team_persons = [p for p in all_persons if any(m in p['name'] for m in members)]
    html = make_html(team_key, team_persons, today, year, month, archive_months, report_data)
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"{TEAMS[team_key]['name']}: {len(team_persons)}명 → {filename} 생성완료")

# ── 월말 아카이브 (말일이거나 수동 실행 시 FORCE_ARCHIVE=1) ──
last_day = calendar.monthrange(year, month)[1]
is_last_workday = False
check = datetime.date(year, month, last_day)
while check.weekday() >= 5:
    check -= datetime.timedelta(days=1)
is_last_workday = (today_dt == check)

if is_last_workday or os.environ.get('FORCE_ARCHIVE') == '1':
    print(f"월말 아카이브 생성 중: {year}-{month:02d}")
    archive_dir = f'archive/{year}-{month:02d}'
    os.makedirs(archive_dir, exist_ok=True)
    for team_key in files:
        members = TEAMS[team_key]['members']
        team_persons = [p for p in all_persons if any(m in p['name'] for m in members)]
        html = make_archive_html(team_key, team_persons, year, month, None)
        with open(f'{archive_dir}/{team_key}.html', 'w', encoding='utf-8') as f:
            f.write(html)
        print(f"  아카이브: {archive_dir}/{team_key}.html")
