import json, re, urllib.parse, urllib.request, xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

CONFIG=Path('consultas_tendencias.json')
OUT=Path('pautas-descobertas.json')
REPORT=Path('resultado-tendencias.txt')
UA={'User-Agent':'MotorhomeEmPauta/1.0 editorial-radar'}
DIRECT=('motorhome','trailer','camper','caravanismo','camping','rv ','recreational vehicle')
BRAZIL=('brasil','brasileiro','brasileira','anacamp','motorhome brasil')
USEFUL=('lançamento','lancamento','preço','preco','segurança','seguranca','manutenção','manutencao','bateria','solar','legislação','legislacao','camping','ponto de apoio','recall')
CORP=('executivo','presidente','finalista','prêmio anual','premio anual','dealer','revendedor')

def fetch(url):
    req=urllib.request.Request(url,headers=UA)
    with urllib.request.urlopen(req,timeout=30) as r:return r.read()

def clean(s):return ' '.join(re.sub(r'<[^>]+>',' ',s or '').split())
def date(s):
    try:return parsedate_to_datetime(s).astimezone(timezone.utc).isoformat()
    except:return ''
def google_news(q):
    url='https://news.google.com/rss/search?'+urllib.parse.urlencode({'q':q,'hl':'pt-BR','gl':'BR','ceid':'BR:pt-419'})
    root=ET.fromstring(fetch(url)); out=[]
    for n in root.findall('./channel/item'):
        out.append({'titulo':clean(n.findtext('title')),'link':clean(n.findtext('link')),'data_fonte':date(n.findtext('pubDate') or ''),'fonte_descoberta':'Google News','consulta':q})
    return out

def trends_br():
    try:
        root=ET.fromstring(fetch('https://trends.google.com.br/trending/rss?geo=BR')); out=[]
        for n in root.findall('./channel/item'):
            title=clean(n.findtext('title')); low=title.casefold()
            if any(k in low for k in DIRECT+USEFUL):out.append({'titulo':title,'link':'https://trends.google.com/trending?geo=BR','data_fonte':'','fonte_descoberta':'Google Trends Brasil','consulta':'tendências Brasil'})
        return out
    except Exception:return []

def score(x):
    t=x['titulo'].casefold(); s=0; why=[]
    if any(k in t for k in DIRECT):s+=35;why.append('tema direto +35')
    if any(k in t for k in BRAZIL):s+=25;why.append('Brasil +25')
    if any(k in t for k in USEFUL):s+=20;why.append('utilidade +20')
    if x['data_fonte']:s+=10;why.append('data disponível +10')
    if any(k in t for k in CORP):s-=30;why.append('corporativo -30')
    return max(0,min(100,s)),why

def main():
    queries=json.loads(CONFIG.read_text(encoding='utf-8')); items=[]; log=[]
    for q in queries:
        try:
            found=google_news(q)[:10];items+=found;log.append(f'{q}: {len(found)} resultados')
        except Exception as e:log.append(f'{q}: falha {type(e).__name__}')
    items+=trends_br(); dedup={}
    for x in items:
        key=re.sub(r'\W+',' ',x['titulo'].casefold()).strip()
        if key and key not in dedup:dedup[key]=x
    ranked=[]
    for x in dedup.values():
        x['pontuacao_tendencia'],x['sinais']=score(x)
        if x['pontuacao_tendencia']>=35:ranked.append(x)
    ranked.sort(key=lambda x:x['pontuacao_tendencia'],reverse=True)
    OUT.write_text(json.dumps(ranked[:25],ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    log.append(f'Pautas elegíveis: {len(ranked[:25])}')
    REPORT.write_text('\n'.join(log)+'\n',encoding='utf-8');print('\n'.join(log))
if __name__=='__main__':main()
