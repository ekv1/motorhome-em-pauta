#!/usr/bin/env python3
"""Seleciona 5 pautas editoriais, com prioridade para Brasil, eventos e encontros."""
from __future__ import annotations
import json, re, sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

ENTRADAS = [
    Path("pautas-descobertas.json"),
    Path("rascunhos-coletor.json"),
    Path("rascunhos-internacionais.json"),
    Path("pendentes-conferencia.json"),
]
SAIDA = Path("pautas-selecionadas.json")
RESUMO = Path("resumo-aprovacao.md")
MAX_OPCOES = 5
MIN_BRASIL = 3
MIN_EVENTOS = 2

DOMINIOS_BRASIL = {
    "anacamp.com", "macamp.com.br", "caravanismobrasil.com.br",
    "caravanista.com.br", "boraprocamping.com.br", "expomotorhome.com",
    "gov.br", "turismo.gov.br", "agenciabrasil.ebc.com.br",
}
TERMOS_BRASIL = {
    "brasil", "brasileiro", "brasileira", "nacional", "anacamp", "macamp",
    "expo motorhome", "expomotorhome", "pinhais", "paraná", "são paulo",
    "minas gerais", "rio grande do sul", "santa catarina", "mato grosso",
}
TERMOS_EVENTO = {
    "evento", "eventos", "encontro", "encontros", "feira", "festival",
    "agenda", "programação", "caravana", "fórum", "exposição", "expo",
    "confraternização", "campistas raiz", "vai quem quer", "vqq",
}


def txt(v): return v.strip() if isinstance(v, str) else ""
def norm(v):
    import unicodedata
    return unicodedata.normalize("NFKD", v).encode("ascii", "ignore").decode().lower()

def primeiro(d, *chaves):
    for c in chaves:
        v=d.get(c)
        if isinstance(v, str) and v.strip(): return v.strip()
    return ""

def carregar():
    itens=[]
    for arq in ENTRADAS:
        if not arq.exists(): continue
        try: dados=json.loads(arq.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"Aviso: {arq}: {e}", file=sys.stderr); continue
        if isinstance(dados, dict):
            dados=dados.get("pautas") or dados.get("itens") or dados.get("resultados") or [dados]
        if isinstance(dados, list):
            for x in dados:
                if isinstance(x, dict):
                    x=dict(x); x["_arquivo_origem"]=arq.name; itens.append(x)
    return itens

def adaptar(x):
    titulo=primeiro(x,"titulo","title","headline","assunto")
    link=primeiro(x,"link","url","fonte_url","link_original")
    resumo=primeiro(x,"resumo","summary","descricao","description","texto")
    fonte=primeiro(x,"fonte","source","site") or urlparse(link).netloc
    data=primeiro(x,"data","date","published","data_fonte","data_publicacao")
    categoria=primeiro(x,"categoria_sugerida","categoria","category")
    conjunto=norm(" ".join([titulo,resumo,fonte,link,categoria]))
    dominio=urlparse(link).netloc.lower().removeprefix("www.")
    brasil=bool(x.get("mercado") == "Brasil" or x.get("pais") == "Brasil" or
                any(dominio==d or dominio.endswith("."+d) for d in DOMINIOS_BRASIL) or
                any(t in conjunto for t in map(norm,TERMOS_BRASIL)))
    evento=bool(any(t in conjunto for t in map(norm,TERMOS_EVENTO)))
    pontuacao=x.get("pontuacao_editorial",x.get("pontuacao",x.get("score",0)))
    try: pontuacao=float(pontuacao)
    except: pontuacao=0
    # Eventos futuros e pautas nacionais recebem prioridade explícita.
    nota=pontuacao + (18 if brasil else 0) + (25 if evento else 0)
    return {
        "titulo":titulo,"resumo":resumo[:700],"fonte":fonte,"link":link,
        "data":data,"categoria_sugerida":categoria or ("Eventos e feiras" if evento else "Últimas notícias"),
        "origem":"Brasil" if brasil else "Internacional","tipo":"Evento/encontro" if evento else "Notícia",
        "pontuacao_original":pontuacao,"pontuacao_selecao":round(nota,2),
        "arquivo_origem":x.get("_arquivo_origem","")
    }

def deduplicar(itens):
    vistos=set(); saida=[]
    for i in itens:
        chave=(i["link"].rstrip("/").lower() or norm(i["titulo"]))
        if not i["titulo"] or not i["link"] or chave in vistos: continue
        vistos.add(chave); saida.append(i)
    return saida

def escolher(itens):
    itens=sorted(itens,key=lambda i:i["pontuacao_selecao"],reverse=True)
    escolhidos=[]
    def add(pool,qtd):
        for i in pool:
            if len([x for x in escolhidos if x in pool])>=qtd: break
            if i not in escolhidos: escolhidos.append(i)
    eventos_br=[i for i in itens if i["origem"]=="Brasil" and i["tipo"]=="Evento/encontro"]
    nacionais=[i for i in itens if i["origem"]=="Brasil"]
    eventos=[i for i in itens if i["tipo"]=="Evento/encontro"]
    add(eventos_br,min(MIN_EVENTOS,len(eventos_br)))
    for i in nacionais:
        if sum(x["origem"]=="Brasil" for x in escolhidos)>=MIN_BRASIL: break
        if i not in escolhidos: escolhidos.append(i)
    for i in eventos:
        if sum(x["tipo"]=="Evento/encontro" for x in escolhidos)>=MIN_EVENTOS: break
        if i not in escolhidos: escolhidos.append(i)
    for i in itens:
        if len(escolhidos)>=MAX_OPCOES: break
        if i not in escolhidos: escolhidos.append(i)
    escolhidos=escolhidos[:MAX_OPCOES]
    for n,i in enumerate(escolhidos,1): i["opcao"]=n
    return escolhidos

def markdown(opcoes):
    n_br=sum(x["origem"]=="Brasil" for x in opcoes)
    n_ev=sum(x["tipo"]=="Evento/encontro" for x in opcoes)
    linhas=["# Cinco opções de pauta para aprovação","",f"- Opções do Brasil: **{n_br}**",f"- Eventos ou encontros: **{n_ev}**","", "Use o comentário `/escolher N` para indicar a pauta desejada.",""]
    if n_br<MIN_BRASIL: linhas += [f"> Atenção: foram encontradas somente {n_br} pautas nacionais válidas nesta execução.",""]
    for i in opcoes:
        linhas += [f"## Opção {i['opcao']} · {i['origem']} · {i['tipo']}","",f"**Título:** {i['titulo']}",f"**Fonte:** {i['fonte']}",f"**Categoria:** {i['categoria_sugerida']}",f"**Pontuação de seleção:** {i['pontuacao_selecao']}",f"**Link:** {i['link']}","",i['resumo'] or "Sem resumo disponível.",""]
    linhas += ["## Regras aplicadas","","- Até 5 opções.","- Pelo menos 3 brasileiras quando houver fontes válidas.","- Pelo menos 2 eventos/encontros quando houver fontes válidas.","- Eventos/encontros recebem bônus editorial de 25 pontos.","- Origem brasileira recebe bônus editorial de 18 pontos.",""]
    return "\n".join(linhas)

def main():
    candidatos=deduplicar([adaptar(x) for x in carregar()])
    if not candidatos: raise SystemExit("Nenhuma pauta válida encontrada nos arquivos de coleta.")
    opcoes=escolher(candidatos)
    SAIDA.write_text(json.dumps(opcoes,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    RESUMO.write_text(markdown(opcoes),encoding="utf-8")
    print(f"Selecionadas {len(opcoes)} pautas: {sum(x['origem']=='Brasil' for x in opcoes)} do Brasil e {sum(x['tipo']=='Evento/encontro' for x in opcoes)} eventos/encontros.")
if __name__=="__main__": main()
