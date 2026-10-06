import json
from pathlib import Path
P=Path('pendentes-conferencia.json'); N=Path('noticias.json'); S=Path('resumo-aprovacao.md')
def load(p):
    try:
        d=json.loads(p.read_text(encoding='utf-8'));return d if isinstance(d,list) else []
    except:return []
def main():
    pend=load(P)[:1]
    if not pend:
        S.write_text('# Nenhuma matéria aguardando aprovação\n',encoding='utf-8');print('Nenhum item preparado');return
    x=pend[0]; old=load(N); link=str(x.get('link','')).rstrip('/').casefold()
    old=[i for i in old if str(i.get('link','')).rstrip('/').casefold()!=link]
    N.write_text(json.dumps([x]+old,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    checks='\n'.join(f'- {c}' for c in x.get('criterios_selecao',[]))
    S.write_text(f'''# Matéria aguardando aprovação

## Publicação
- **Título:** {x.get('titulo','')}
- **Categoria:** {x.get('categoria_sugerida','')}
- **Data da fonte:** {x.get('data','')}
- **Fonte:** {x.get('fonte','')}
- **Mercado:** {x.get('mercado','')}
- **Pontuação editorial:** {x.get('pontuacao_editorial','')}/100
- **Decisão automática:** {x.get('decisao_editorial','')}
- **Imagem:** {x.get('imagem','')}
- **Origem da imagem:** {x.get('imagem_origem','')}
- **Link original:** {x.get('link','')}

## Resumo
{x.get('resumo','')}

## Critérios
{checks}

## Aprovação
Revise **Files changed**. Para publicar, faça o merge deste Pull Request. Para rejeitar, feche o Pull Request sem merge.
''',encoding='utf-8')
    print('Preparado:',x.get('titulo'))
if __name__=='__main__':main()
