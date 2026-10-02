import json
import os
import re
from datetime import datetime
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

from google import genai


FONTE = "https://anacamp.com/"
ARQUIVO_REGISTROS = Path("noticias.json")
MODELO_IA = "gemini-3.8-flash"

# Este filtro apenas seleciona candidatas para o teste.
# Uma palavra no titulo nao equivale a aprovacao editorial.
TERMOS_RELEVANTES = (
    "motorhome",
    "motor home",
    "caravanismo",
    "caravanista",
    "campista",
    "camping",
    "trailer",
    "campervan",
    "ponto de apoio",
)


class LeitorDeNoticias(HTMLParser):
    def __init__(self):
        super().__init__()
        self.link_atual = None
        self.texto_atual = []
        self.noticias = []

    def handle_starttag(self, tag, attrs):
        if tag != "a" or self.link_atual is not None:
            return

        href = dict(attrs).get("href", "")
        link = urljoin(FONTE, href)
        partes = urlparse(link)

        if (
            partes.netloc == "anacamp.com"
            and partes.path.startswith("/noticia/")
        ):
            self.link_atual = link
            self.texto_atual = []

    def handle_data(self, texto):
        if self.link_atual is not None:
            self.texto_atual.append(texto)

    def handle_endtag(self, tag):
        if tag != "a" or self.link_atual is None:
            return

        texto = " ".join(" ".join(self.texto_atual).split())

        if texto:
            self.noticias.append((texto, self.link_atual))

        self.link_atual = None
        self.texto_atual = []


class LeitorDeDescricao(HTMLParser):
    def __init__(self):
        super().__init__()
        self.metadados = {}

    def handle_starttag(self, tag, attrs):
        if tag != "meta":
            return

        atributos = dict(attrs)
        nome = atributos.get("property") or atributos.get("name")

        if nome in ("og:description", "description"):
            valor = unescape(
                atributos.get("content", "")
            ).strip()

            if valor:
                self.metadados[nome] = valor

    def obter_descricao(self):
        return (
            self.metadados.get("og:description")
            or self.metadados.get("description")
            or ""
        )


def ler_links_salvos():
    registros = json.loads(
        ARQUIVO_REGISTROS.read_text(encoding="utf-8")
    )

    if not isinstance(registros, list):
        raise ValueError("noticias.json deve conter uma lista.")

    return {
        item["link"]
        for item in registros
        if isinstance(item, dict)
        and isinstance(item.get("link"), str)
    }


def baixar_pagina(url):
    pedido = Request(
        url,
        headers={
            "User-Agent": "MotorhomeEmPauta/0.1 (teste de coleta)"
        },
    )

    with urlopen(pedido, timeout=20) as resposta:
        return resposta.read(1000000).decode(
            "utf-8",
            errors="replace",
        )


def buscar_noticias():
    pagina = baixar_pagina(FONTE)

    leitor = LeitorDeNoticias()
    leitor.feed(pagina)

    # Remove pares identicos de titulo e link.
    return list(dict.fromkeys(leitor.noticias))


def buscar_descricao(link):
    pagina = baixar_pagina(link)

    leitor = LeitorDeDescricao()
    leitor.feed(pagina)

    return leitor.obter_descricao()


def analisar(texto, link, links_salvos):
    encontrado = re.match(
        r"^(\d{2}/\d{2}/\d{4})\s+(.+)$",
        texto,
    )

    if not encontrado:
        return "IGNORADA: data nao identificada", texto, link

    data_texto, titulo = encontrado.groups()

    try:
        datetime.strptime(data_texto, "%d/%m/%Y")
    except ValueError:
        return "IGNORADA: data invalida", titulo, link

    if link in links_salvos:
        situacao = "REPETIDA"
    elif any(
        termo in titulo.casefold()
        for termo in TERMOS_RELEVANTES
    ):
        situacao = "CANDIDATA: verificar relevancia"
    else:
        situacao = "REVISAR: titulo sem termo especifico"

    return situacao, f"{data_texto} | {titulo}", link


def testar_avaliacao_ia(titulo, link):
    if not os.getenv("GEMINI_API_KEY"):
        print("IA: chave nao encontrada; noticia nao avaliada.")
        return

    try:
        descricao = buscar_descricao(link)

        if not descricao:
            print("IA: descricao ausente; noticia nao avaliada.")
            return

        prompt = f"""
Voce avalia uma noticia para o site Motorhome em Pauta.

Use somente o titulo e a descricao fornecidos abaixo.
Nao invente datas, precos, horarios, vagas ou servicos.
Nao diga que o site verificou pessoalmente o local.

Responda em portugues com exatamente tres linhas:
Relevancia: SIM ou NAO
Motivo: uma frase curta
Resumo: uma frase curta baseada somente nos dados recebidos

Titulo: {titulo}
Descricao: {descricao}
"""

        # Manter o cliente aberto durante a chamada evita o erro
        # "client has been closed" visto no teste anterior.
        with genai.Client() as client:
            resposta = client.models.generate_content(
                model=MODELO_IA,
                contents=prompt,
            )

        texto = (resposta.text or "").strip()
        linhas = texto.splitlines()

        if (
            len(linhas) != 3
            or not linhas[0].startswith("Relevancia: ")
            or linhas[0].split(": ", 1)[1].strip()
            not in ("SIM", 
