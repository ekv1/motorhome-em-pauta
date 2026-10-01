import json
import re
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

FONTE = "https://anacamp.com/"
ARQUIVO_REGISTROS = Path("noticias.json")

# Filtro inicial: sugere relevância, mas não aprova publicação.
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


def ler_links_salvos():
    registros = json.loads(
        ARQUIVO_REGISTROS.read_text(encoding="utf-8")
    )

    if not isinstance(registros, list):
        raise ValueError("noticias.json deve conter uma lista.")

    return {
        item["link"]
        for item in registros
        if isinstance(item, dict) and isinstance(item.get("link"), str)
    }


def buscar_noticias():
    pedido = Request(
        FONTE,
        headers={"User-Agent": "MotorhomeEmPauta/0.1 (teste de coleta)"},
    )

    with urlopen(pedido, timeout=20) as resposta:
        pagina = resposta.read(1000000).decode(
            "utf-8", errors="replace"
        )

    leitor = LeitorDeNoticias()
    leitor.feed(pagina)

    # Remove links idênticos encontrados mais de uma vez na página.
    return list(dict.fromkeys(leitor.noticias))


def analisar(texto, link, links_salvos):
    encontrado = re.match(
        r"^(\d{2}/\d{2}/\d{4})\s+(.+)$", texto
    )

    if not encontrado:
        return "IGNORADA: data não identificada", texto, link

    data_texto, titulo = encontrado.groups()

    try:
        datetime.strptime(data_texto, "%d/%m/%Y")
    except ValueError:
        return "IGNORADA: data inválida", titulo, link

    if link in links_salvos:
        situacao = "REPETIDA"
    elif any(termo in titulo.casefold() for termo in TERMOS_RELEVANTES):
        situacao = "CANDIDATA: verificar relevância"
    else:
        situacao = "REVISAR: título sem termo específico"

    return situacao, f"{data_texto} | {titulo}", link


def main():
    links_salvos = ler_links_salvos()
    noticias = buscar_noticias()

    print("Notícias encontradas:", len(noticias))
    print("Links já salvos:", len(links_salvos))

    for texto, link in noticias:
        situacao, descricao, link = analisar(
            texto, link, links_salvos
        )
        print(situacao, "|", descricao)
        print("Fonte:", link)

    print("TESTE: nenhum arquivo foi alterado ou publicado.")


if __name__ == "__main__":
    main()
