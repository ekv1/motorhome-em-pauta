"""Verifica quais sites de fabricantes oferecem feed RSS utilizavel.
Nao chama IA, nao altera o site e nao publica nada."""
import json
import xml.etree.ElementTree as ET
from urllib.parse import urljoin
from urllib.request import Request, urlopen

CAMINHOS = ("feed/", "blog/feed/", "noticias/feed/", "rss/")


def tentar(url):
    pedido = Request(url, headers={"User-Agent": "MotorhomeEmPauta/0.1 (teste de fontes)"})
    with urlopen(pedido, timeout=15) as r:
        raiz = ET.fromstring(r.read(1_000_000))
    if raiz.tag != "rss":
        return None
    itens = raiz.findall("./channel/item")
    if not itens:
        return None
    ultimo = itens[0]
    return len(itens), (ultimo.findtext("pubDate") or "").strip(), (ultimo.findtext("title") or "").strip()


def main():
    fabricantes = json.load(open("fabricantes.json", encoding="utf-8"))
    com_feed = []
    for f in fabricantes:
        achou = False
        for caminho in CAMINHOS:
            url = urljoin(f["site"], caminho)
            try:
                resultado = tentar(url)
            except Exception:
                continue
            if resultado:
                qtd, data, titulo = resultado
                print(f"COM FEED | {f['nome']} | {qtd} itens | ultimo: {data} | {titulo[:70]}")
                print(f"           {url}")
                com_feed.append({"nome": f["nome"], "feed": url, "itens": qtd, "ultimo": data})
                achou = True
                break
        if not achou:
            print(f"SEM FEED | {f['nome']}")
    print("---")
    print("Fabricantes verificados:", len(fabricantes))
    print("Com feed RSS utilizavel:", len(com_feed))
    json.dump(com_feed, open("fontes-fabricantes.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print("TESTE: nenhum arquivo do site foi alterado.")


if __name__ == "__main__":
    main()
