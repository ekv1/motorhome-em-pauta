import json
from pathlib import Path
N=Path('noticias.json');P=Path('pendentes-conferencia.json')
def load(p):
 try:return json.loads(p.read_text(encoding='utf-8'))
 except:return []
def main():
 old=load(N);seen={str(x.get('link','')).rstrip('/').casefold() for x in old if isinstance(x,dict)};new=[x for x in load(P) if str(x.get('link','')).rstrip('/').casefold() not in seen][:1]
 if new:N.write_text(json.dumps(new+old,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 Path('resultado-publicacao.txt').write_text(f'Publicados: {len(new)}\n',encoding='utf-8');print(f'Publicados: {len(new)}')
if __name__=='__main__':main()
