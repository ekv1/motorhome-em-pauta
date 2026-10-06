#!/usr/bin/env python3
"""Qualifica, consolida e seleciona cinco pautas editoriais."""
from __future__ import annotations

import html
import json
import re
import sys
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

ENTRADAS = [
    Path("pautas-descobertas.json"),
    Path("rascunhos-coletor.json"),
    Path("rascunhos-internacionais.json"),
    Path("pendentes-conferencia.json"),
]
SAIDA = Path("pautas-selecionadas.json")
RESUMO = Path("resumo-aprovacao.md")
RELATORIO = Path("resultado-qualificacao-pautas.txt")
MAX_OPCOES = 5
MIN_RESUMO = 120
SIMILARIDADE_DUPLICADA = 0.68
TIMEOUT = 20

DOMINIOS_BRASIL = {
    "anacamp.com", "macamp.com.br", "caravanismobrasil.com.br",
    "caravanista.com.br", "boraprocamping.com.br", "expomotorhome.com",
    "gov.br", "turismo.gov.br", "agenciabrasil.ebc.com.br",
}
TERMOS_BRASIL = {
    "brasil", "brasileiro", "brasileira", "nacional", "anacamp", "macamp",
    "expo motorhome", "pinhais", "parana", "sao paulo", "minas gerais",
    "rio grande do sul", "santa catarina", "mato grosso", "apucarana",
    "curitiba", "porto murtinho",
}
TERMOS_EVENTO = {
    "evento", "encontro", "feira", "festival", "agenda", "programacao",
    "caravana", "forum", "exposicao", "expo", "confraternizacao",
}
TERMOS_DESTINO = {
    "camping", "acampar", "campismo", "ponto de apoio", "area de apoio",
    "pernoite", "destino", "rota", "roteiro",
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
LOG: list[str] = []
SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "Chrome/124 Safari/537.36 MotorhomeEmPauta/1.0"
    )
})


def registrar(msg: str) -> None:
    LOG.append(msg)
    print(msg)


def texto(v: object) -> str:
    return v.strip() if isinstance(v, str) else ""


def normalizar(v: str) -> str:
    v = unicodedata.normalize("NFKD", html.unescape(v).casefold())
    v = "".join(c for c in v if not unicodedata.combining(c))
    tokens = re.findall(r"[a-z0-9]+", v)
    return " ".join(t for t in tokens if t not in PALAVRAS_VAZIAS)


def primeiro(d: dict, *chaves: str) -> str:
    for chave in chaves:
        v = d.get(chave)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def host(url: str) -> str:
    try:
        return urlparse(url).netloc.casefold().removeprefix("www.")
    except ValueError:
        return ""


def limpar_texto(v: str) -> str:
    v = BeautifulSoup(html.unescape(v or ""), "html.parser").get_text(" ", strip=True)
    return re.sub(r"\s+", " ", v).strip()


def carregar() -> list[dict]:
    itens: list[dict] = []
    for arquivo in ENTRADAS:
        if not arquivo.is_file():
            registrar(f"IGNORADO: arquivo inexistente: {arquivo}")
            continue
        try:
            dados = json.loads(arquivo.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as erro:
            registrar(f"IGNORADO: {arquivo}: {erro}")
            continue
        if isinstance(dados, dict):
            dados = dados.get("pautas") or dados.get("itens") or dados.get("resultados") or [dados]
        if isinstance(dados, list):
            for item in dados:
                if isinstance(item, dict):
                    item = dict(item)
                    item["_arquivo_origem"] = arquivo.name
                    itens.append(item)
    registrar(f"Candidatos brutos carregados: {len(itens)}")
    return itens


def resolver_google_news(url: str) -> str:
    if host(url) != "news.google.com":
        return url
    try:
        from googlenewsdecoder import gnewsdecoder
        resultado = gnewsdecoder(url, interval=None, timeout=TIMEOUT)
        if isinstance(resultado, dict) and resultado.get("success"):
            resolvida = texto(resultado.get("decoded_url"))
            if resolvida.startswith("https://") and host(resolvida) != "news.google.com":
                return resolvida
    except Exception as erro:
        registrar(f"LINK NÃO RESOLVIDO: {type(erro).__name__}: {url[:90]}")
    return ""


def metadados_da_pagina(url: str) -> dict[str, str]:
    try:
        resposta = SESSION.get(url, timeout=TIMEOUT, allow_redirects=True)
        resposta.raise_for_status()
        if "text/html" not in resposta.headers.get("content-type", "").casefold():
            return {"url": resposta.url}
        sopa = BeautifulSoup(resposta.text, "html.parser")

        def meta(*seletores: tuple[str, str]) -> str:
            for atributo, valor in seletores:
                tag = sopa.find("meta", attrs={atributo: valor})
                if tag and texto(tag.get("content")):
                    return limpar_texto(tag.get("content"))
            return ""

        titulo = meta(("property", "og:title"), ("name", "twitter:title"))
        if not titulo and sopa.title:
            titulo = limpar_texto(sopa.title.get_text(" ", strip=True))
        resumo = meta(
            ("property", "og:description"),
            ("name", "description"),
            ("name", "twitter:description"),
        )
        site = meta(("property", "og:site_name")) or host(resposta.url)
        return {"url": resposta.url, "titulo": titulo, "resumo": resumo, "fonte": site}
    except requests.RequestException as erro:
        registrar(f"FONTE INACESSÍVEL: {type(erro).__name__}: {url[:100]}")
        return {}


def classificar(titulo: str, resumo: str, categoria_atual: str) -> tuple[str, str]:
    conjunto = normalizar(" ".join((titulo, resumo, categoria_atual)))
    evento = any(normalizar(t) in conjunto for t in TERMOS_EVENTO)
    destino = any(normalizar(t) in conjunto for t in TERMOS_DESTINO)
    produto = any(normalizar(t) in conjunto for t in TERMOS_PRODUTO)
    if evento:
        return "Eventos e feiras", "Evento/encontro"
    if destino:
        return "Destinos e estrutura", "Destino/camping"
    if produto:
        if any(t in conjunto for t in ("lancamento", "novo modelo", "apresenta")):
            return "Lançamentos nacionais", "Lançamento"
        return "Equipamentos e tecnologia", "Equipamento"
    if categoria_atual == "Guias e vida a bordo":
        return categoria_atual, "Guia"
    if categoria_atual == "Histórias e comunidade":
        return categoria_atual, "História/comunidade"
    if categoria_atual in {"Novidades internacionais", "Tendências internacionais"}:
        return categoria_atual, "Notícia"
    return "Últimas notícias", "Notícia"


def adaptar(bruto: dict) -> dict | None:
    titulo = primeiro(bruto, "titulo", "title", "headline", "assunto")
    resumo = limpar_texto(primeiro(bruto, "resumo", "summary", "descricao", "description", "texto"))
    link = resolver_google_news(primeiro(bruto, "link_original", "fonte_url", "link", "url"))
    if not titulo or not link:
        registrar(f"DESCARTADO: título/link ausente: {titulo or '(sem título)'}")
        return None

    pagina = metadados_da_pagina(link)
    link = texto(pagina.get("url")) or link
    if host(link) == "news.google.com" or not link.startswith("https://"):
        registrar(f"DESCARTADO: link original inválido: {titulo}")
        return None

    if len(resumo) < MIN_RESUMO:
        resumo = limpar_texto(pagina.get("resumo", ""))
    if len(resumo) < MIN_RESUMO:
        registrar(f"DESCARTADO: resumo insuficiente ({len(resumo)}): {titulo}")
        return None

    titulo_pagina = limpar_texto(pagina.get("titulo", ""))
    if titulo_pagina and len(titulo_pagina) >= 20:
        titulo = titulo_pagina
    fonte = primeiro(bruto, "fonte", "source", "site")
    if not fonte or fonte.casefold() == "news.google.com":
        fonte = texto(pagina.get("fonte")) or host(link)

    data = primeiro(bruto, "data", "date", "published", "data_fonte", "data_publicacao")
    categoria_atual = primeiro(bruto, "categoria_sugerida", "categoria", "category")
    categoria, tipo = classificar(titulo, resumo, categoria_atual)
    conjunto = normalizar(" ".join((titulo, resumo, fonte, link, categoria)))
    h = host(link)
    brasil = bool(
        bruto.get("mercado") == "Brasil"
        or bruto.get("pais") == "Brasil"
        or h.endswith(".br")
        or any(h == d or h.endswith("." + d) for d in DOMINIOS_BRASIL)
        or any(normalizar(t) in conjunto for t in TERMOS_BRASIL)
    )

    valor = bruto.get("pontuacao_editorial", bruto.get("pontuacao", bruto.get("score", 0)))
    try:
        pontuacao = float(valor)
    except (TypeError, ValueError):
        pontuacao = 0.0
    nota = pontuacao + (18 if brasil else 0) + (25 if tipo == "Evento/encontro" else 0)

    return {
        "titulo": titulo[:240],
        "resumo": resumo[:700],
        "fonte": fonte,
        "link": link,
        "data": data,
        "categoria_sugerida": categoria,
        "origem": "Brasil" if brasil else "Internacional",
        "tipo": tipo,
        "pontuacao_original": pontuacao,
        "pontuacao_selecao": round(nota, 2),
        "arquivo_origem": bruto.get("_arquivo_origem", ""),
        "fontes_complementares": [],
    }


def similaridade(a: dict, b: dict) -> float:
    ta, tb = normalizar(a["titulo"]), normalizar(b["titulo"])
    sequencia = SequenceMatcher(None, ta, tb).ratio()
    sa, sb = set(ta.split()), set(tb.split())
    uniao = sa | sb
    jaccard = len(sa & sb) / len(uniao) if uniao else 0.0
    return max(sequencia, jaccard)


def consolidar(itens: list[dict]) -> list[dict]:
    saida: list[dict] = []
    for item in sorted(itens, key=lambda x: x["pontuacao_selecao"], reverse=True):
        duplicada = next((x for x in saida if x["link"].rstrip("/").casefold() == item["link"].rstrip("/").casefold() or similaridade(x, item) >= SIMILARIDADE_DUPLICADA), None)
        if duplicada:
            extra = {"titulo": item["fonte"], "url": item["link"]}
            if extra["url"] != duplicada["link"] and extra not in duplicada["fontes_complementares"]:
                duplicada["fontes_complementares"].append(extra)
            registrar(f"CONSOLIDADO: {item['titulo']} -> {duplicada['titulo']}")
        else:
            saida.append(item)
    registrar(f"Candidatos válidos e distintos: {len(saida)}")
    return saida


def escolher(itens: list[dict]) -> list[dict]:
    br = [x for x in itens if x["origem"] == "Brasil"]
    inter = [x for x in itens if x["origem"] == "Internacional"]
    escolhidos: list[dict] = []

    def um(pool: list[dict]) -> None:
        for item in pool:
            if item not in escolhidos:
                escolhidos.append(item)
                return

    um([x for x in br if x["tipo"] == "Evento/encontro"])
    um([x for x in br if x["tipo"] in {"Lançamento", "Equipamento"}])
    um([x for x in br if x["tipo"] == "Destino/camping"])
    for pool in (br, inter, itens):
        for item in pool:
            if len(escolhidos) >= MAX_OPCOES:
                break
            if item not in escolhidos:
                escolhidos.append(item)
    if len(escolhidos) < MAX_OPCOES:
        return []
    for numero, item in enumerate(escolhidos[:MAX_OPCOES], 1):
        item["opcao"] = numero
    return escolhidos[:MAX_OPCOES]


def markdown(opcoes: list[dict]) -> str:
    linhas = [
        "# Cinco opções de pauta para aprovação", "",
        f"- Opções do Brasil: **{sum(x['origem'] == 'Brasil' for x in opcoes)}**",
        f"- Eventos ou encontros: **{sum(x['tipo'] == 'Evento/encontro' for x in opcoes)}**", "",
        "Use um único comentário `/escolher N` para indicar a pauta desejada.", "",
    ]
    for item in opcoes:
        linhas += [
            f"## Opção {item['opcao']} · {item['origem']} · {item['tipo']}", "",
            f"**Título:** {item['titulo']}", f"**Fonte:** {item['fonte']}",
            f"**Categoria:** {item['categoria_sugerida']}",
            f"**Pontuação de seleção:** {item['pontuacao_selecao']}",
            f"**Link:** {item['link']}", "", item["resumo"], "",
        ]
    linhas += [
        "## Regras aplicadas", "", "- Cinco opções com link original HTTPS.",
        "- Resumo factual com pelo menos 120 caracteres.",
        "- Assuntos semelhantes consolidados em uma pauta.",
        "- Categoria e tipo recalculados pelo conteúdo.", "",
    ]
    return "\n".join(linhas)


def main() -> None:
    SAIDA.unlink(missing_ok=True)
    RESUMO.unlink(missing_ok=True)
    adaptados = [x for bruto in carregar() if (x := adaptar(bruto))]
    candidatos = consolidar(adaptados)
    opcoes = escolher(candidatos)
    RELATORIO.write_text("\n".join(LOG) + "\n", encoding="utf-8")
    if len(opcoes) != MAX_OPCOES:
        raise SystemExit(
            f"Somente {len(candidatos)} pautas válidas e distintas foram encontradas; "
            f"são necessárias {MAX_OPCOES}. Nenhum PR ou e-mail será criado."
        )
    SAIDA.write_text(json.dumps(opcoes, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    RESUMO.write_text(markdown(opcoes), encoding="utf-8")
    registrar(f"Selecionadas {len(opcoes)} pautas qualificadas.")
    RELATORIO.write_text("\n".join(LOG) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
