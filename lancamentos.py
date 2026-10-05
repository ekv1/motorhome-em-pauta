"""Identifica lançamentos de modelos e preenche os campos usados pelo site.

Uso no coletor, logo antes de gravar um rascunho:
    from lancamentos import enriquecer
    previa = enriquecer(previa)

A faixa "Lançamentos nacionais" só exibe itens com
destaque = "lancamento" e mercado = "Brasil".
Nada aqui publica: os campos vão para o rascunho e passam pela revisão.
"""
import json
import re
import unicodedata
from pathlib import Path

FONTES_NACIONAIS = {"ANACAMP", "MaCamp"}

GATILHOS = (
    "lanca", "lancamento", "novo modelo", "nova linha", "apresenta", "estreia",
    "nova geracao", "linha 20", "launches", "introduces", "unveils", "debuts",
)

TIPOS = (
    ("Camper", ("camper", "pop up", "pop-up", "flatbed", "cacamba")),
    ("Trailer", ("trailer", "teardrop", "reboque", "quinta roda", "caravan")),
    ("Van", ("van ", "vanhome", "van home", "sprinter", "ducato", "daily")),
    ("Motorhome", ("motorhome", "motor home", "motor-home")),
)


def _normalizar(texto):
    sem_acento = unicodedata.normalize("NFKD", texto or "")
    return "".join(c for c in sem_acento if not unicodedata.combining(c)).casefold()


def _fabricantes():
    caminho = Path("fabricantes.json")
    if not caminho.exists():
        return []
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    return dados if isinstance(dados, list) else []


def parece_lancamento(titulo):
    t = " " + _normalizar(titulo) + " "
    return any(re.search(r"\b" + re.escape(g), t) for g in GATILHOS)


def tipo_do_veiculo(titulo, categorias_fabricante=()):
    t = " " + _normalizar(titulo) + " "
    for tipo, palavras in TIPOS:
        if any(p in t for p in palavras):
            return tipo
    # Sem pista no título: usa o tipo único do fabricante, se houver.
    mapa = {"Trailers": "Trailer", "Campers": "Camper", "Motorhomes e vans": "Motorhome"}
    tipos = {mapa[c] for c in categorias_fabricante if c in mapa}
    return tipos.pop() if len(tipos) == 1 else ""


def fabricante_citado(titulo):
    t = _normalizar(titulo)
    for f in _fabricantes():
        if any(_normalizar(a) in t for a in f.get("apelidos", [])):
            return f
    return None


def enriquecer(previa):
    """Acrescenta campos de lançamento quando o título indicar um novo modelo."""
    titulo = previa.get("titulo", "")
    if not parece_lancamento(titulo):
        return previa

    fab = fabricante_citado(titulo)
    nacional = (
        previa.get("fonte") in FONTES_NACIONAIS
        and fab is not None
        and fab.get("lancamento_nacional", False)   # revendas e importadoras não contam
    )

    previa["destaque"] = "lancamento"
    previa["mercado"] = "Brasil" if nacional else "Internacional"
    previa["tipo_veiculo"] = tipo_do_veiculo(titulo, fab.get("categorias", []) if fab else ())
    if fab:
        previa["marca"] = fab["nome"]
        if fab.get("uf"):
            previa["uf"] = fab["uf"]
    previa.setdefault("origem", "imprensa")
    # Lançamento nacional sem fabricante reconhecido fica para revisão manual.
    if previa.get("fonte") in FONTES_NACIONAIS and not nacional:
        previa["revisar_lancamento"] = "Fabricante não identificado na lista de fabricantes brasileiros"
    return previa
