#!/usr/bin/env python3
"""Seleciona cinco pautas editoriais válidas, distintas e prontas para escolha."""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from difflib import SequenceMatcher
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
MIN_RESUMO = 120
SIMILARIDADE_DUPLICADA = 0.72

DOMINIOS_BRASIL = {
    "anacamp.com", "macamp.com.br", "caravanismobrasil.com.br",
    "caravanista.com.br", "boraprocamping.com.br", "expomotorhome.com",
    "gov.br", "turismo.gov.br", "agenciabrasil.ebc.com.br",
}
TERMOS_BRASIL = {
    "brasil", "brasileiro", "brasileira", "nacional", "anacamp", "macamp",
    "expo motorhome", "expomotorhome", "pinhais", "parana", "sao paulo",
    "minas gerais", "rio grande do sul", "santa catarina", "mato grosso",
    "apucarana", "curitiba",
}
TERMOS_EVENTO = {
    "evento", "eventos", "encontro", "encontros", "feira", "festival",
    "agenda", "programacao", "caravana", "forum", "exposicao", "expo",
    "confraternizacao", "campistas raiz", "vai quem quer", "vqq",
}
TERMOS_DESTINO = {
    "camping", "campings", "acampar", "campismo", "ponto de apoio",
    "area de apoio", "pernoite", "destino", "rota", "roteiro",
}
TERMOS_PRODUTO = {
    "motorhome", "trailer", "minitrailer", "mini trailer", "camper", "van",
    "bateria", "equipamento", "acessorio", "lancamento", "modelo",
}
PALAVRAS_VAZIAS = {
    "a", "as", "ao", "aos", "com", "da", "das", "de", "do", "dos", "e",
    "em", "na", "nas", "no", "nos", "o", "os", "para", "por", "um", "uma",
    "brasil", "brasileiro", "brasileira",
}


def txt(valor: object) -> str:
    return valor.strip() if isinstance(valor, str) else ""


def norm(valor: str) -> str:
    valor = unicodedata.normalize("NFKD", valor.casefold())
    valor = "".join(c for c in valor if not unicodedata.combining(c))
    tokens = re.findall(r"[a-z0-9]+", valor)
    return " ".join(t for t in tokens if t not in PALAVRAS_VAZIAS)


def primeiro(dados: dict, *chaves: str) -> str:
    for chave in chaves:
        valor = dados.get(chave)
        if isinstance(valor, str) and valor.strip():
            return valor.strip()
    return ""


def dominio(url: str) -> str:
    try:
        return urlparse(url).netloc.casefold().removeprefix("www.")
    except ValueError:
        return ""


def carregar() -> list[dict]:
    itens: list[dict] = []
    for arquivo in ENTRADAS:
        if not arquivo.exists():
            continue
        try:
            dados = json.loads(arquivo.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as erro:
            print(f"Aviso: {arquivo}: {erro}", file=sys.stderr)
            continue
        if isinstance(dados, dict):
            dados = (
                dados.get("pautas")
                or dados.get("itens")
                or dados.get("resultados")
                or [dados]
            )
        if isinstance(dados, list):
            for item in dados:
                if isinstance(item, dict):
                    copia = dict(item)
                    copia["_arquivo_origem"] = arquivo.name
                    itens.append(copia)
    return itens


def resolver_google_news(url: str) -> str:
    if dominio(url) != "news.google.com":
        return url
    try:
        from googlenewsdecoder import gnewsdecoder

        resultado = gnewsdecoder(url, interval=None, timeout=15.0)
        if isinstance(resultado, dict) and resultado.get("success"):
            resolvida = txt(resultado.get("decoded_url"))
            if resolvida.startswith("https://") and dominio(resolvida) != "news.google.com":
                return resolvida
    except Exception as erro:
        print(f"Aviso: não foi possível resolver Google News: {erro}", file=sys.stderr)
    return ""


def classificar(titulo: str, resumo: str, categoria_atual: str) -> tuple[str, str]:
    conjunto = norm(" ".join((titulo, resumo, categoria_atual)))
    evento = any(norm(t) in conjunto for t in TERMOS_EVENTO)
    destino = any(norm(t) in conjunto for t in TERMOS_DESTINO)
    produto = any(norm(t) in conjunto for t in TERMOS_PRODUTO)

    if evento:
        return "Eventos e feiras", "Evento/encontro"
    if destino:
        return "Destinos e estrutura", "Destino/camping"
    if produto:
        if any(t in conjunto for t in ("lancamento", "novo modelo", "apresenta")):
            return "Lançamentos nacionais", "Lançamento"
        return "Equipamentos e tecnologia", "Equipamento"
    if categoria_atual in {
        "Guias e vida a bordo", "Histórias e comunidade",
        "Novidades internacionais", "Tendências internacionais",
    }:
        tipo = {
            "Guias e vida a bordo": "Guia",
            "Histórias e comunidade": "História/comunidade",
            "Novidades internacionais": "Notícia",
            "Tendências internacionais": "Notícia",
        }[categoria_atual]
        return categoria_atual, tipo
    return "Últimas notícias", "Notícia"


def adaptar(item: dict) -> dict | None:
    titulo = primeiro(item, "titulo", "title", "headline", "assunto")
    resumo = primeiro(item, "resumo", "summary", "descricao", "description", "texto")
    link_bruto = primeiro(item, "link_original", "fonte_url", "link", "url")
    link = resolver_google_news(link_bruto)

    if not titulo or not link or len(resumo) < MIN_RESUMO:
        return None

    fonte = primeiro(item, "fonte", "source", "site")
    if not fonte or fonte.casefold() == "news.google.com":
        fonte = dominio(link)
    data = primeiro(item, "data", "date", "published", "data_fonte", "data_publicacao")
    categoria_atual = primeiro(item, "categoria_sugerida", "categoria", "category")
    categoria, tipo = classificar(titulo, resumo, categoria_atual)

    conjunto = norm(" ".join((titulo, resumo, fonte, link, categoria)))
    host = dominio(link)
    brasil = bool(
        item.get("mercado") == "Brasil"
        or item.get("pais") == "Brasil"
        or any(host == d or host.endswith("." + d) for d in DOMINIOS_BRASIL)
        or any(norm(t) in conjunto for t in TERMOS_BRASIL)
        or host.endswith(".br")
    )

    pontuacao = item.get(
        "pontuacao_editorial",
        item.get("pontuacao", item.get("score", 0)),
    )
    try:
        pontuacao = float(pontuacao)
    except (TypeError, ValueError):
        pontuacao = 0.0

    evento = tipo == "Evento/encontro"
    nota = pontuacao + (18 if brasil else 0) + (25 if evento else 0)

    return {
        "titulo": titulo,
        "resumo": resumo[:700],
        "fonte": fonte,
        "link": link,
        "data": data,
        "categoria_sugerida": categoria,
        "origem": "Brasil" if brasil else "Internacional",
        "tipo": tipo,
        "pontuacao_original": pontuacao,
        "pontuacao_selecao": round(nota, 2),
        "arquivo_origem": item.get("_arquivo_origem", ""),
        "fontes_complementares": [],
    }


def similaridade(a: dict, b: dict) -> float:
    ta, tb = norm(a["titulo"]), norm(b["titulo"])
    sequencia = SequenceMatcher(None, ta, tb).ratio()
    sa, sb = set(ta.split()), set(tb.split())
    uniao = sa | sb
    jaccard = len(sa & sb) / len(uniao) if uniao else 0.0
    return max(sequencia, jaccard)


def consolidar(itens: list[dict]) -> list[dict]:
    ordenados = sorted(itens, key=lambda i: i["pontuacao_selecao"], reverse=True)
    consolidados: list[dict] = []
    for item in ordenados:
        duplicado = next(
            (
                existente
                for existente in consolidados
                if existente["link"].rstrip("/").casefold()
                == item["link"].rstrip("/").casefold()
                or similaridade(existente, item) >= SIMILARIDADE_DUPLICADA
            ),
            None,
        )
        if duplicado:
            fonte_extra = {"titulo": item["fonte"], "url": item["link"]}
            if fonte_extra["url"] != duplicado["link"]:
                duplicado["fontes_complementares"].append(fonte_extra)
            continue
        consolidados.append(item)
    return consolidados


def escolher(itens: list[dict]) -> list[dict]:
    brasileiros = [i for i in itens if i["origem"] == "Brasil"]
    internacionais = [i for i in itens if i["origem"] == "Internacional"]
    escolhidos: list[dict] = []

    def adicionar(pool: list[dict], limite: int | None = None) -> None:
        for item in pool:
            if len(escolhidos) >= MAX_OPCOES:
                return
            if limite is not None and sum(x in pool for x in escolhidos) >= limite:
                return
            if item not in escolhidos:
                escolhidos.append(item)

    eventos_br = [i for i in brasileiros if i["tipo"] == "Evento/encontro"]
    destinos_br = [i for i in brasileiros if i["tipo"] == "Destino/camping"]
    produtos_br = [
        i for i in brasileiros if i["tipo"] in {"Lançamento", "Equipamento"}
    ]

    adicionar(eventos_br, 1)
    adicionar(produtos_br, 1)
    adicionar(destinos_br, 1)
    adicionar(brasileiros)
    adicionar(internacionais)
    adicionar(itens)

    if len(escolhidos) < MAX_OPCOES:
        return []

    escolhidos = escolhidos[:MAX_OPCOES]
    for numero, item in enumerate(escolhidos, 1):
        item["opcao"] = numero
    return escolhidos


def markdown(opcoes: list[dict]) -> str:
    n_br = sum(x["origem"] == "Brasil" for x in opcoes)
    n_ev = sum(x["tipo"] == "Evento/encontro" for x in opcoes)
    linhas = [
        "# Cinco opções de pauta para aprovação",
        "",
        f"- Opções do Brasil: **{n_br}**",
        f"- Eventos ou encontros: **{n_ev}**",
        "",
        "Use um único comentário `/escolher N` para indicar a pauta desejada.",
        "",
    ]
    if n_br < MIN_BRASIL:
        linhas.extend([
            f"> Atenção: somente {n_br} pautas brasileiras válidas foram encontradas.",
            "",
        ])
    for item in opcoes:
        linhas.extend([
            f"## Opção {item['opcao']} · {item['origem']} · {item['tipo']}",
            "",
            f"**Título:** {item['titulo']}",
            f"**Fonte:** {item['fonte']}",
            f"**Categoria:** {item['categoria_sugerida']}",
            f"**Pontuação de seleção:** {item['pontuacao_selecao']}",
            f"**Link:** {item['link']}",
            "",
            item["resumo"],
            "",
        ])
    linhas.extend([
        "## Regras aplicadas",
        "",
        "- Cinco opções com link original HTTPS.",
        "- Resumo factual com pelo menos 120 caracteres.",
        "- Assuntos semelhantes consolidados em uma pauta.",
        "- Categoria e tipo recalculados pelo conteúdo.",
        "- Prioridade para Brasil, eventos, produtos e infraestrutura.",
        "",
    ])
    return "\n".join(linhas)


def main() -> None:
    SAIDA.unlink(missing_ok=True)
    RESUMO.unlink(missing_ok=True)

    adaptados = []
    for bruto in carregar():
        item = adaptar(bruto)
        if item:
            adaptados.append(item)

    candidatos = consolidar(adaptados)
    opcoes = escolher(candidatos)
    if len(opcoes) != MAX_OPCOES:
        raise SystemExit(
            f"Somente {len(candidatos)} pautas válidas e distintas foram encontradas; "
            f"são necessárias {MAX_OPCOES}. Nenhum PR ou e-mail será criado."
        )

    SAIDA.write_text(
        json.dumps(opcoes, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    RESUMO.write_text(markdown(opcoes), encoding="utf-8")
    print(
        f"Selecionadas {len(opcoes)} pautas: "
        f"{sum(x['origem'] == 'Brasil' for x in opcoes)} do Brasil e "
        f"{sum(x['tipo'] == 'Evento/encontro' for x in opcoes)} eventos/encontros."
    )


if __name__ == "__main__":
    main()
