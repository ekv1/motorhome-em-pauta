#!/usr/bin/env python3
"""Bloqueia pautas fracas antes do e-mail e do Pull Request editorial."""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import urlparse

ARQUIVO = Path(sys.argv[1] if len(sys.argv) > 1 else "pautas-selecionadas.json")
QUANTIDADE_EXIGIDA = 5
MIN_RESUMO = 120
SIMILARIDADE_MAXIMA = 0.72

CATEGORIAS = {
    "Eventos e feiras",
    "Destinos e estrutura",
    "Guias e vida a bordo",
    "Histórias e comunidade",
    "Lançamentos nacionais",
    "Equipamentos e tecnologia",
    "Novidades internacionais",
    "Tendências internacionais",
    "Últimas notícias",
}

TIPOS = {
    "Evento/encontro",
    "Guia",
    "Notícia",
    "Lançamento",
    "Equipamento",
    "Destino/camping",
    "História/comunidade",
}

PALAVRAS_VAZIAS = {
    "a", "as", "ao", "aos", "com", "da", "das", "de", "do", "dos", "e",
    "em", "na", "nas", "no", "nos", "o", "os", "para", "por", "um", "uma",
}


def texto(v: object) -> str:
    return v.strip() if isinstance(v, str) else ""


def normalizar(v: str) -> str:
    v = unicodedata.normalize("NFKD", v.casefold())
    v = "".join(c for c in v if not unicodedata.combining(c))
    tokens = re.findall(r"[a-z0-9]+", v)
    return " ".join(t for t in tokens if t not in PALAVRAS_VAZIAS)


def host(url: str) -> str:
    try:
        return urlparse(url).netloc.casefold().removeprefix("www.")
    except ValueError:
        return ""


def validar_item(item: dict, numero: int) -> list[str]:
    erros: list[str] = []
    obrigatorios = (
        "titulo", "resumo", "fonte", "link", "categoria_sugerida", "origem", "tipo"
    )
    for campo in obrigatorios:
        if not texto(item.get(campo)):
            erros.append(f"opção {numero}: campo ausente ou vazio: {campo}")

    resumo = texto(item.get("resumo"))
    if resumo and len(resumo) < MIN_RESUMO:
        erros.append(
            f"opção {numero}: resumo curto ({len(resumo)} caracteres; mínimo {MIN_RESUMO})"
        )

    url = texto(item.get("link"))
    if url:
        if not url.startswith("https://"):
            erros.append(f"opção {numero}: link precisa usar HTTPS")
        if host(url) == "news.google.com":
            erros.append(
                f"opção {numero}: link do Google News não foi resolvido para a fonte original"
            )

    categoria = texto(item.get("categoria_sugerida"))
    tipo = texto(item.get("tipo"))
    if categoria and categoria not in CATEGORIAS:
        erros.append(f"opção {numero}: categoria não reconhecida: {categoria}")
    if tipo and tipo not in TIPOS:
        erros.append(f"opção {numero}: tipo não reconhecido: {tipo}")

    titulo_norm = normalizar(texto(item.get("titulo")))
    if "camping" in titulo_norm and categoria == "Últimas notícias":
        erros.append(
            f"opção {numero}: pauta de camping não deve ficar em Últimas notícias"
        )
    if any(p in titulo_norm for p in ("trailer", "motorhome", "camper")):
        if tipo == "Evento/encontro" and not any(
            p in titulo_norm for p in ("expo", "feira", "encontro", "caravana", "evento")
        ):
            erros.append(
                f"opção {numero}: veículo/produto classificado como evento sem indicador de evento"
            )

    return erros


def main() -> int:
    if not ARQUIVO.is_file():
        print(f"ERRO: arquivo não encontrado: {ARQUIVO}")
        return 1

    try:
        pautas = json.loads(ARQUIVO.read_text(encoding="utf-8"))
    except json.JSONDecodeError as erro:
        print(f"ERRO: JSON inválido: {erro}")
        return 1

    erros: list[str] = []
    if not isinstance(pautas, list):
        erros.append("o conteúdo precisa ser uma lista")
        pautas = []

    if len(pautas) != QUANTIDADE_EXIGIDA:
        erros.append(
            f"eram esperadas {QUANTIDADE_EXIGIDA} pautas; recebidas {len(pautas)}"
        )

    for numero, item in enumerate(pautas, 1):
        if not isinstance(item, dict):
            erros.append(f"opção {numero}: item não é objeto JSON")
            continue
        erros.extend(validar_item(item, numero))

    for i in range(len(pautas)):
        if not isinstance(pautas[i], dict):
            continue
        t1 = normalizar(texto(pautas[i].get("titulo")))
        for j in range(i + 1, len(pautas)):
            if not isinstance(pautas[j], dict):
                continue
            t2 = normalizar(texto(pautas[j].get("titulo")))
            if not t1 or not t2:
                continue
            similaridade = SequenceMatcher(None, t1, t2).ratio()
            tokens1, tokens2 = set(t1.split()), set(t2.split())
            uniao = tokens1 | tokens2
            jaccard = len(tokens1 & tokens2) / len(uniao) if uniao else 0
            if max(similaridade, jaccard) >= SIMILARIDADE_MAXIMA:
                erros.append(
                    f"opções {i + 1} e {j + 1}: provável duplicidade "
                    f"(similaridade {max(similaridade, jaccard):.2f})"
                )

    if erros:
        print("STATUS: PAUTAS REPROVADAS")
        for erro in erros:
            print(" -", erro)
        print(f"\nTotal de falhas: {len(erros)}")
        return 1

    print("STATUS: PAUTAS PRONTAS PARA ESCOLHA")
    print(f"Quantidade: {len(pautas)}")
    for numero, pauta in enumerate(pautas, 1):
        print(f" {numero}. {pauta['titulo']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
