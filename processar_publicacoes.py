import base64,hashlib,json,os,re,unicodedata
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
import requests
R=Path('rascunhos-coletor.json');N=Path('noticias.json');P=Path('pendentes-conferencia.json');O=Path('resultado-processamento.txt');D=Path('imagens/noticias')
C={'Últimas notícias','Eventos e feiras','Histórias e comunidade','Guias e vida a bordo','Novidades internacionais'}
F={'Últimas notícias':'imagens/capa-estrada.png','Eventos e feiras':'imagens/padrao-eventos.png','Histórias e comunidade':'imagens/padrao-comunidade.png','Guias e vida a bordo':'imagens/guia-organizar.png','Novidades internacionais':'imagens/ilustrativa-veiculos.png'}
def load(p):
 try:return json.loads(p.read_text(encoding='utf-8'))
 except:return []
def text(v):return v.strip() if isinstance(v,str) else ''
def key(v):return text(v).rstrip('/').casefold()
def category(x):
 c=text(x.get('categoria_sugerida'))
 if c in C:return c
 b=(text(x.get('titulo'))+' '+text(x.get('resumo'))).casefold()
 if any(k in b for k in ('expo','feira','encontro','festival')):return 'Eventos e feiras'
 if any(k in b for k in ('guia','como ','dicas','manutenção')):return 'Guias e vida a bordo'
 return 'Últimas notícias'
def normalize(x):
 y=dict(x);u=urlparse(text(y.get('link')))
 if len(text(y.get('titulo')))<8 or u.scheme!='https' or not u.netloc:raise ValueError()
 y['categoria_sugerida']=category(y);y['fonte']=text(y.get('fonte')) or u.netloc;y['resumo']=text(y.get('resumo')) or text(y.get('titulo'));y['data']=text(y.get('data')) or datetime.now().strftime('%d/%m/%Y');return y
def score(x,pub):
 b=(text(x.get('titulo'))+' '+text(x.get('resumo'))).casefold();rel=min(40,sum(k in b for k in ('motorhome','caravanismo','trailer','camper','campervan','vanhome','camping'))*10);fresh=0
 try:
  age=(datetime.now().date()-datetime.strptime(x['data'],'%d/%m/%Y').date()).days;fresh=25 if age<=1 else 22 if age<=3 else 18 if age<=7 else 13 if age<=14 else 8 if age<=30 else 4 if age<=45 else 0
 except:pass
 comp=(4 if len(text(x.get('titulo')))>=20 else 0)+(6 if len(text(x.get('resumo')))>=60 else 0)+(3 if text(x.get('fonte')) else 0)+2;val=8 if any(k in b for k in ('lança','lançamento','novo modelo','launches','introduces')) else 7 if any(k in b for k in ('expo','feira','encontro')) else 6 if any(k in b for k in ('guia','como ','dicas')) else 0;div=5 if pub and category(x)!=text(pub[0].get('categoria_sugerida')) else 0
 return rel+fresh+comp+val+div,[f'relevância {rel}/40',f'atualidade {fresh}/25',f'completude {comp}/15',f'valor editorial {val}/15',f'diversidade {div}/5']
def slug(s):return re.sub(r'[^a-z0-9]+','-',unicodedata.normalize('NFKD',s).encode('ascii','ignore').decode().lower()).strip('-')[:55]+'-'+hashlib.sha1(s.encode()).hexdigest()[:8]
def image(x,path):
 aid=os.getenv('CLOUDFLARE_ACCOUNT_ID','');tok=os.getenv('CLOUDFLARE_API_TOKEN','')
 if not aid or not tok:return False,'secrets ausentes'
 prompt=f"Photorealistic editorial landscape image for a Brazilian motorhome news website. Topic: {x['titulo']}. Context: {x['resumo'][:350]}. Relevant motorhomes, trailers or camper vans. Natural light, magazine quality, no text, no logos, no watermark, no recognizable people, no empty space."
 try:
  r=requests.post(f'https://api.cloudflare.com/client/v4/accounts/{aid}/ai/run/@cf/black-forest-labs/flux-1-schnell',headers={'Authorization':f'Bearer {tok}'},json={'prompt':prompt[:2048],'steps':4},timeout=180);r.raise_for_status();z=r.json();raw=base64.b64decode(z.get('result',{}).get('image') or z.get('image'));path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw);return True,'Cloudflare AI'
 except Exception as e:return False,type(e).__name__
def main():
 pub=load(N);seen={key(x.get('link')) for x in pub if isinstance(x,dict)};rank=[]
 for i,z in enumerate(load(R)):
  try:
   x=normalize(z)
   if key(x.get('link')) in seen:continue
   s,m=score(x,pub);x['pontuacao_editorial']=s;x['criterios_selecao']=m;rank.append((s,-i,x))
  except:pass
 rank.sort(key=lambda q:(q[0],q[1]),reverse=True);log=['RANKING DOS CANDIDATOS:']+[f'{i}. {q[2]["titulo"]} | {q[0]}/100' for i,q in enumerate(rank,1)];out=[]
 if rank:
  x=rank[0][2];dst=D/(slug(x['titulo'])+'.jpg');ok,why=image(x,dst);x['imagem']=dst.as_posix() if ok else F[category(x)];x['imagem_origem']='gerada_por_ia' if ok else 'padrao_categoria';x['imagem_legenda']='Imagem gerada por inteligência artificial' if ok else 'Imagem ilustrativa';out=[x];log.append('SELECIONADO: '+x['titulo']+' | '+why)
 P.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');log+=['Aprovados: '+str(len(out)),'Limite por execução: 1'];O.write_text('\n'.join(log)+'\n',encoding='utf-8');print('\n'.join(log))
if __name__=='__main__':main()
