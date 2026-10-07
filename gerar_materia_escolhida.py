#!/usr/bin/env python3
"""
Gera uma reportagem completa a partir de pauta-escolhida.json.

Entradas:
- pauta-escolhida.json
- noticias.json
- variáveis de ambiente:
  - GROQ_API_KEY
  - CLOUDFLARE_ACCOUNT_ID
  - CLOUDFLARE_API_TOKEN

Saídas:
- noticias.json
- resumo-aprovacao.md
- resultado-geracao-materia.txt
- imagens/noticias/<slug>.jpg, quando Cloudflare estiver disponível

A publicação não é feita por este script. O workflow deve criar um
Pull Request para revisão humana.
"""

from __future__ import annotations

import base64
import json
import os
import re
import sys
import time
import unicodedata
from datetime import datetime
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from groq import APIStatusError, BadRequestError, Groq


ARQUIVO_PAUTA = Path("pauta-escolhida.json")
ARQUIVO_NOTICIAS = Path("noticias.json")
ARQUIVO_RESUMO = Path("resumo-aprovacao.md")
ARQUIVO_RELATORIO = Path("resultado-geracao-materia.txt")
PASTA_IMAGENS = Path("imagens/noticias")

MODELO = os.getenv(
    "GROQ_MODEL",
    "openai/gpt-oss-20b",
)

MAX_TENTATIVAS = 3
MIN_PALAVRAS = 800
ALVO_MINIMO = 1100
ALVO_MAXIMO = 1500
MIN_SECOES = 6
MIN_PARAGRAFOS_SECAO = 2

LOG: list[str] = []

IMAGENS_PADRAO = {
    "Últimas notícias": "imagens/capa-estrada.png",
    "Eventos e feiras": "imagens/padrao-eventos.png",
    "Equipamentos e tecnologia": "imagens/ilustrativa-equipamentos.png",
    "Lançamentos nacionais": "imagens/ilustrativa-veiculos.png",
    "Destinos e estrutura": "imagens/padrao-comunidade.png",
    "Guias e vida a bordo": "imagens/guia-organizar.png",
    "Histórias e comunidade": "imagens/padrao-comunidade.png",
    "Tendências internacionais": "imagens/ilustrativa-veiculos.png",
    "Novidades internacionais": "imagens/ilustrativa-veiculos.png",
}


class LeitorPagina(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.titulo = ""
        self.descricao = ""
        self.imagem = ""
        self._em_titulo = False
        self._titulo_partes: list[str] = []
        self._ignorar = 0
        self._texto: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        atributos = {
            chave.lower(): valor or ""
            for chave, valor in attrs
        }

        if tag.lower() in {"script", "style", "noscript", "svg"}:
            self._ignorar += 1
            return

        if tag.lower() == "title":
            self._em_titulo = True

        if tag.lower() != "meta":
            return

        nome = (
            atributos.get("property")
            or atributos.get("name")
            or ""
        ).lower()

        conteudo = unescape(
            atributos.get("content", "")
        ).strip()

        if not conteudo:
            return

        if nome in {"og:title", "twitter:title"} and not self.titulo:
            self.titulo = conteudo
        elif nome in {
            "og:description",
            "twitter:description",
            "description",
        } and not self.descricao:
            self.descricao = conteudo
        elif nome in {
            "og:image",
            "twitter:image",
        } and not self.imagem:
            self.imagem = conteudo

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "noscript", "svg"}:
            self._ignorar = max(0, self._ignorar - 1)
            return

        if tag.lower() == "title":
            self._em_titulo = False

    def handle_data(self, data: str) -> None:
        if self._ignorar:
            return

        texto = " ".join(data.split())

        if not texto:
            return

        if self._em_titulo:
            self._titulo_partes.append(texto)

        self._texto.append(texto)

    def resultado(self) -> dict[str, str]:
        if not self.titulo:
            self.titulo = " ".join(self._titulo_partes).strip()

        texto = " ".join(self._texto)
        texto = re.sub(r"\s+", " ", texto).strip()

        return {
            "titulo": self.titulo,
            "descricao": self.descricao,
            "imagem": self.imagem,
            "texto": texto[:14000],
        }


def registrar(mensagem: str) -> None:
    print(mensagem)
    LOG.append(mensagem)


def ler_json(path: Path, padrao: Any = None) -> Any:
    if not path.is_file():
        return padrao

    try:
        return json.loads(
            path.read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as erro:
        raise RuntimeError(
            f"Não foi possível ler {path}: {erro}"
        ) from erro


def carregar_pauta() -> dict[str, Any]:
    dados = ler_json(ARQUIVO_PAUTA)

    if isinstance(dados, list):
        dados = dados[0] if dados else None

    if not isinstance(dados, dict):
        raise SystemExit(
            "ERRO: pauta-escolhida.json deve conter "
            "um objeto ou lista com um objeto."
        )

    obrigatorios = ("titulo", "link")

    ausentes = [
        campo
        for campo in obrigatorios
        if not str(dados.get(campo, "")).strip()
    ]

    if ausentes:
        raise SystemExit(
            "ERRO: pauta escolhida sem: "
            + ", ".join(ausentes)
        )

    return dict(dados)


def slugificar(valor: str) -> str:
    normalizado = unicodedata.normalize("NFKD", valor)
    normalizado = normalizado.encode(
        "ascii",
        "ignore",
    ).decode("ascii")
    normalizado = normalizado.lower()
    normalizado = re.sub(r"[^a-z0-9]+", "-", normalizado)
    return normalizado.strip("-")[:100] or "materia"


def baixar_pagina(url: str) -> dict[str, str]:
    if not url.startswith(("http://", "https://")):
        return {
            "titulo": "",
            "descricao": "",
            "imagem": "",
            "texto": "",
        }

    pedido = Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (compatible; "
                "MotorhomeEmPauta/1.0)"
            ),
            "Accept": (
                "text/html,application/xhtml+xml,"
                "application/xml;q=0.9,*/*;q=0.8"
            ),
        },
    )

    try:
        with urlopen(
            pedido,
            timeout=25,
        ) as resposta:
            tipo = resposta.headers.get(
                "Content-Type",
                "",
            ).lower()

            if "html" not in tipo:
                return {
                    "titulo": "",
                    "descricao": "",
                    "imagem": "",
                    "texto": "",
                }

            conteudo = resposta.read(
                1_500_000
            ).decode(
                "utf-8",
                errors="replace",
            )

    except (HTTPError, URLError, TimeoutError) as erro:
        registrar(
            "Aviso: fonte não pôde ser aberta: "
            f"{url} | {type(erro).__name__}"
        )
        return {
            "titulo": "",
            "descricao": "",
            "imagem": "",
            "texto": "",
        }

    leitor = LeitorPagina()
    leitor.feed(conteudo)

    return leitor.resultado()


def fontes_da_pauta(
    pauta: dict[str, Any],
) -> list[dict[str, str]]:
    fontes: list[dict[str, str]] = []

    principal = str(pauta.get("link", "")).strip()

    if principal:
        fontes.append({
            "titulo": str(
                pauta.get("fonte")
                or pauta.get("titulo")
                or "Fonte principal"
            ).strip(),
            "url": principal,
        })

    complementares = pauta.get(
        "fontes_complementares",
        [],
    )

    if isinstance(complementares, list):
        for fonte in complementares:
            if not isinstance(fonte, dict):
                continue

            url = str(
                fonte.get("url")
                or fonte.get("link")
                or ""
            ).strip()

            if not url:
                continue

            fontes.append({
                "titulo": str(
                    fonte.get("titulo")
                    or fonte.get("fonte")
                    or urlparse(url).netloc
                    or "Fonte complementar"
                ).strip(),
                "url": url,
            })

    unicas: list[dict[str, str]] = []
    urls = set()

    for fonte in fontes:
        chave = fonte["url"].rstrip("/").casefold()

        if chave in urls:
            continue

        urls.add(chave)
        unicas.append(fonte)

    return unicas[:5]


def preparar_material(
    pauta: dict[str, Any],
) -> tuple[list[dict[str, str]], str]:
    fontes = fontes_da_pauta(pauta)
    materiais: list[str] = []

    for numero, fonte in enumerate(fontes, 1):
        pagina = baixar_pagina(fonte["url"])

        materiais.append(
            "\n".join([
                f"FONTE {numero}",
                f"Nome: {fonte['titulo']}",
                f"URL: {fonte['url']}",
                f"Título da página: {pagina['titulo']}",
                f"Descrição: {pagina['descricao']}",
                f"Conteúdo disponível: {pagina['texto']}",
            ])
        )

    if not materiais:
        materiais.append(
            "Nenhuma página pôde ser recuperada. "
            "Use somente os dados da pauta."
        )

    return fontes, "\n\n".join(materiais)


def esquema_json() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "titulo": {
                "type": "string",
            },
            "resumo": {
                "type": "string",
            },
            "categoria_sugerida": {
                "type": "string",
            },
            "data": {
                "type": "string",
            },
            "fonte": {
                "type": "string",
            },
            "link": {
                "type": "string",
            },
            "tipo": {
                "type": "string",
            },
            "origem": {
                "type": "string",
            },
            "mercado": {
                "type": "string",
            },
            "corpo": {
                "type": "object",
                "properties": {
                    "abertura": {
                        "type": "string",
                    },
                    "secoes": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "subtitulo": {
                                    "type": "string",
                                },
                                "paragrafos": {
                                    "type": "array",
                                    "items": {
                                        "type": "string",
                                    },
                                    "minItems": 2,
                                },
                            },
                            "required": [
                                "subtitulo",
                                "paragrafos",
                            ],
                            "additionalProperties": False,
                        },
                        "minItems": MIN_SECOES,
                    },
                    "contexto_brasil": {
                        "type": "string",
                    },
                },
                "required": [
                    "abertura",
                    "secoes",
                    "contexto_brasil",
                ],
                "additionalProperties": False,
            },
        },
        "required": [
            "titulo",
            "resumo",
            "categoria_sugerida",
            "data",
            "fonte",
            "link",
            "tipo",
            "origem",
            "mercado",
            "corpo",
        ],
        "additionalProperties": False,
    }


def prompt_sistema() -> str:
    return f"""
Você é jornalista e editor especializado em caravanismo,
motorhomes, trailers, campers, campings e turismo sobre rodas.

Produza uma reportagem original em português brasileiro.

REGRAS OBRIGATÓRIAS:

1. A reportagem deve ter entre {ALVO_MINIMO} e
   {ALVO_MAXIMO} palavras. Nunca entregue menos de
   {MIN_PALAVRAS} palavras.

2. Produza pelo menos {MIN_SECOES} seções com subtítulos
   informativos. Cada seção precisa ter pelo menos
   {MIN_PARAGRAFOS_SECAO} parágrafos completos.

3. O resumo deve ter entre 300 e 500 caracteres.

4. A abertura deve contextualizar o assunto, explicar por
   que a pauta importa e apresentar os fatos principais.

5. Inclua uma seção específica sobre contexto, utilidade,
   disponibilidade ou impacto para o público brasileiro.

6. Preserve exatamente datas, horários, cidades, nomes de
   empresas, modelos, preços, moedas, dimensões e
   especificações encontrados nas fontes.

7. Não invente fatos. Quando uma informação não estiver
   confirmada, diga claramente que a fonte consultada não
   informa aquele dado.

8. Não afirme disponibilidade, representação, homologação
   ou assistência no Brasil sem confirmação nas fontes.

9. Não escreva linguagem publicitária, chamada de vendas,
   exagero ou clickbait.

10. Não copie trechos extensos nem faça tradução literal.
    Organize e explique os fatos com redação própria.

11. Não mencione que o texto foi escrito por inteligência
    artificial.

12. Retorne exclusivamente um objeto JSON correspondente
    à estrutura solicitada.
""".strip()


def prompt_usuario(
    pauta: dict[str, Any],
    material: str,
    tentativa: int,
    erro_anterior: str = "",
) -> str:
    complemento = ""

    if tentativa > 1:
        complemento = f"""
A tentativa anterior foi recusada pelo seguinte motivo:

{erro_anterior}

Produza uma nova versão realmente mais completa. Desenvolva
os parágrafos com fatos, contexto e explicações úteis, sem
repetir frases apenas para aumentar o tamanho.
"""

    dados_pauta = json.dumps(
        pauta,
        ensure_ascii=False,
        indent=2,
    )

    return f"""
PAUTA SELECIONADA:

{dados_pauta}

MATERIAL DAS FONTES:

{material}

{complemento}

Produza a reportagem completa agora.

Atenção:
- entre {ALVO_MINIMO} e {ALVO_MAXIMO} palavras;
- resumo entre 300 e 500 caracteres;
- pelo menos {MIN_SECOES} seções;
- pelo menos dois parágrafos por seção;
- texto factual;
- contexto brasileiro obrigatório;
- saída exclusivamente em JSON.
""".strip()


def extrair_json(texto: str) -> dict[str, Any]:
    conteudo = (texto or "").strip()

    if not conteudo:
        raise ValueError("resposta vazia")

    conteudo = re.sub(
        r"^```(?:json)?\s*",
        "",
        conteudo,
        flags=re.IGNORECASE,
    )
    conteudo = re.sub(
        r"\s*```$",
        "",
        conteudo,
    ).strip()

    try:
        dados = json.loads(conteudo)

        if isinstance(dados, dict):
            return dados
    except json.JSONDecodeError:
        pass

    inicio = conteudo.find("{")
    fim = conteudo.rfind("}")

    if inicio == -1 or fim == -1 or fim <= inicio:
        raise ValueError(
            "objeto JSON não encontrado na resposta"
        )

    trecho = conteudo[inicio: fim + 1]
    dados = json.loads(trecho)

    if not isinstance(dados, dict):
        raise ValueError(
            "a resposta JSON não é um objeto"
        )

    return dados


def chamar_groq(
    client: Groq,
    pauta: dict[str, Any],
    material: str,
    tentativa: int,
    erro_anterior: str,
) -> dict[str, Any]:
    mensagens = [
        {
            "role": "system",
            "content": prompt_sistema(),
        },
        {
            "role": "user",
            "content": prompt_usuario(
                pauta,
                material,
                tentativa,
                erro_anterior,
            ),
        },
    ]

    kwargs: dict[str, Any] = {
        "model": MODELO,
        "messages": mensagens,
        "temperature": 0.25,
        "max_completion_tokens": 8000,
    }

    # GPT-OSS 20B oferece Structured Outputs estrito.
    if MODELO in {
        "openai/gpt-oss-20b",
        "openai/gpt-oss-120b",
    }:
        kwargs["response_format"] = {
            "type": "json_schema",
            "json_schema": {
                "name": "materia_caravanismo",
                "strict": True,
                "schema": esquema_json(),
            },
        }

    try:
        resposta = client.chat.completions.create(
            **kwargs
        )

    except BadRequestError as erro:
        registrar(
            f"Tentativa {tentativa}: Structured Output "
            f"recusado ({erro.code or type(erro).__name__}). "
            "Tentando JSON livre."
        )

        kwargs.pop("response_format", None)

        mensagens[0]["content"] += (
            "\n\nRetorne JSON válido. Não use Markdown, "
            "comentários ou texto fora do objeto JSON."
        )

        kwargs["messages"] = mensagens
        kwargs["temperature"] = 0.15

        resposta = client.chat.completions.create(
            **kwargs
        )

    if not resposta.choices:
        raise ValueError("resposta sem alternativas")

    escolha = resposta.choices[0]
    conteudo = escolha.message.content or ""

    return extrair_json(conteudo)


def contar_palavras(item: dict[str, Any]) -> int:
    corpo = item.get("corpo", {})

    textos = [
        str(item.get("titulo", "")),
        str(item.get("resumo", "")),
        str(corpo.get("abertura", "")),
        str(corpo.get("contexto_brasil", "")),
    ]

    secoes = corpo.get("secoes", [])

    if isinstance(secoes, list):
        for secao in secoes:
            if not isinstance(secao, dict):
                continue

            textos.append(
                str(secao.get("subtitulo", ""))
            )

            paragrafos = secao.get(
                "paragrafos",
                [],
            )

            if isinstance(paragrafos, list):
                textos.extend(
                    str(paragrafo)
                    for paragrafo in paragrafos
                )

    return len(
        re.findall(
            r"\b[\wÀ-ÿ'-]+\b",
            " ".join(textos),
            flags=re.UNICODE,
        )
    )


def validar_estrutura(
    item: dict[str, Any],
) -> listerros: list[str] = []

    titulo = str(item.get("titulo", "")).strip()
    resumo = str(item.get("resumo", "")).strip()
    corpo = item.get("corpo")

    if len(titulo) < 15:
        erros.append("título curto ou ausente")

    if not 300 <= len(resumo) <= 500:
        erros.append(
            "resumo com "
            f"{len(resumo)} caracteres; esperado entre 300 e 500"
        )

    if not isinstance(corpo, dict):
        erros.append("campo corpo ausente ou inválido")
        return erros

    abertura = str(corpo.get("abertura", "")).strip()
    contexto = str(
        corpo.get("contexto_brasil", "")
    ).strip()
    secoes = corpo.get("secoes", [])

    if len(abertura) < 180:
        erros.append("abertura pouco desenvolvida")

    if len(contexto) < 160:
        erros.append(
            "contexto brasileiro pouco desenvolvido"
        )

    if not isinstance(secoes, list):
        erros.append("seções ausentes ou inválidas")
        return erros

    if len(secoes) < MIN_SECOES:
        erros.append(
            f"matéria com {len(secoes)} seções; "
            f"esperado no mínimo {MIN_SECOES}"
        )

    for numero, secao in enumerate(secoes, 1):
        if not isinstance(secao, dict):
            erros.append(
                f"seção {numero} inválida"
            )
            continue

        subtitulo = str(
            secao.get("subtitulo", "")
        ).strip()
        paragrafos = secao.get(
            "paragrafos",
            [],
        )

        if len(subtitulo) < 5:
            erros.append(
                f"seção {numero} sem subtítulo válido"
            )

        if not isinstance(paragrafos, list):
            erros.append(
                f"seção {numero} sem parágrafos"
            )
            continue

        if len(paragrafos) < MIN_PARAGRAFOS_SECAO:
            erros.append(
                f"seção {numero} possui "
                f"{len(paragrafos)} parágrafo(s)"
            )

        for indice, paragrafo in enumerate(
            paragrafos,
            1,
        ):
            if len(str(paragrafo).strip()) < 120:
                erros.append(
                    f"seção {numero}, parágrafo {indice} "
                    "pouco desenvolvido"
                )

    palavras = contar_palavras(item)

    if palavras < MIN_PALAVRAS:
        erros.append(
            f"matéria com {palavras} palavras; "
            f"esperado no mínimo {MIN_PALAVRAS}"
        )

    return erros


def normalizar_item(
    gerado: dict[str, Any],
    pauta: dict[str, Any],
    fontes: list[dict[str, str]],
) -> dict[str, Any]:
    item = dict(gerado)

    item["titulo"] = str(
        item.get("titulo")
        or pauta.get("titulo")
        or ""
    ).strip()

    item["resumo"] = str(
        item.get("resumo")
        or pauta.get("resumo")
        or ""
    ).strip()

    item["categoria_sugerida"] = str(
        item.get("categoria_sugerida")
        or pauta.get("categoria_sugerida")
        or "Últimas notícias"
    ).strip()

    item["data"] = str(
        item.get("data")
        or pauta.get("data")
        or datetime.now().strftime("%d/%m/%Y")
    ).strip()

    item["fonte"] = str(
        pauta.get("fonte")
        or item.get("fonte")
        or urlparse(
            str(pauta.get("link", ""))
        ).netloc
    ).strip()

    item["link"] = str(
        pauta.get("link")
        or item.get("link")
        or ""
    ).strip()

    item["tipo"] = str(
        pauta.get("tipo")
        or item.get("tipo")
        or "Notícia"
    ).strip()

    item["origem"] = str(
        pauta.get("origem")
        or item.get("origem")
        or "Brasil"
    ).strip()

    item["mercado"] = str(
        item.get("mercado")
        or pauta.get("mercado")
        or (
            "Brasil"
            if item["origem"] == "Brasil"
            else "Internacional"
        )
    ).strip()

    item["slug"] = slugificar(item["titulo"])

    item["fontes_complementares"] = fontes

    item["status"] = "aguardando_aprovacao"

    if "pontuacao_selecao" in pauta:
        item["pontuacao_editorial"] = pauta[
            "pontuacao_selecao"
        ]

    item["pauta_original"] = {
        "titulo": pauta.get("titulo", ""),
        "fonte": pauta.get("fonte", ""),
        "link": pauta.get("link", ""),
        "opcao": pauta.get("opcao", ""),
    }

    return item


def gerar_reportagem(
    pauta: dict[str, Any],
    fontes: list[dict[str, str]],
    material: str,
) -> dict[str, Any]:
    chave = os.getenv("GROQ_API_KEY", "").strip()

    if not chave:
        raise SystemExit(
            "ERRO: GROQ_API_KEY não está configurada."
        )

    client = Groq(
        api_key=chave,
        timeout=120.0,
        max_retries=0,
    )

    ultimo_erro = ""

    for tentativa in range(1, MAX_TENTATIVAS + 1):
        registrar(
            f"Tentativa {tentativa} de {MAX_TENTATIVAS}."
        )

        try:
            gerado = chamar_groq(
                client,
                pauta,
                material,
                tentativa,
                ultimo_erro,
            )

            item = normalizar_item(
                gerado,
                pauta,
                fontes,
            )

            erros = validar_estrutura(item)

            if not erros:
                registrar(
                    "Reportagem aprovada na validação interna: "
                    f"{contar_palavras(item)} palavras."
                )
                return item

            ultimo_erro = "; ".join(erros)

            registrar(
                f"Tentativa {tentativa} reprovada: "
                + ultimo_erro
            )

        except (
            BadRequestError,
            APIStatusError,
            json.JSONDecodeError,
            ValueError,
            TypeError,
        ) as erro:
            ultimo_erro = (
                f"{type(erro).__name__}: {str(erro)[:500]}"
            )

            registrar(
                f"Tentativa {tentativa} falhou: "
                + ultimo_erro
            )

        if tentativa < MAX_TENTATIVAS:
            time.sleep(2)

    raise SystemExit(
        "ERRO: não foi possível gerar uma reportagem "
        "completa após "
        f"{MAX_TENTATIVAS} tentativas. "
        f"Último problema: {ultimo_erro}"
    )


def gerar_imagem(
    item: dict[str, Any],
) -> tuple[str | None, str]:
    account_id = os.getenv(
        "CLOUDFLARE_ACCOUNT_ID",
        "",
    ).strip()
    token = os.getenv(
        "CLOUDFLARE_API_TOKEN",
        "",
    ).strip()

    if not account_id or not token:
        return None, "secrets_cloudflare_ausentes"

    prompt = (
        "Fotografia editorial realista e horizontal, "
        "proporção 16:9, relacionada ao caravanismo e "
        "turismo sobre rodas. "
        f"Tema: {item.get('titulo', '')}. "
        f"Contexto: {item.get('resumo', '')}. "
        "Cena natural e plausível, composição completa, "
        "sem texto, sem letras, sem números, sem logotipos, "
        "sem marcas comerciais, sem placas legíveis, "
        "sem pessoas reconhecíveis, no empty space."
    )

    url = (
        "https://api.cloudflare.com/client/v4/accounts/"
        f"{account_id}/ai/run/"
        "@cf/black-forest-labs/flux-1-schnell"
    )

    corpo = json.dumps({
        "prompt": prompt[:1900],
        "steps": 4,
    }).encode("utf-8")

    pedido = Request(
        url,
        data=corpo,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )

    try:
        with urlopen(
            pedido,
            timeout=120,
        ) as resposta:
            dados = json.loads(
                resposta.read().decode("utf-8")
            )

        resultado = dados.get("result", {})
        imagem_b64 = resultado.get("image")

        if not imagem_b64:
            raise ValueError(
                "Cloudflare não retornou o campo image"
            )

        conteudo = base64.b64decode(
            imagem_b64
        )

        PASTA_IMAGENS.mkdir(
            parents=True,
            exist_ok=True,
        )

        caminho = (
            PASTA_IMAGENS
            / f"{item['slug']}.jpg"
        )

        caminho.write_bytes(conteudo)

        return caminho.as_posix(), "gerada_por_ia"

    except (
        HTTPError,
        URLError,
        TimeoutError,
        ValueError,
        json.JSONDecodeError,
    ) as erro:
        registrar(
            "Aviso: geração de imagem falhou: "
            f"{type(erro).__name__}"
        )
        return None, f"cloudflare_{type(erro).__name__}"


def aplicar_imagem(
    item: dict[str, Any],
) -> None:
    caminho, origem = gerar_imagem(item)

    if caminho:
        item["imagem"] = caminho
        item["imagem_alt"] = (
            "Imagem ilustrativa relacionada à matéria: "
            + item["titulo"]
        )
        item["imagem_legenda"] = (
            "Imagem ilustrativa gerada por "
            "inteligência artificial"
        )
        item["imagem_credito"] = (
            "Cloudflare Workers AI · FLUX.1 Schnell"
        )
        item["credito_imagem"] = item[
            "imagem_credito"
        ]
        item["imagem_origem"] = origem
        item["fonte_imagem"] = (
            "Cloudflare Workers AI"
        )
        return

    categoria = item.get(
        "categoria_sugerida",
        "Últimas notícias",
    )

    fallback = IMAGENS_PADRAO.get(
        categoria,
        IMAGENS_PADRAO["Últimas notícias"],
    )

    item["imagem"] = fallback
    item["imagem_alt"] = (
        f"Imagem ilustrativa da categoria {categoria}"
    )
    item["imagem_legenda"] = "Imagem ilustrativa"
    item["imagem_credito"] = (
        "Acervo visual do Motorhome em Pauta"
    )
    item["credito_imagem"] = item[
        "imagem_credito"
    ]
    item["imagem_origem"] = "padrao_categoria"
    item["fonte_imagem"] = fallback

    registrar(
        "Imagem padrão aplicada: "
        f"{fallback} | motivo: {origem}"
    )


def atualizar_noticias(
    item: dict[str, Any],
) -> None:
    atuais = ler_json(
        ARQUIVO_NOTICIAS,
        [],
    )

    if not isinstance(atuais, list):
        atuais = []

    link = item["link"].rstrip("/").casefold()
    slug = item["slug"].casefold()

    filtradas = []

    for existente in atuais:
        if not isinstance(existente, dict):
            continue

        link_existente = str(
            existente.get("link", "")
        ).rstrip("/").casefold()

        slug_existente = str(
            existente.get("slug", "")
        ).casefold()

        if link_existente == link:
            continue

        if slug_existente and slug_existente == slug:
            continue

        filtradas.append(existente)

    ARQUIVO_NOTICIAS.write_text(
        json.dumps(
            [item] + filtradas,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def escrever_resumo(
    item: dict[str, Any],
) -> None:
    corpo = item.get("corpo", {})
    secoes = corpo.get("secoes", [])
    palavras = contar_palavras(item)

    fontes = item.get(
        "fontes_complementares",
        [],
    )

    linhas = [
        "# Reportagem completa aguardando aprovação",
        "",
        "## Publicação",
        "",
        f"- **Título:** {item['titulo']}",
        (
            "- **Categoria:** "
            f"{item['categoria_sugerida']}"
        ),
        f"- **Data da fonte:** {item['data']}",
        f"- **Fonte principal:** {item['fonte']}",
        f"- **Origem:** {item['origem']}",
        f"- **Tipo:** {item['tipo']}",
        f"- **Palavras:** {palavras}",
        f"- **Seções:** {len(secoes)}",
        f"- **Imagem:** {item['imagem']}",
        (
            "- **Origem da imagem:** "
            f"{item['imagem_origem']}"
        ),
        f"- **Link original:** {item['link']}",
        "",
        "## Resumo",
        "",
        item["resumo"],
        "",
        "## Fontes",
        "",
    ]

    for fonte in fontes:
        linhas.append(
            f"- [{fonte['titulo']}]({fonte['url'inhas.extend([
        "",
        "## Revisão",
        "",
        (
            "Revise a reportagem e a imagem na aba "
            "**Files changed**."
        ),
        "",
        (
            "Para pedir alterações, comente no Pull Request:"
        ),
        "",
        "```text",
        (
            "/refazer Desenvolva melhor o tema e use "
            "somente informações confirmadas."
        ),
        "```",
        "",
        (
            "Para publicar, faça o merge somente depois "
            "que todos os checks estiverem verdes."
        ),
    ])

    ARQUIVO_RESUMO.write_text(
        "\n".join(linhas) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    pauta = carregar_pauta()

    registrar(
        "Pauta recebida: "
        + str(pauta.get("titulo", ""))
    )

    fontes, material = preparar_material(pauta)

    if not fontes:
        raise SystemExit(
            "ERRO: nenhuma fonte válida foi encontrada."
        )

    item = gerar_reportagem(
        pauta,
        fontes,
        material,
    )

    aplicar_imagem(item)

    erros = validar_estrutura(item)

    if erros:
        raise SystemExit(
            "ERRO: matéria inválida depois da imagem: "
            + "; ".join(erros)
        )

    atualizar_noticias(item)
    escrever_resumo(item)

    ARQUIVO_RELATORIO.write_text(
        "\n".join(LOG) + "\n",
        encoding="utf-8",
    )

    registrar(
        "Reportagem completa preparada: "
        f"{item['titulo']} | "
        f"{contar_palavras(item)} palavras | "
        f"{len(item['corpo']['secoes'])} seções."
    )


if __name__ == "__main__":
    try:
        main()
    finally:
        if LOG:
            ARQUIVO_RELATORIO.write_text(
                "\n".join(LOG) + "\n",
                encoding="utf-8",
            )
