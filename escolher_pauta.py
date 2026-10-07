#!/usr/bin/env python3
"""Processa o comando /escolher N e grava a pauta editorial escolhida."""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

COMANDO = re.compile(r"^\s*/escolher\s+([1-5])\s*$", re.IGNORECASE)


def carregar_json(caminho: Path):
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit(f"ERRO: arquivo não encontrado: {caminho}")
    except json.JSONDecodeError as erro:
        raise SystemExit(f"ERRO: JSON inválido em {caminho}: {erro}")


def extrair_opcao(comentario: str) -> int:
    correspondencia = COMANDO.fullmatch(comentario or "")
    if not correspondencia:
        raise SystemExit("ERRO: use exatamente /escolher N, com N entre 1 e 5.")
    return int(correspondencia.group(1))


def localizar_pauta(dados, numero: int) -> dict:
    if isinstance(dados, dict):
        dados = dados.get("pautas") or dados.get("itens") or dados.get("opcoes") or []
    if not isinstance(dados, list):
        raise SystemExit("ERRO: pautas-selecionadas.json deve conter uma lista.")

    for indice, item in enumerate(dados, 1):
        if not isinstance(item, dict):
            continue
        opcao = item.get("opcao", indice)
        try:
            opcao = int(opcao)
        except (TypeError, ValueError):
            continue
        if opcao == numero:
            return dict(item)

    raise SystemExit(f"ERRO: opção {numero} não existe no arquivo de pautas.")


def validar_pauta(pauta: dict) -> None:
    obrigatorios = ("titulo", "resumo", "link", "fonte")
    ausentes = [campo for campo in obrigatorios if not str(pauta.get(campo, "")).strip()]
    if ausentes:
        raise SystemExit("ERRO: pauta escolhida sem campos obrigatórios: " + ", ".join(ausentes))
    link = str(pauta["link"]).strip()
    if not link.startswith("https://"):
        raise SystemExit("ERRO: a pauta escolhida não possui link HTTPS válido.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--comentario", required=True)
    parser.add_argument("--arquivo", default="pautas-selecionadas.json")
    parser.add_argument("--saida", default="pauta-escolhida.json")
    parser.add_argument("--resumo", default="resumo-pauta-escolhida.md")
    parser.add_argument("--pr", type=int, required=True)
    parser.add_argument("--autor", required=True)
    args = parser.parse_args()

    numero = extrair_opcao(args.comentario)
    pauta = localizar_pauta(carregar_json(Path(args.arquivo)), numero)
    validar_pauta(pauta)

    registro = {
        "status": "APROVADA_PARA_PRODUCAO",
        "opcao": numero,
        "pull_request_selecao": args.pr,
        "aprovada_por": args.autor,
        "aprovada_em_utc": datetime.now(timezone.utc).isoformat(),
        "pauta": pauta,
    }

    Path(args.saida).write_text(
        json.dumps(registro, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    fontes = pauta.get("fontes_complementares") or []
    linhas = [
        "# Pauta aprovada para produção editorial",
        "",
        f"- **Opção:** {numero}",
        f"- **Título:** {pauta['titulo']}",
        f"- **Fonte principal:** {pauta['fonte']}",
        f"- **Link:** {pauta['link']}",
        f"- **Categoria:** {pauta.get('categoria_sugerida', 'Não informada')}",
        f"- **Origem:** {pauta.get('origem', 'Não informada')}",
        f"- **Aprovada por:** {args.autor}",
        f"- **PR de seleção:** #{args.pr}",
        "",
        "## Resumo da pauta",
        "",
        str(pauta["resumo"]).strip(),
        "",
        "## Fontes complementares",
        "",
    ]
    if fontes:
        for fonte in fontes:
            if isinstance(fonte, dict):
                linhas.append(f"- [{fonte.get('titulo', 'Fonte')}]({fonte.get('url', '')})")
    else:
        linhas.append("- Nenhuma fonte complementar registrada.")

    linhas += [
        "",
        "## Próxima etapa",
        "",
        "Produzir a matéria completa, validar conteúdo e abrir um Pull Request editorial separado.",
        "",
        "> Este Pull Request registra a aprovação da pauta e não publica conteúdo diretamente.",
    ]
    Path(args.resumo).write_text("\n".join(linhas) + "\n", encoding="utf-8")
    print(f"OPCAO_ESCOLHIDA={numero}")
    print(f"TITULO_ESCOLHIDO={pauta['titulo']}")


if __name__ == "__main__":
    main()
