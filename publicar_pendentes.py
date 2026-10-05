"""Publica no noticias.json apenas itens previamente validados pelo workflow.

O script nao acessa a internet e nao usa IA. Ele apenas move itens de
pendentes-conferencia.json para noticias.json, aplicando validacoes de
estrutura, categoria, data, URL, duplicidade e tamanho editorial.
"""
import json
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

ARQUIVO_NOTICIAS = Path("noticias.json")
ARQUIVO_PENDENTES = Path("pendentes-conferencia.json")
ARQUIVO_RELATORIO = Path("resultado-publicacao.txt")
FUSO = ZoneInfo("America/Sao_Paulo")

CATEGORIAS_PERMITIDAS = {
    "Últimas notícias",
    "Eventos e feiras",
    "Histórias e comunidade",
    "Guias e vida a bordo",
    "Novidades internacionais",
}

CAMPOS_OBRIGATORIOS = (
    "titulo",
    "categoria_sugerida",
    "data",
    "resumo",
    "fonte",
    "link",
)

CAMPOS_OPCIONAIS = {
    "origem",
    "destaque",
    "mercado",
    "tipo_veiculo",
    "marca",
    "modelo",
    "uf",
    "selo",
    "imagem",
    "imagem_alt",
    "imagem_legenda",
    "imagem_credito",
    "slug",
    "corpo",
}


def carregar_lista(caminho, nome):
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    if not isinstance(dados, list):
        raise ValueError(f"{nome} deve conter uma lista.")
    return dados


def texto_obrigatorio(item, campo):
    valor = item.get(campo)
    if not isinstance(valor, str) or not valor.strip():
        raise ValueError(f"campo ausente ou vazio: {campo}")
    return valor.strip()


def validar_data(valor):
    data = datetime.strptime(valor, "%d/%m/%Y").date()
    hoje = datetime.now(FUSO).date()
    if data > hoje:
        raise ValueError("data futura")
    return data


def validar_link(valor):
    partes = urlparse(valor)
    if partes.scheme != "https" or not partes.netloc:
        raise ValueError("link deve usar HTTPS")
    return valor


def limpar_item(item):
    if not isinstance(item, dict):
        raise ValueError("item nao e um objeto JSON")

    limpo = {}
    for campo in CAMPOS_OBRIGATORIOS:
        limpo[campo] = texto_obrigatorio(item, campo)

    if limpo["categoria_sugerida"] not in CATEGORIAS_PERMITIDAS:
        raise ValueError("categoria nao permitida")

    validar_data(limpo["data"])
    validar_link(limpo["link"])

    if len(limpo["titulo"]) < 15 or len(limpo["titulo"]) > 180:
        raise ValueError("titulo fora do tamanho permitido")
    if len(limpo["resumo"]) < 50 or len(limpo["resumo"]) > 500:
        raise ValueError("resumo fora do tamanho permitido")

    if item.get("revisar_lancamento"):
        raise ValueError("lancamento ainda requer revisao")

    for campo in CAMPOS_OPCIONAIS:
        if campo not in item:
            continue
        valor = item[campo]
        if valor in (None, "", [], {}):
            continue
        limpo[campo] = valor.strip() if isinstance(valor, str) else valor

    return limpo


def chave(item):
    return item["link"].strip().rstrip("/").casefold()


def main():
    linhas = []

    if not ARQUIVO_PENDENTES.exists():
        linhas.append("Nenhum arquivo pendentes-conferencia.json encontrado.")
        linhas.append("Nenhuma publicacao realizada.")
        ARQUIVO_RELATORIO.write_text("\n".join(linhas) + "\n", encoding="utf-8")
        print("\n".join(linhas))
        return

    publicados = carregar_lista(ARQUIVO_NOTICIAS, "noticias.json")
    pendentes = carregar_lista(ARQUIVO_PENDENTES, "pendentes-conferencia.json")

    existentes = {
        chave(item)
        for item in publicados
        if isinstance(item, dict) and isinstance(item.get("link"), str)
    }

    aprovados = []
    rejeitados = 0
    duplicados = 0

    for numero, bruto in enumerate(pendentes, start=1):
        try:
            item = limpar_item(bruto)
        except Exception as erro:
            rejeitados += 1
            titulo = bruto.get("titulo", "sem titulo") if isinstance(bruto, dict) else "item invalido"
            linhas.append(f"REJEITADO | {titulo} | {type(erro).__name__}: {erro}")
            continue

        identificador = chave(item)
        if identificador in existentes:
            duplicados += 1
            linhas.append(f"DUPLICADO | {item['titulo']}")
            continue

        existentes.add(identificador)
        aprovados.append(item)
        linhas.append(f"PUBLICAR | {item['categoria_sugerida']} | {item['titulo']}")

    if aprovados:
        # Itens novos no inicio; o site também ordena pela data.
        ARQUIVO_NOTICIAS.write_text(
            json.dumps(aprovados + publicados, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    linhas.extend([
        "---",
        f"Pendentes recebidos: {len(pendentes)}",
        f"Publicados: {len(aprovados)}",
        f"Duplicados: {duplicados}",
        f"Rejeitados: {rejeitados}",
        "noticias.json atualizado." if aprovados else "noticias.json nao foi alterado.",
    ])

    ARQUIVO_RELATORIO.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    print("\n".join(linhas))


if __name__ == "__main__":
    main()
