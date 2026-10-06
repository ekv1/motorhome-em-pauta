#!/usr/bin/env python3
"""Valida notícias propostas antes de permitir merge/publicação."""
import argparse
import json
from pathlib import Path

from qualidade_editorial import validar_materia


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("arquivo", nargs="?", default="noticias.json")
    parser.add_argument("--sem-imagem", action="store_true")
    args = parser.parse_args()

    caminho = Path(args.arquivo)
    if not caminho.is_file():
        print(f"ERRO: arquivo não encontrado: {caminho}")
        return 1

    dados = json.loads(caminho.read_text(encoding="utf-8"))
    if not isinstance(dados, list):
        print("ERRO: o arquivo deve conter uma lista JSON")
        return 1

    falhas = 0
    for numero, item in enumerate(dados, 1):
        if not isinstance(item, dict):
            print(f"ERRO: item {numero} não é um objeto")
            falhas += 1
            continue
        ok, erros, metricas = validar_materia(item, exigir_imagem=not args.sem_imagem)
        titulo = item.get("titulo", f"Item {numero}")
        print(f"\n{numero}. {titulo}")
        print("Métricas:", json.dumps(metricas, ensure_ascii=False))
        if ok:
            print("STATUS: PRONTO PARA REVISÃO")
        else:
            falhas += 1
            print("STATUS: MATÉRIA INCOMPLETA")
            for erro in erros:
                print(" -", erro)

    print(f"\nMatérias verificadas: {len(dados)}")
    print(f"Matérias incompletas: {falhas}")
    return 1 if falhas else 0


if __name__ == "__main__":
    raise SystemExit(main())
