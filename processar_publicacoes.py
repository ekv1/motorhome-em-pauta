"""Seleciona um único item, aplica critérios editoriais e gera imagem."""
import base64
import hashlib
import json
import os
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

FUSO = ZoneInfo("America/Sao_Paulo")
PUBLICADOS = Path("noticias.json")
SAIDA = Path("pendentes-conferencia.json")
RELATORIO = Path("resultado-processamento.txt")
PASTA_IMAGENS = Path("imagens/noticias")
MODELO_IMAGEM = "@cf/black-forest-labs/flux-1-schnell"
LIMITE_PUBLICACOES = 1
CANDIDATOS = (
    Path("rascunhos-coletor.json"),
    Path("rascunhos-internacionais.json"),
    Path("internacionais-rascunhos.json"),
    Path("rascunhos-internacional.json"),
)

FALLBACKS = {
    "Últimas notícias": "imagens/capa-estrada.png",
    "Eventos e feiras": "imagens/padrao-comunidade.png",
    "Histórias e comunidade": "imagens/padrao-comunidade.png",
    "Guias e vida a bordo": "imagens/guia-organizar.png",
    "Novidades internacionais": "imagens/ilustrativa-veiculos.png",
}

DIRETOS = (
    "motorhome", "motor home", "trailer", "camper", "campervan",
    "vanhome", "van home", "caravanismo", "caravan", "rv ",
    "recreational vehicle", "fifth wheel", "travel trailer",
)
EQUIPAMENTOS = (
    "bateria", "energia solar", "inversor", "gerador", "suspensão",
    "suspensao", "freio", "pneu", "acessório", "acessorio",
    "equipamento", "refrigeração", "refrigeracao", "aquecimento",
    "ar-condicionado", "camping", "ponto de apoio", "campground",
)
UTILIDADE = (
    "segurança", "seguranca", "manutenção", "manutencao", "legislação",
    "legislacao", "recall", "guia", "como", "custo", "preço", "preco",
    "viagem", "rota", "camping", "evento", "feira", "lançamento",
    "lancamento", "novo modelo", "apresenta", "estreia",
)
APOIO = (
    "evento", "feira", "expo", "encontro", "guia", "manutenção",
    "manutencao", "segurança", "seguranca", "equipamento", "acessório",
    "acessorio", "destino", "camping", "ponto de apoio",
)
VALOR_ALTO = (
    "lança", "lanca", "lançamento", "lancamento", "novo modelo",
    "nova geração", "nova geracao", "recall", "segurança", "seguranca",
    "regulamentação", "regulamentacao", "tecnologia", "bateria",
)
AQUISICOES = (
    "compra ativos", "adquire ativos", "aquisição", "aquisicao",
    "fusão", "fusao", "compra empresa", "compra a empresa",
)
IMPACTO_CONSUMIDOR = (
    "produção", "producao", "modelo", "linha de produtos", "garantia",
    "assistência", "assistencia", "disponibilidade", "preço", "preco",
    "segurança", "seguranca", "manutenção", "manutencao", "continuidade",
    "revenda", "peças", "pecas", "atendimento", "proprietário",
    "proprietario", "comprador", "consumidor", "entrega",
)
CORPORATIVOS = (
    "executivo", "executiva", "nomeia", "nomeação", "nomeacao",
    "premiação", "premiacao", "prêmio anual", "premio anual",
    "liderança", "lideranca", "concessionário", "concessionario",
    "revendedor", "open house", "resultado financeiro", "receita trimestral",
    "estoque do revendedor", "inventário do revendedor", "dealer inventory",
    "nomeia presidente", "finalistas", "prêmios anuais", "premios anuais",
)

LOG = []
def registrar(texto=""):
    print(texto)
    LOG.append(str(texto))

def norm(valor):
    if not isinstance(valor, str):
        return ""
    valor = unicodedata.normalize("NFKD", valor)
    valor = "".join(c for c in valor if not unicodedata.combining(c))
    return " ".join(valor.casefold().split())

def contem(texto, termos):
    return any(norm(t) in texto for t in termos if norm(t))

def ler_lista(path):
    if not path.exists():
        return []
    try:
        dados = json.loads(path.read_text(encoding="utf-8"))
        return dados if isinstance(dados, list) else []
    except (OSError, json.JSONDecodeError) as erro:
        registrar(f"IGNORADO: {path} inválido ({type(erro).__name__})")
        return []

def texto_item(item):
    partes = [item.get("titulo", ""), item.get("resumo", ""), item.get("fonte", "")]
    corpo = item.get("corpo")
    if isinstance(corpo, dict):
        partes += [corpo.get("abertura", ""), corpo.get("contexto_brasil", "")]
        for secao in corpo.get("secoes", []) or []:
            if isinstance(secao, dict):
                partes.append(secao.get("subtitulo", ""))
                partes.extend(secao.get("paragrafos", []) or [])
    return norm(" ".join(str(p) for p in partes if p))

def link_normalizado(link):
    return str(link or "").strip().rstrip("/").casefold()

def carregar_candidatos():
    itens, vistos = [], set()
    for arquivo in CANDIDATOS:
        for item in ler_lista(arquivo):
            if not isinstance(item, dict):
                continue
            chave = link_normalizado(item.get("link")) or norm(item.get("titulo", ""))
            if not chave or chave in vistos:
                continue
            vistos.add(chave)
            itens.append(dict(item))
    return itens

def links_publicados():
    return {
        link_normalizado(i.get("link")) for i in ler_lista(PUBLICADOS)
        if isinstance(i, dict) and i.get("link")
    }

def parse_data(valor):
    for formato in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(valor).strip(), formato).date()
        except ValueError:
            pass
    return None

def idade(item):
    data = parse_data(item.get("data"))
    return (datetime.now(FUSO).date() - data).days if data else 999

def secoes_validas(item):
    corpo = item.get("corpo")
    if not isinstance(corpo, dict):
        return 0
    return sum(
        1 for s in corpo.get("secoes", []) or []
        if isinstance(s, dict) and str(s.get("subtitulo", "")).strip()
        and any(str(p).strip() for p in s.get("paragrafos", []) or [])
    )

def contar_fatos(item):
    texto = texto_item(item)
    numeros = len(set(re.findall(r"\b\d+(?:[.,]\d+)?\b", texto)))
    corpo = item.get("corpo")
    paragrafos = 0
    if isinstance(corpo, dict):
        paragrafos = sum(
            len([p for p in s.get("paragrafos", []) or [] if str(p).strip()])
            for s in corpo.get("secoes", []) or [] if isinstance(s, dict)
        )
    campos = sum(bool(str(item.get(c, "")).strip()) for c in ("titulo", "resumo", "fonte", "link"))
    return min(10, numeros + secoes_validas(item) + min(paragrafos, 4) + max(0, campos - 2))

def elegibilidade(item, publicados):
    titulo = str(item.get("titulo", "")).strip()
    link = str(item.get("link", "")).strip()
    texto = texto_item(item)
    if len(titulo) < 8:
        return False, "título ausente ou muito curto"
    if not link.startswith("https://"):
        return False, "link ausente ou sem HTTPS"
    if link_normalizado(link) in publicados:
        return False, "duplicado"
    if item.get("irrelevante") is True:
        return False, "marcado como irrelevante"
    direto = contem(texto, DIRETOS)
    relacionado = direto or contem(texto, EQUIPAMENTOS) or contem(texto, APOIO)
    if not relacionado:
        return False, "sem relação clara com caravanismo"
    aquisicao = contem(texto, AQUISICOES)
    impacto = contem(texto, IMPACTO_CONSUMIDOR)
    corporativo = contem(texto, CORPORATIVOS)
    if aquisicao and not impacto:
        return False, "aquisição sem impacto concreto para produto ou consumidor"
    if corporativo and not aquisicao:
        return False, "conteúdo predominantemente corporativo"
    if len(str(item.get("resumo", "")).strip()) < 30 and contar_fatos(item) < 3:
        return False, "informações insuficientes"
    return True, "elegível"

def pontuar(item, ultima_categoria):
    texto, detalhes = texto_item(item), []
    relacao = 30 if contem(texto, DIRETOS) else 24 if contem(texto, EQUIPAMENTOS) else 18
    detalhes.append(f"relação direta {relacao}/30")
    pratica = ("segurança", "seguranca", "manutenção", "manutencao", "compra", "custo", "preço", "preco", "viagem", "recall", "legislação", "legislacao")
    novidade = ("lançamento", "lancamento", "novo modelo", "equipamento", "evento", "feira", "camping", "destino")
    utilidade = 20 if contem(texto, pratica) else 15 if contem(texto, novidade) else 10
    detalhes.append(f"utilidade {utilidade}/20")
    fatos = contar_fatos(item)
    qualidade = 15 if fatos >= 7 else 10 if fatos >= 4 else 5
    detalhes.append(f"qualidade dos fatos {qualidade}/15")
    dias = idade(item)
    if item.get("categoria_sugerida") in {"Eventos e feiras", "Guias e vida a bordo"} and dias >= 0:
        atualidade = 12
    elif 0 <= dias <= 3: atualidade = 15
    elif dias <= 7: atualidade = 12
    elif dias <= 15: atualidade = 9
    elif dias <= 30: atualidade = 6
    elif dias <= 45: atualidade = 3
    else: atualidade = 0
    detalhes.append(f"atualidade {atualidade}/15")
    valor = 10 if contem(texto, VALOR_ALTO) else 8 if contem(texto, APOIO) else 2 if contem(texto, CORPORATIVOS) else 5
    detalhes.append(f"valor editorial {valor}/10")
    rastreabilidade = 5 if item.get("fonte") and str(item.get("link", "")).startswith("https://") else 3
    detalhes.append(f"fonte e rastreabilidade {rastreabilidade}/5")
    diversidade = 5 if item.get("categoria_sugerida") != ultima_categoria else 3
    detalhes.append(f"diversidade {diversidade}/5")
    aquisicao, impacto, corporativo = contem(texto, AQUISICOES), contem(texto, IMPACTO_CONSUMIDOR), contem(texto, CORPORATIVOS)
    penalidade = 0
    if aquisicao and impacto:
        penalidade = -5; detalhes.append("penalidade aquisição com impacto -5")
    elif aquisicao:
        penalidade = -20; detalhes.append("penalidade aquisição sem impacto -20")
    elif corporativo:
        penalidade = -15; detalhes.append("penalidade corporativa -15")
    if fatos < 3:
        penalidade -= 10; detalhes.append("penalidade por poucos fatos -10")
    bonus = 0
    if item.get("destaque") == "lancamento" and item.get("mercado") == "Brasil":
        bonus += 10; detalhes.append("bônus lançamento nacional +10")
    elif item.get("destaque") == "lancamento":
        bonus += 8; detalhes.append("bônus novo veículo +8")
    if item.get("categoria_sugerida") == "Eventos e feiras":
        bonus += 6; detalhes.append("bônus evento +6")
    total = max(0, min(100, relacao + utilidade + qualidade + atualidade + valor + rastreabilidade + diversidade + penalidade + bonus))
    return total, detalhes

def verificacao_reforcada(item):
    texto = texto_item(item)
    corpo = item.get("corpo") if isinstance(item.get("corpo"), dict) else {}
    aquisicao, impacto, corporativo = contem(texto, AQUISICOES), contem(texto, IMPACTO_CONSUMIDOR), contem(texto, CORPORATIVOS)
    if aquisicao and not impacto:
        return False
    if corporativo and not aquisicao:
        return False
    return (
        contem(texto, DIRETOS + EQUIPAMENTOS + APOIO)
        and contar_fatos(item) >= 3
        and secoes_validas(item) >= 2
        and (contem(texto, UTILIDADE) or impacto or bool(str(corpo.get("contexto_brasil", "")).strip()))
    )

def conteudo_apoio(item):
    return contem(texto_item(item), APOIO) and contar_fatos(item) >= 4

def slugificar(texto):
    base = re.sub(r"[^a-z0-9]+", "-", norm(texto)).strip("-")[:80]
    return f"{base or 'noticia'}-{hashlib.sha256(str(texto).encode()).hexdigest()[:8]}"

def gerar_imagem(item):
    conta = os.getenv("CLOUDFLARE_ACCOUNT_ID", "").strip()
    token = os.getenv("CLOUDFLARE_API_TOKEN", "").strip()
    if not conta or not token:
        return None, "secrets ausentes"
    prompt = (
        "Fotografia editorial realista e horizontal para portal de caravanismo. "
        f"Tema: {item.get('titulo', '')}. Contexto: {item.get('resumo', '')}. "
        "Mostrar somente elementos relacionados ao assunto. Sem texto, números, logotipos, "
        "marcas, placas legíveis ou pessoas reconhecíveis."
    )[:2048]
    url = f"https://api.cloudflare.com/client/v4/accounts/{conta}/ai/run/{MODELO_IMAGEM}"
    req = Request(url, data=json.dumps({"prompt": prompt, "steps": 4}).encode(), method="POST", headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    try:
        with urlopen(req, timeout=90) as resposta:
            dados = json.loads(resposta.read().decode())
        imagem = dados.get("result", {}).get("image")
        if not imagem:
            return None, "Cloudflare sem imagem na resposta"
        binario = base64.b64decode(imagem)
        ext = ".png" if binario.startswith(b"\x89PNG") else ".jpg"
        caminho = PASTA_IMAGENS / f"{item.get('slug') or slugificar(item.get('titulo'))}{ext}"
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_bytes(binario)
        return str(caminho).replace("\\", "/"), "gerada_por_ia"
    except HTTPError as erro:
        return None, f"Cloudflare HTTP {erro.code}: {erro.read().decode(errors='replace')[:400]}"
    except (URLError, TimeoutError, json.JSONDecodeError, ValueError) as erro:
        return None, f"Cloudflare {type(erro).__name__}"

def aplicar_imagem(item):
    caminho, origem = gerar_imagem(item)
    if caminho:
        item.update({"imagem": caminho, "imagem_alt": f"Imagem ilustrativa relacionada à matéria: {item.get('titulo')}", "imagem_legenda": "Imagem gerada por inteligência artificial", "imagem_credito": "Cloudflare Workers AI · FLUX.1 Schnell", "imagem_origem": origem})
        return origem
    categoria = item.get("categoria_sugerida", "Últimas notícias")
    item.update({"imagem": FALLBACKS.get(categoria, FALLBACKS["Últimas notícias"]), "imagem_alt": f"Imagem ilustrativa da categoria {categoria}", "imagem_legenda": "Imagem ilustrativa", "imagem_credito": "Acervo visual do Motorhome em Pauta", "imagem_origem": "padrao_categoria"})
    return origem

def main():
    SAIDA.unlink(missing_ok=True)
    candidatos, publicados = carregar_candidatos(), links_publicados()
    ultima = next((i.get("categoria_sugerida") for i in ler_lista(PUBLICADOS) if isinstance(i, dict) and i.get("categoria_sugerida")), None)
    registrar("RANKING DOS CANDIDATOS:")
    avaliados = []
    for item in candidatos:
        ok, motivo = elegibilidade(item, publicados)
        if not ok:
            registrar(f"IGNORADO | {item.get('titulo', 'sem título')} | {motivo}")
            continue
        item = dict(item)
        item["pontuacao_editorial"], item["criterios_selecao"] = pontuar(item, ultima)
        avaliados.append(item)
    avaliados.sort(key=lambda i: (i["pontuacao_editorial"], -idade(i)), reverse=True)
    for n, item in enumerate(avaliados, 1):
        registrar(f"{n}. {item.get('titulo')} | {item['pontuacao_editorial']}/100")
    escolhido, decisao = None, ""
    for item in avaliados:
        nota = item["pontuacao_editorial"]
        if nota >= 65:
            escolhido, decisao = item, "aprovação automática"; break
        if 50 <= nota <= 64 and verificacao_reforcada(item):
            escolhido, decisao = item, "aprovado por verificação reforçada"; break
        if 40 <= nota <= 49 and conteudo_apoio(item):
            escolhido, decisao = item, "aprovado como conteúdo útil"; break
    if not escolhido:
        registrar("SELECIONADO: nenhum candidato atingiu os critérios equilibrados")
        registrar("Aprovados: 0")
        registrar(f"Limite por execução: {LIMITE_PUBLICACOES}")
    else:
        escolhido.setdefault("slug", slugificar(escolhido.get("titulo", "noticia")))
        origem = aplicar_imagem(escolhido)
        escolhido["decisao_editorial"] = decisao
        SAIDA.write_text(json.dumps([escolhido], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        registrar(f"SELECIONADO: {escolhido.get('titulo')} | {escolhido['pontuacao_editorial']}/100 | {decisao} | {origem}")
        registrar("Aprovados: 1")
        registrar(f"Limite por execução: {LIMITE_PUBLICACOES}")
    RELATORIO.write_text("\n".join(LOG) + "\n", encoding="utf-8")

if __name__ == "__main__":
    main()
