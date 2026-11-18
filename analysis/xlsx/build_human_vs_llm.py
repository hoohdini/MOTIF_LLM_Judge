import json, re, csv, sys, glob
from collections import defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(ROOT))
from kcaudit.aggregate import Registry
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo
from openpyxl.formatting.rule import FormulaRule

reg=Registry('checks.yaml',ROOT); GROUP={'card':'atom_audit','item':'item_audit'}
PH={s:reg.prompt_hash(g) for s,g in GROUP.items()}
SKIP={'NO_OVERLAP','CENTRALITY','NO_INTRA_CARD_OVERLAP','CONCEPT_SCOPE'}
CH={s:[c for c in reg.groups[g]['checks'] if c not in SKIP] for s,g in GROUP.items()}
ORDER={'fail':3,'hold':2,'revise':1,'pass':0}
rows=[json.loads(l) for l in open(ROOT/'store/ledger/verdicts.jsonl',encoding='utf-8')]
llm=defaultdict(lambda: defaultdict(dict)); hum=defaultdict(list)
for r in rows:
    st=r['stage']
    if r['judge'] in('judge_a','judge_b') and r.get('prompt_hash')==PH.get(st): llm[(st,r['unit_id'])][r['check']][r['judge']]=(r['v'],r.get('why',''))
    elif r['judge'].startswith('human:'): hum[(st,r['unit_id'])].append(r)
adj={r['unit_id']:r for r in csv.DictReader(open(ROOT/'analysis/results/adjudication_p1.csv',encoding='utf-8-sig'))}
fix={r['unit_id']:r for r in csv.DictReader(open(ROOT/'analysis/results/review_fix_1118.csv',encoding='utf-8-sig'))}
items={json.loads(l)['item_id']:json.loads(l) for l in open(ROOT/'store/snapshots/items/d68da57f36d7/items.jsonl',encoding='utf-8')}
cards=[json.loads(l) for l in open(glob.glob(str(ROOT/'store/snapshots/cards/3fe7b34e8c59/*.jsonl'))[0],encoding='utf-8')]
atoms={a['atom_id']:(c,a) for c in cards for a in c['atoms']}

def unit(st,u,j):
    vs=[cs[j][0] for c,cs in llm[(st,u)].items() if c in CH[st] and j in cs]
    return max(vs,key=lambda v:ORDER.get(v,1)) if vs else ''
def flags(st,u,j):
    out=[]
    for c in CH[st]:
        x=llm[(st,u)].get(c,{}).get(j)
        if x and x[0]!='pass': out.append(f"{c}={x[0]}: {x[1]}")
    return '\n'.join(out)
def cited(note,st): return ', '.join(c for c in CH[st] if re.search(rf'\b{c}\b',note or ''))

def human_rows(st,u):
    """[(출처, 채점자, 판정, 메모, 지적 조건)]"""
    out=[]
    by=defaultdict(list)
    for r in hum[(st,u)]: by[(r.get('extra') or {}).get('source')].append(r)
    if by.get('calib'):
        r=by['calib'][-1]; out.append(('보정 라벨',r['judge'].split(':',1)[1],r['v'],r.get('why',''),cited(r.get('why'),st) if r['v']!='pass' else ''))
    rv=by.get('sample',[])+by.get('queue',[])
    if rv:
        q=[r for r in rv if r['check']!='_UNIT']
        if q:
            bad=[r['check'] for r in q if r['v']!='pass']; v='fail' if bad else 'pass'
            out.append(('11/18 검토(보류)',q[-1]['judge'].split(':',1)[1],v,' / '.join(r.get('why','') for r in q if r.get('why')),', '.join(bad)))
        else:
            r=rv[-1]; out.append(('11/18 검토(표본)',r['judge'].split(':',1)[1],r['v'],r.get('why',''),''))
    return out

thin=Side(style='thin',color='D0D0D0'); F=Font(name='Arial',size=10); HF=Font(name='Arial',size=10,bold=True,color='FFFFFF')
HFILL=PatternFill('solid',fgColor='305496'); WR=Alignment(wrap_text=True,vertical='top')

def sheet(wb,title,headers,data,widths,tname):
    ws=wb.create_sheet(title)
    ws.append(headers)
    for d in data: ws.append(d)
    n=len(data)+1
    for c in range(1,len(headers)+1):
        h=ws.cell(1,c); h.font=HF; h.fill=HFILL; h.alignment=Alignment(wrap_text=True,vertical='center')
        ws.column_dimensions[get_column_letter(c)].width=widths[c-1]
    for row in ws.iter_rows(min_row=2,max_row=n):
        for cell in row: cell.font=F; cell.alignment=WR
    ws.freeze_panes='C2'
    t=Table(displayName=tname,ref=f"A1:{get_column_letter(len(headers))}{n}")
    t.tableStyleInfo=TableStyleInfo(name='TableStyleLight9',showRowStripes=True); ws.add_table(t)
    for r in range(2,n+1): ws.row_dimensions[r].height=60
    return ws,n

wb=Workbook(); wb.remove(wb.active)

# ---------- atom ----------
H=['unit_id','도서','사람 판정 출처','채점자','사람 판정','사람 메모','사람이 지적한 조건','GPT 판정','Gemini 판정','LLM 합산','이진 비교','재판정 결과','재판정: 누가 맞았나','GPT 지적 (조건=판정: 이유)','Gemini 지적 (조건=판정: 이유)','atom 범위','atom 내용','근거 문장']
data=[]
for (st,u),hs in sorted(hum.items()):
    if st!='card' or u not in atoms: continue
    c,a=atoms[u]; ga,gb=unit(st,u,'judge_a'),unit(st,u,'judge_b')
    for src,who,v,note,fl in human_rows(st,u):
        data.append([u,u.split('-')[0],src,who,v,note,fl,ga,gb,None,None,adj[u]['adjudicated_v'] if u in adj else '',adj[u]['who_was_right'] if u in adj else '',flags(st,u,'judge_a'),flags(st,u,'judge_b'),a['scope'],a['statement'],'\n'.join(f"[{e['id']} p.{e.get('pdf_page')}] {e['text']}" for e in a['evidence'])])
wsA,nA=sheet(wb,'atom_비교',H,data,[18,9,13,8,9,30,22,9,9,10,10,10,11,45,45,7,55,60],'AtomCompare')
for r in range(2,nA+1):
    wsA[f'J{r}']=f'=IF(OR(H{r}="",I{r}=""),"",IF(OR(H{r}="hold",I{r}="hold"),"hold",IF((H{r}="pass")=(I{r}="pass"),IF(H{r}="pass","pass","nonpass"),"hold")))'
    wsA[f'K{r}']=f'=IF(OR(E{r}="hold",J{r}="hold",J{r}=""),"제외",IF((E{r}="pass")=(J{r}="pass"),"일치",IF(E{r}="pass","LLM만 불통과","사람만 불통과")))'

# ---------- item ----------
H=['unit_id','도서','형식','사람 판정 출처','채점자','사람 판정','사람 메모','사람이 지적한 조건','GPT 판정','Gemini 판정','LLM 합산','이진 비교','재판정 결과','재판정: 누가 맞았나','최종본 제외(11/18)','GPT 지적 (조건=판정: 이유)','Gemini 지적 (조건=판정: 이유)','문항','선택지','정답','정답 key points','atom 내용']
data=[]
for (st,u),hs in sorted(hum.items()):
    if st!='item' or u not in items: continue
    it=items[u]; ga,gb=unit(st,u,'judge_a'),unit(st,u,'judge_b')
    for src,who,v,note,fl in human_rows(st,u):
        data.append([u,u.split('-')[0],it['format'],src,who,v,note,fl,ga,gb,None,None,adj[u]['adjudicated_v'] if u in adj else '',adj[u]['who_was_right'] if u in adj else '',fix[u]['human_note'] if u in fix else '',flags(st,u,'judge_a'),flags(st,u,'judge_b'),it['question'],'\n'.join(f'{k}) {x}' for k,x in (it.get('options') or {}).items()),it.get('answer') or '','\n'.join(it.get('key_points') or []),it['atom_statement']])
wsI,nI=sheet(wb,'문항_비교',H,data,[24,9,7,14,8,9,30,22,9,9,10,12,10,11,30,45,45,55,30,8,35,50],'ItemCompare')
for r in range(2,nI+1):
    wsI[f'K{r}']=f'=IF(OR(I{r}="",J{r}=""),"",IF(OR(I{r}="hold",J{r}="hold"),"hold",IF((I{r}="pass")=(J{r}="pass"),IF(I{r}="pass","pass","nonpass"),"hold")))'
    wsI[f'L{r}']=f'=IF(OR(F{r}="hold",K{r}="hold",K{r}=""),"제외",IF((F{r}="pass")=(K{r}="pass"),"일치",IF(F{r}="pass","LLM만 불통과","사람만 불통과")))'

# ---------- per check ----------
H=['단계','unit_id','도서','조건','사람 출처','채점자','사람이 이 조건을 지적','GPT','Gemini','LLM 지적','비교','GPT 이유','Gemini 이유']
data=[]
for (st,u),hs in sorted(hum.items()):
    if (st=='card' and u not in atoms) or (st=='item' and u not in items): continue
    for src,who,v,note,fl in human_rows(st,u):
        if v=='hold': continue
        fs={x.strip() for x in fl.split(',') if x.strip()}
        for c in CH[st]:
            x=llm[(st,u)].get(c,{})
            if not x: continue
            ga=x.get('judge_a',('',''));gb=x.get('judge_b',('',''))
            data.append(['atom' if st=='card' else '문항',u,u.split('-')[0],c,src,who,'Y' if c in fs else 'N',ga[0],gb[0],None,None,ga[1] if ga[0]!='pass' else '',gb[1] if gb[0]!='pass' else ''])
wsC,nC=sheet(wb,'조건별_비교',H,data,[7,24,9,22,14,8,10,9,9,9,14,50,50],'CheckCompare')
for r in range(2,nC+1):
    wsC[f'J{r}']=f'=IF(OR(H{r}="fail",H{r}="revise",I{r}="fail",I{r}="revise"),"Y","N")'
    wsC[f'K{r}']=f'=IF(G{r}=J{r},IF(G{r}="Y","둘 다 지적","둘 다 통과"),IF(G{r}="Y","사람만 지적","LLM만 지적"))'
    wsC.row_dimensions[r].height=30

# conditional fills
red=PatternFill('solid',fgColor='FCE4E4'); yel=PatternFill('solid',fgColor='FFF2CC'); grn=PatternFill('solid',fgColor='E2EFDA')
for ws,col,n in ((wsA,'K',nA),(wsI,'L',nI),(wsC,'K',nC)):
    rng=f'{col}2:{col}{n}'
    ws.conditional_formatting.add(rng,FormulaRule(formula=[f'{col}2="LLM만 불통과"'],fill=yel))
    ws.conditional_formatting.add(rng,FormulaRule(formula=[f'{col}2="사람만 불통과"'],fill=red))
    ws.conditional_formatting.add(rng,FormulaRule(formula=[f'{col}2="LLM만 지적"'],fill=yel))
    ws.conditional_formatting.add(rng,FormulaRule(formula=[f'{col}2="사람만 지적"'],fill=red))
    ws.conditional_formatting.add(rng,FormulaRule(formula=[f'{col}2="일치"'],fill=grn))

# ---------- summary ----------
S=wb.create_sheet('요약',0)
S['A1']='사람 채점 vs LLM 저지 판정 비교'; S['A1'].font=Font(name='Arial',size=14,bold=True)
S['A2']='LLM = 현재 저지 프롬프트(v2)의 GPT·Gemini 판정. 아래 숫자는 모두 다른 시트를 세는 수식이라, 시트에서 값을 고치면 자동으로 바뀝니다.'
S['A2'].font=Font(name='Arial',size=10,italic=True)
hdr=['단계','사람 판정 출처','채점자','비교 대상','일치','LLM만 불통과','사람만 불통과','일치율']
r0=4
for i,h in enumerate(hdr,1):
    c=S.cell(r0,i,h); c.font=HF; c.fill=HFILL
combos=[]
for st,ws,src_col,who_col,cmp_col,name in (('atom','atom_비교','C','D','K','AtomCompare'),('문항','문항_비교','D','E','L','ItemCompare')):
    data_ws=wsA if st=='atom' else wsI; n=nA if st=='atom' else nI
    srcs=sorted({data_ws[f'{src_col}{r}'].value for r in range(2,n+1)})
    for s in srcs:
        whos=sorted({data_ws[f'{who_col}{r}'].value for r in range(2,n+1) if data_ws[f'{src_col}{r}'].value==s})
        for w in ['(전체)']+(whos if len(whos)>1 else []):
            combos.append((st,ws,src_col,who_col,cmp_col,n,s,w))
r=r0+1
for st,ws,sc,wc,cc,n,s,w in combos:
    q=f"'{ws}'"
    crit=f'{q}!${sc}$2:${sc}${n},"{s}"'+('' if w=='(전체)' else f',{q}!${wc}$2:${wc}${n},"{w}"')
    S.cell(r,1,st);S.cell(r,2,s);S.cell(r,3,w);S.cell(r,4,f'=E{r}+F{r}+G{r}')
    S.cell(r,5,f'=COUNTIFS({crit},{q}!${cc}$2:${cc}${n},"일치")')
    S.cell(r,6,f'=COUNTIFS({crit},{q}!${cc}$2:${cc}${n},"LLM만 불통과")')
    S.cell(r,7,f'=COUNTIFS({crit},{q}!${cc}$2:${cc}${n},"사람만 불통과")')
    S.cell(r,8,f'=IF(D{r}=0,"-",E{r}/D{r})'); S.cell(r,8).number_format='0%'
    r+=1
r+=1
S.cell(r,1,'조건별 (조건별_비교 시트)').font=Font(name='Arial',size=11,bold=True); r+=1
for i,h in enumerate(['단계','조건','둘 다 지적','LLM만 지적','사람만 지적','LLM 재현율 (사람 지적 중 LLM도 지적)'],1):
    c=S.cell(r,i,h); c.font=HF; c.fill=HFILL
r+=1
q="'조건별_비교'"
for st,stn in (('card','atom'),('item','문항')):
    for c in CH[st]:
        base=f'{q}!$A$2:$A${nC},"{stn}",{q}!$D$2:$D${nC},"{c}"'
        S.cell(r,1,stn);S.cell(r,2,c)
        S.cell(r,3,f'=COUNTIFS({base},{q}!$K$2:$K${nC},"둘 다 지적")')
        S.cell(r,4,f'=COUNTIFS({base},{q}!$K$2:$K${nC},"LLM만 지적")')
        S.cell(r,5,f'=COUNTIFS({base},{q}!$K$2:$K${nC},"사람만 지적")')
        S.cell(r,6,f'=IF(C{r}+E{r}=0,"-",C{r}/(C{r}+E{r}))'); S.cell(r,6).number_format='0%'
        r+=1
r+=1
notes=['읽는 법',
'· atom_비교 / 문항_비교: 단위(atom·문항) 하나에 사람 판정 한 줄. 같은 문항을 보정 라벨과 11/18 검토에서 모두 봤으면 두 줄입니다.',
'· 이진 비교: pass 대 비pass(fail·revise). 사람이나 LLM 합산이 hold면 "제외". 노랑 = LLM만 불통과, 빨강 = 사람만 불통과.',
'· LLM 합산: 저지별 단위 판정(fail > hold > revise > pass 중 가장 나쁜 값)을 합쳐, 어느 쪽이든 hold면 hold, pass/비pass가 같으면 그 값, 다르면 hold (파이프라인의 decision 규칙과 같음).',
'· 사람이 지적한 조건: 보정 라벨 메모에 적힌 조건 이름, 또는 11/18 보류 검토에서 fail을 준 조건. 표본 검토는 문항 단위라 비어 있습니다.',
'· 재판정 결과·누가 맞았나: 사람·LLM이 갈린 42건을 다시 판정한 결과 (정답 기준).',
'· 최종본 제외(11/18): 사람 검토 뒤 정답 문제로 최종 76문항에서 뺀 6건과 그 이유.',
'· 조건별_비교: 단위 × 조건 한 줄. 필터로 조건·채점자·"LLM만 지적" 등을 골라 보면 됩니다.',
'· 범위: 보정 세트(atom 120, 문항 120), 재판정 42건, 11/18 검토 88문항. LLM 판정이 없는 단위(현재 프롬프트로 안 돌린 것)는 LLM 칸이 비어 있습니다.']
for t in notes:
    S.cell(r,1,t).font=Font(name='Arial',size=10,bold=(t=='읽는 법')); r+=1
for col,w in zip('ABCDEFGH',[8,18,10,10,12,22,14,10]): S.column_dimensions[col].width=w
for row in S.iter_rows(min_row=r0,max_row=r):
    for c in row:
        if c.font.name!='Arial' or (not c.font.bold and c.font.color is None): c.font=Font(name='Arial',size=10,bold=c.font.bold,color=c.font.color)
out=str(ROOT/'analysis/results/MOTIF_사람채점_vs_LLM판정.xlsx')
wb.save(out); print(out, nA-1, nI-1, nC-1, len(combos))
