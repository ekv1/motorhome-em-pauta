import json
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from groq import APIStatusError, Groq
from lancamentos import (
    enriquecer,
    parece_lancamento,
    tipo_do_veiculo,
)


ANACAMP = "https://anacamp.com/"

MACAMP_FEED = (
    "https://macamp.com.br/category/noticias/"
    "caravanismo/feed/"
)

APOLO_FEED = "https://apolotrailer.com.br/feed/"

ESTRELLA_FEED = (
    "http://www.estrella-mobil.com.br/feed/"
)

ARQUIVO_PUBLICADOS = Path("noticias.json")
ARQUIVO_RASCUNHOS = Path("rascunhos-coletor.json")

MODELO_IA = "openai/gpt-oss-20b"
IDADE_MAXIMA_DIAS = 14
FUSO = ZoneInfo("America/Sao_Paulo")


FONTES_FABRICANTES = {
    "Apolo Trailer": {
        "marca": "Apolo Trailer",
        "uf": "SC",
        "categorias": [
            "Trailers",
            "Motorhomes e vans",
        ],
    },
    "Estrella Mobil": {
        "marca": "Estrella Mobil Motorhomes",
        "uf": "SP",
        "categorias": [
            "Motorhomes e vans",
        ],
    },
}


# Os termos selecionam candidatas.
# Eles nao autorizam publicacao.
TERMOS_RELEVANTES = (
    "motorhome",
    "motor home",
    "motor-home",
    "caravanismo",
    "caravanista",
    "campista",
    "camping",
    "trailer",
    "camper",
    "campervan",
    "vanhome",
    "van home",
    "ponto de apoio",
    "lança",
    "lanca",
    "lançamento",
    "lancamento",
    "novo modelo",
    "nova geração",
    "nova geracao",
    "nova linha",
    "apresenta",
    "estreia",
)


class LeitorANACAMP(HTMLParser):
    def __init__(self):
        super().__init__()
        self.link_atual = None
        self.texto_atual = []
        self.itens = []

    def handle_starttag(self, tag, attrs):
        if tag != "a" or self.link_atual is not None:
            return

        link = urljoin(
            ANACAMP,
            dict(attrs).get("href", ""),
        )

        partes = urlparse(link)

        if (
            partes.scheme == "https"
            and partes.hostname == "anacamp.com"
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

        texto = " ".join(
            " ".join(self.texto_atual).split()
        )

        if texto:
            self.itens.append(
                (
                    texto,
                    self.link_atual,
                )
            )

        self.link_atual = None
        self.texto_atual = []


class LeitorMetadados(HTMLParser):
    def __init__(self):
        super().__init__()
        self.metadados = {}

    def handle_starttag(self, tag, attrs):
        if tag != "meta":
            return

        atributos = dict(attrs)

        nome = (
            atributos.get("property")
            or atributos.get("name")
        )

        if nome in (
            "og:description",
            "description",
        ):
            valor = unescape(
                atributos.get(
                    "content",
                    "",
                )
            ).strip()

            if valor:
                self.metadados[nome] = valor

    def descricao(self):
        return (
            self.metadados.get(
                "og:description"
            )
            or self.metadados.get(
                "description"
            )
            or ""
        )


def baixar(url):
    pedido = Request(
        url,
        headers={
            "User-Agent": (
                "MotorhomeEmPauta/0.2"
            )
        },
    )

    with urlopen(
        pedido,
        timeout=20,
    ) as resposta:
        return resposta.read(
            1_000_000
        )


def ler_publicados():
    registros = json.loads(
        ARQUIVO_PUBLICADOS.read_text(
            encoding="utf-8"
        )
    )

    if not isinstance(registros, list):
        raise ValueError(
            "noticias.json deve conter uma lista."
        )

    return {
        item["link"].strip()
        for item in registros
        if isinstance(item, dict)
        and isinstance(
            item.get("link"),
            str,
        )
    }


def coletar_anacamp():
    pagina = baixar(
        ANACAMP
    ).decode(
        "utf-8",
        errors="replace",
    )

    leitor = LeitorANACAMP()
    leitor.feed(pagina)

    noticias = []

    for texto, link in dict.fromkeys(
        leitor.itens
    ):
        encontrado = re.match(
            r"^(\d{2}/\d{2}/\d{4})\s+(.+)$",
            
