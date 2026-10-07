#!/usr/bin/env python3
"""Seleciona exatamente uma pauta aprovada pelo editor."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def carregar_lista(caminho: Path) -> list[dict]:
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    if not isinstance(dados, list):
        raise SystemExit("ERRO: o arquivo de pautas deve conter uma lista.")
    return [item for item in dados if isinstance(item, dict)]


def texto(valor: object) -> str:
    return valor.strip() if isinstance(valor, str) else ""


def validar_pauta(pauta: dict, numero: int) -> None:
    obrigatorios = ("titulo", "resumo", "fonte", "link", "categoria_sugerida")
    ausentes = [campo for campo in obrigatorios if not texto(pauta.get(campo))]
    if ausentes:
        raise SystemExit(
            f"ERRO: a opção {numero} não está pronta. Campos ausentes: "
            + ", ".join(ausentes)
        )
    if not texto(pauta.get("link")).startswith("https://"):
        raise SystemExit(f"ERRO: a opção {numero} não possui link HTTPS válido.")


def criar_resumo(pauta: dict, numero: int) -> str:
    complementares = pauta.get("fontes_complementares") or []
    fontes = [f"- {texto(pauta.get('fonte'))}: {texto(pauta.get('link'))}"]
    for fonte in complementares:
        if isinstance(fonte, dict) and texto(fonte.get("url")):
            fontes.append(
                f"- {texto(fonte.get('titulo')) or texto(fonte.get('fonte')) or 'Fonte complementar'}: "
                f"{texto(fonte.get('url'))}"
            )
    return "\n".join(
        [
            "# Pauta escolhida para produção editorial",
            "",
            f"- **Opção:** {numero}",
            f"- **Título-base:** {texto(pauta.get('titulo'))}",
            f"- **Categoria:** {texto(pauta.get('categoria_sugerida'))}",
            f"- **Origem:** {texto(pauta.get('origem'))}",
            f"- **Tipo:** {texto(pauta.get('tipo'))}",
            f"- **Pontuação:** {pauta.get('pontuacao_selecao', '')}",
            "",
            "## Resumo da pauta",
            texto(pauta.get("resumo")),
            "",
            "## Fontes disponíveis",
            *fontes,
            "",
            "A reportagem completa ainda será gerada, validada e apresentada em Pull Request antes da publicação.",
            "",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="pautas-selecionadas.json")
    parser.add_argument("--option", type=int, required=True)
    parser.add_argument("--output", default="pauta-escolhida.json")
    parser.add_argument("--summary", default="resumo-pauta-escolhida.md")
    args = parser.parse_args()

    entrada = Path(args.input)
    if not entrada.is_file():
        raise SystemExit(f"ERRO: arquivo não encontrado: {entrada}")

    pautas = carregar_lista(entrada)
    if args.option < 1 or args.option > len(pautas):
        raise SystemExit(
            f"ERRO: opção {args.option} inválida. Existem {len(pautas)} opções."
        )

    escolhida = dict(pautas[args.option - 1])
    validar_pauta(escolhida, args.option)
    escolhida["opcao_escolhida"] = args.option
    escolhida["status_editorial"] = "escolhida_para_producao"

    Path(args.output).write_text(
        json.dumps([escolhida], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    Path(args.summary).write_text(
        criar_resumo(escolhida, args.option), encoding="utf-8"
    )
    print(f"Opção {args.option} selecionada: {texto(escolhida.get('titulo'))}")


if __name__ == "__main__":
    main()
