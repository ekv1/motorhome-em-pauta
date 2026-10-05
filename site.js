// Motorhome em Pauta - conteúdo carregado de noticias.json
// O coletor automático só precisa acrescentar itens nesse arquivo.

const SECOES = [
  ["Notícias", "index.html#ultimas"],
  ["Internacionais", "index.html#internacionais"],
  ["Guias", "index.html#guias"],
  ["Comunidade", "index.html#comunidade"]
];

const IMAGEM_PADRAO = {
  "Últimas notícias": "imagens/capa-estrada.png",
  "Novidades internacionais": "imagens/ilustrativa-veiculos.png",
  "Guias e vida a bordo": "imagens/guia-organizar.png",
  "Histórias e comunidade": "imagens/padrao-comunidade.png"
};

const ROTULO = {
  "Últimas notícias": "Brasil",
  "Novidades internacionais": "Internacional",
  "Guias e vida a bordo": "Guia",
  "Histórias e comunidade": "Comunidade"
};

const MAXIMO_POR_SECAO = 6;

function criarLink(texto, destino, classe, externo) {
  const a = document.createElement("a");
  a.textContent = texto;
  a.href = destino;
  if (classe) a.className = classe;
  if (externo) { a.target = "_blank"; a.rel = "noopener noreferrer"; }
  return a;
}

function montarMenus() {
  const menu = document.getElementById("menu");
  const rodape = document.getElementById("menu-rodape");
  // Na página inicial usa só a âncora; nas matérias volta ao início.
  const naInicial = document.querySelector(".grade[data-categoria]") !== null;
  SECOES.forEach(([nome, destino]) => {
    const link = naInicial ? destino.replace("index.html", "") : destino;
    if (menu) menu.appendChild(criarLink(nome, link));
    if (rodape) rodape.appendChild(criarLink(nome, link));
  });
  if (menu) menu.appendChild(criarLink("Viver é estrada", naInicial ? "#ultimas" : "index.html#ultimas", "botao"));
  const capa = document.getElementById("capa-acao");
  if (capa) capa.appendChild(criarLink("Ver últimas notícias →", "#ultimas", "botao-capa"));
}

function texto(v) { return typeof v === "string" && v.trim().length > 0; }

function linkSeguro(v) {
  try {
    const u = new URL(v, window.location.href);
    if (u.origin === window.location.origin || u.protocol === "https:") return u.href;
  } catch (e) {}
  return null;
}

function paraData(d) {
  const m = /^(\d{2})\/(\d{2})\/(\d{4})$/.exec(d || "");
  return m ? new Date(+m[3], +m[2] - 1, +m[1]).getTime() : 0;
}

function destinoDoItem(item) {
  // Matéria completa no site quando houver corpo; senão, a fonte original.
  if (texto(item.slug) && item.corpo) return { url: "materia.html?id=" + encodeURIComponent(item.slug), externo: false };
  const fonte = linkSeguro(item.link);
  return fonte ? { url: fonte, externo: true } : null;
}

function cartao(item) {
  if (!texto(item.titulo) || !texto(item.data)) return null;
  const destino = destinoDoItem(item);
  if (!destino) return null;
  const categoria = item.categoria_sugerida || "Últimas notícias";

  const a = criarLink("", destino.url, "cartao", destino.externo);

  const foto = document.createElement("div");
  foto.className = "foto";
  const imagem = linkSeguro(item.imagem || IMAGEM_PADRAO[categoria] || "");
  if (imagem) foto.style.backgroundImage = 'url("' + imagem + '")';
  foto.setAttribute("role", "img");
  foto.setAttribute("aria-label", item.imagem_alt || item.titulo);

  const selo = document.createElement("span");
  selo.className = "selo";
  selo.textContent = item.selo || ROTULO[categoria] || "Notícia";
  foto.appendChild(selo);

  if (item.imagem_legenda === "Imagem ilustrativa" || !item.imagem) {
    const ilu = document.createElement("span");
    ilu.className = "ilustrativa";
    ilu.textContent = "Imagem ilustrativa";
    foto.appendChild(ilu);
  }

  const conteudo = document.createElement("div");
  conteudo.className = "conteudo";
  const h3 = document.createElement("h3");
  h3.textContent = item.titulo;
  const p = document.createElement("p");
  p.textContent = item.resumo || "";
  const base = document.createElement("div");
  base.className = "rodape-cartao";
  const info = document.createElement("span");
  info.textContent = item.data + (texto(item.fonte) ? " · " + item.fonte : "");
  const seta = document.createElement("span");
  seta.className = "seta";
  seta.textContent = destino.externo ? "↗" : "→";
  base.append(info, seta);
  conteudo.append(h3, p, base);

  a.append(foto, conteudo);
  return a;
}

async function carregarNoticias() {
  const resposta = await fetch("noticias.json", { cache: "no-store" });
  if (!resposta.ok) throw new Error("noticias.json indisponível");
  const dados = await resposta.json();
  if (!Array.isArray(dados)) throw new Error("formato inválido");
  return dados.filter(i => i && typeof i === "object");
}

function irParaAncora() {
  if (!window.location.hash) return;
  const alvo = document.getElementById(window.location.hash.slice(1));
  if (alvo) alvo.scrollIntoView();
}

async function montarInicio() {
  const grades = document.querySelectorAll(".grade[data-categoria]");
  if (!grades.length) return;
  try {
    const itens = (await carregarNoticias()).sort((a, b) => paraData(b.data) - paraData(a.data));
    grades.forEach(grade => {
      const cat = grade.dataset.categoria;
      const cartoes = itens
        .filter(i => (i.categoria_sugerida || "Últimas notícias") === cat)
        .slice(0, MAXIMO_POR_SECAO)
        .map(cartao)
        .filter(Boolean);
      if (cartoes.length) grade.replaceChildren(...cartoes);
      else {
        const v = document.createElement("div");
        v.className = "vazio";
        v.textContent = "Em breve, novas publicações nesta seção.";
        grade.replaceChildren(v);
      }
    });
  } catch (e) {
    console.error(e);
    grades.forEach(g => { g.textContent = "Não foi possível carregar o conteúdo agora."; });
  }
  // Rola só depois que os cartões aumentaram a altura das seções.
  irParaAncora();
}

async function montarMateria() {
  const alvo = document.getElementById("materia");
  if (!alvo) return;
  const id = new URLSearchParams(window.location.search).get("id");
  try {
    const item = (await carregarNoticias()).find(i => i.slug === id && i.corpo);
    if (!item) throw new Error("matéria não encontrada");
    const categoria = item.categoria_sugerida || "Últimas notícias";
    document.title = item.titulo + " | Motorhome em Pauta";

    const capa = document.createElement("div");
    capa.className = "materia-capa";
    const img = linkSeguro(item.imagem || IMAGEM_PADRAO[categoria] || "");
    if (img) capa.style.backgroundImage = 'url("' + img + '")';
    capa.setAttribute("role", "img");
    capa.setAttribute("aria-label", item.imagem_alt || item.titulo);

    const legenda = document.createElement("p");
    legenda.className = "legenda";
    legenda.textContent = item.imagem_credito ||
      "Imagem ilustrativa criada para o Motorhome em Pauta; não representa o produto ou local citado.";

    const corpo = document.createElement("div");
    corpo.className = "materia-corpo";
    const meta = document.createElement("p");
    meta.className = "meta";
    meta.textContent = (ROTULO[categoria] || "Notícia") + " · " + item.data;
    const h1 = document.createElement("h1");
    h1.textContent = item.titulo;
    const ab = document.createElement("p");
    ab.className = "abertura";
    ab.textContent = item.corpo.abertura || item.resumo || "";
    corpo.append(meta, h1, ab);

    (item.corpo.secoes || []).forEach(s => {
      const h2 = document.createElement("h2");
      h2.textContent = s.subtitulo;
      corpo.appendChild(h2);
      (s.paragrafos || []).forEach(t => {
        const p = document.createElement("p");
        p.textContent = t;
        corpo.appendChild(p);
      });
    });

    if (texto(item.corpo.contexto_brasil)) {
      const h2 = document.createElement("h2");
      h2.textContent = "O que sabemos sobre o Brasil";
      const p = document.createElement("p");
      p.textContent = item.corpo.contexto_brasil;
      corpo.append(h2, p);
    }

    const fonte = document.createElement("p");
    fonte.className = "fonte";
    const linkFonte = linkSeguro(item.link);
    if (linkFonte) {
      fonte.append("Fonte: " + (item.fonte || "publicação original") + " · ");
      fonte.appendChild(criarLink("ler publicação original", linkFonte, "", true));
    } else {
      fonte.textContent = "Conteúdo original Motorhome em Pauta.";
    }
    const voltar = document.createElement("p");
    voltar.className = "voltar";
    voltar.appendChild(criarLink("← Voltar para a página inicial", "index.html"));
    corpo.append(fonte, voltar);

    alvo.replaceChildren(capa, legenda, corpo);
  } catch (e) {
    console.error(e);
    alvo.textContent = "Matéria não encontrada.";
  }
}

montarMenus();
montarInicio();
montarMateria();
