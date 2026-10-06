#!/usr/bin/env python3
"""Validação editorial compartilhada do Motorhome em Pauta."""
from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse

MIN_PALAVRAS = 800
MIN_SECOES = 5
MIN_PARAGRAFOS_POR_SECAO = 2
MIN_RESUMO = 300
MAX_RESUMO = 500
MIN_FONTES = 2

CATEGORIAS = {
    "Últimas notícias",
    "Eventos e feiras",
    "Histórias e comunidade",
    "Guias e vida a bordo",
    "Novidades internacionais",
    "Equipamentos e tecnologia",
    "Destinos e estrutura",
    "Lançamentos nacionais",
    "Tendências internacionais",
}


def _texto(valor: object) -> str:
    return valor.strip() if isinstance(valor, str) else ""


def _url_https(valor: object) -> bool:
    if not isinstance(valor, str):
        return False
    partes = urlparse(valor.strip())
    return partes.scheme == "https" and bool(partes.netloc)


def contar_palavras(item: dict) -> int:
    corpo = item.get("corpo") if isinstance(item.get("corpo"), dict) else {}
    partes = [
        _texto(item.get("titulo")),
        _texto(item.get("resumo")),
        _texto(corpo.get("abertura")),
        _texto(corpo.get("contexto_brasil")),
    ]
    for secao in corpo.get("secoes") or []:
        if not isinstance(secao, dict):
            continue
        partes.append(_texto(secao.get("subtitulo")))
        partes.extend(_texto(p) for p in (secao.get("paragrafos") or []))
    return len(re.findall(r"\b[\wÀ-ÿ'-]+\b", " ".join(partes), flags=re.UNICODE))


def validar_materia(item: dict, *, exigir_imagem: bool = True) -> tuple[bool, list[str], dict]:
    erros: list[str] = []

    for campo in ("titulo", "resumo", "categoria_sugerida", "data", "fonte", "link", "slug"):
        if not _texto(item.get(campo)):
            erros.append(f"campo obrigatório ausente: {campo}")

    categoria = _texto(item.get("categoria_sugerida"))
    if categoria and categoria not in CATEGORIAS:
        erros.append(f"categoria não reconhecida: {categoria}")

    if item.get("link") and not _url_https(item.get("link")):
        erros.append("link principal precisa usar HTTPS")

    resumo = _texto(item.get("resumo"))
    if resumo and not (MIN_RESUMO <= len(resumo) <= MAX_RESUMO):
        erros.append(f"resumo deve ter entre {MIN_RESUMO} e {MAX_RESUMO} caracteres")

    corpo = item.get("corpo") if isinstance(item.get("corpo"), dict) else None
    if not corpo:
        erros.append("corpo da matéria ausente")
        corpo = {}

    if not _texto(corpo.get("abertura")):
        erros.append("abertura ausente")

    contexto = _texto(corpo.get("contexto_brasil"))
    if not contexto:
        erros.append("contexto brasileiro ausente")

    secoes = [s for s in (corpo.get("secoes") or []) if isinstance(s, dict)]
    if len(secoes) < MIN_SECOES:
        erros.append(f"matéria precisa ter pelo menos {MIN_SECOES} seções")

    paragrafos_total = 0
    for indice, secao in enumerate(secoes, 1):
        if not _texto(secao.get("subtitulo")):
            erros.append(f"seção {indice} sem subtítulo")
        paragrafos = [
            _texto(p) for p in (secao.get("paragrafos") or []) if _texto(p)
        ]
        paragrafos_total += len(paragrafos)
        if len(paragrafos) < MIN_PARAGRAFOS_POR_SECAO:
            erros.append(
                f"seção {indice} precisa de pelo menos {MIN_PARAGRAFOS_POR_SECAO} parágrafos"
            )

    palavras = contar_palavras(item)
    if palavras < MIN_PALAVRAS:
        erros.append(f"matéria precisa ter pelo menos {MIN_PALAVRAS} palavras; possui {palavras}")

    fontes = []
    if _url_https(item.get("link")):
        fontes.append(item.get("link"))
    for fonte in item.get("fontes_complementares") or []:
        if isinstance(fonte, dict) and _url_https(fonte.get("url")):
            fontes.append(fonte.get("url"))
    fontes_unicas = list(dict.fromkeys(fontes))
    if len(fontes_unicas) < MIN_FONTES:
        erros.append(f"matéria precisa de pelo menos {MIN_FONTES} fontes HTTPS verificáveis")

    imagem = _texto(item.get("imagem"))
    if exigir_imagem and not imagem:
        erros.append("imagem ausente")
    if imagem and not (Path(imagem).is_file() or _url_https(imagem)):
        erros.append(f"imagem não encontrada: {imagem}")

    credito = _texto(item.get("imagem_credito") or item.get("credito_imagem"))
    origem = _texto(
        item.get("imagem_origem")
        or item.get("fonte_imagem")
        or item.get("imagem_legenda")
    )
    if exigir_imagem and imagem and not credito:
        erros.append("crédito da imagem ausente")
    if exigir_imagem and imagem and not origem:
        erros.append("origem/licença da imagem ausente")

    metricas = {
        "palavras": palavras,
        "secoes": len(secoes),
        "paragrafos": paragrafos_total,
        "fontes": len(fontes_unicas),
        "contexto_brasil": bool(contexto),
        "imagem": bool(imagem),
        "credito_imagem": bool(credito),
        "origem_imagem": bool(origem),
    }
    return not erros, erros, metricas
