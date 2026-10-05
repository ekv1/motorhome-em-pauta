// Motorhome em Pauta - conteúdo carregado de noticias.json e fabricantes.json
// O coletor automático só precisa acrescentar itens em noticias.json.

const SECOES = [
  ["Lançamentos", "index.html#lancamentos"],
  ["Notícias", "index.html#ultimas"],
  ["Eventos", "index.html#eventos"],
  ["Internacionais", "index.html#internacionais"],
  ["Guias", "index.html#guias"],
  ["Comunidade", "index.html#comunidade"],
  ["Fabricantes", "fabricantes.html"]
];

const IMAGEM_PADRAO = {
  "Últimas notícias": "imagens/capa-estrada.png",
  "Eventos e feiras": "imagens/padrao-comunidade.png",
  "Novidades internacionais": "imagens/ilustrativa-veiculos.png",
  "Guias e vida a bordo": "imagens/guia-organizar.png",
  "Histórias e comunidade": "imagens/padrao-comunidade.png"
};

const ROTULO = {
  "Últimas notícias": "Brasil",
  "Eventos e feiras": "Evento",
  "Novidades internacionais": "Internacional",
  "Guias e vida a bordo": "Guia",
  "Histórias e comunidade": "Comunidade"
};

const MAXIMO_POR_SECAO = 6;
const DIAS_FAIXA_LANCAMENTOS = 90;  // tempo na faixa "Lançamentos nacionais"
const DIAS_SELO_NOVO = 30;          // tempo do selo "Novo modelo" nos cartões
const MAXIMO_LANCAMENTOS = 6;
const FILTROS_LANC = ["Todos", "Motorhome", "Trailer", "Camper", "Van"];
const DIA = 24 * 60 * 60 * 1000;

function criarLink(texto, destino, classe, externo) {
  const a = document.createElement("a");
  a.textContent = texto;
  a.href = destino;
  if (classe) a.className = classe;
  if (externo) { a.target = "_blank"; a.rel = "noopener noreferrer"; }
  return a;
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

function idadeEmDias(item) {
  const t = paraData(item.data);
  return t ? Math.floor((Date.now() - t) / DIA) : Infinity;
}

function ehLancamento(item) { return item.destaque === "lancamento"; }

function ehLancamentoNacional(item) {
  // Só entra na faixa: lançamento + mercado Brasil + dentro do prazo.
  return ehLancamento(item) && item.mercado === "Brasil" &&
    idadeEmDias(item) >= 0 && idadeEmDias(item) <= DIAS_FAIXA_LANCAMENTOS;
}

function montarMenus() {
  const menu = document.getElementById("menu");
  const rodape = document.getElementById("menu-rodape");
  const naInicial = document.querySelector(".grade[data-categoria]") !== null;
  SECOES.forEach(([nome, destino]) => {
    const link = naInicial && destino.startsWith("index.html#") ? destino.replace("index.html", "") : destino;
    const a1 = criarLink(nome, link);
    if (nome === "Lançamentos") a1.dataset.menuLanc = "1";
    if (menu) menu.appendChild(a1);
    if (rodape) {
      const a2 = criarLink(nome, link);
      if (nome === "Lançamentos") a2.dataset.menuLanc = "1";
      rodape.appendChild(a2);
    }
  });
  if (menu) menu.appendChild(criarLink("Viver é estrada", naInicial ? "#ultimas" : "index.html#ultimas", "botao"));
  const capa = document.getElementById("capa-acao");
  if (capa) capa.appendChild(criarLink("Ver últimas notícias →", "#ultimas", "botao-capa"));
}

function esconderMenuLancamentos() {
  document.querySelectorAll("[data-menu-lanc]").forEach(a => { a.hidden = true; });
}

function destinoDoItem(item) {
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

  if (ehLancamento(item) && idadeEmDias(item) <= DIAS_SELO_NOVO) {
    const novo = document.createElement("span");
    novo.className = "selo-novo";
    novo.textContent = "Novo modelo";
    foto.appendChild(novo);
  } else if (item.imagem_legenda === "Imagem ilustrativa" || !item.imagem) {
    const ilu = document.createElement("span");
    ilu.className = "ilustrativa";
    ilu.textContent = "Imagem ilustrativa";
    foto.appendChild(ilu);
  }

  const selo = document.createElement("span");
  selo.className = "selo";
  selo.textContent = item.selo || ROTULO[categoria] || "Notícia";
  foto.appendChild(selo);

  const conteudo = document.createElement("div");
  conteudo.className = "conteudo";

  if (ehLancamento(item)) {
    const partes = [item.tipo_veiculo, item.marca, item.uf].filter(texto);
    if (partes.length) {
      const ficha = document.createElement("p");
      ficha.className = "ficha";
      ficha.textContent = partes.join(" · ");
      conteudo.appendChild(ficha);
    }
  }

  const h3 = document.createElement("h3");
  h3.textContent = item.titulo;
  const p = document.createElement("p");
  p.textContent = item.resumo || "";
  const base = document.createElement("div");
  base.className = "rodape-cartao";
  const info = document.createElement("span");
  info.textContent = item.data + (texto(item.fonte) ? " · " + item.fonte : "");
  base.appendChild(info);
  if (item.origem === "fabricante") {
    const o = document.createElement("span");
    o.className = "origem";
    o.textContent = "Informação do fabricante";
    base.appendChild(o);
  }
  const seta = document.createElement("span");
  seta.className = "seta";
  seta.textContent = destino.externo ? "↗" : "→";
  base.appendChild(seta);
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
  if (alvo && !alvo.hidden) alvo.scrollIntoView();
}

function montarLancamentos(itens) {
  const secao = document.getElementById("lancamentos");
  if (!secao) return;
  const lancs = itens.filter(ehLancamentoNacional);
  if (!lancs.length) {
    secao.hidden = true;           // sem lançamento nacional recente, a faixa some
    esconderMenuLancamentos();
    return;
  }
  secao.hidden = false;
  const grade = document.getElementById("grade-lanc");
  const filtros = document.getElementById("filtros-lanc");
  const tipos = FILTROS_LANC.filter(t => t === "Todos" || lancs.some(i => i.tipo_veiculo === t));

  const exibir = tipo => {
    const lista = tipo === "Todos" ? lancs : lancs.filter(i => i.tipo_veiculo === tipo);
    grade.replaceChildren(...lista.slice(0, MAXIMO_LANCAMENTOS).map(cartao).filter(Boolean));
    filtros.querySelectorAll(".filtro").forEach(b => {
      const ativo = b.dataset.filtro === tipo;
      b.classList.toggle("ativo", ativo);
      b.setAttribute("aria-pressed", ativo ? "true" : "false");
    });
  };

  filtros.replaceChildren();
  if (tipos.length > 2) {          // filtros só aparecem quando há mais de um tipo
    tipos.forEach(t => {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "filtro";
      b.dataset.filtro = t;
      b.textContent = t === "Todos" ? "Todos" : t + "s";
      b.addEventListener("click", () => exibir(t));
      filtros.appendChild(b);
    });
  }
  exibir("Todos");
}

async function montarInicio() {
  const grades = document.querySelectorAll(".grade[data-categoria]");
  if (!grades.length) return;
  try {
    const itens = (await carregarNoticias()).sort((a, b) => paraData(b.data) - paraData(a.data));
    montarLancamentos(itens);
    grades.forEach(grade => {
      const cat = grade.dataset.categoria;
      const cartoes = itens
        .filter(i => (i.categoria_sugerida || "Últimas notícias") === cat)
        .filter(i => !ehLancamentoNacional(i))   // evita repetir o que já está na faixa
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
  await montarDestaqueFabricantes();
  irParaAncora();
}

function fichaLancamento(item) {
  const box = document.createElement("div");
  box.className = "ficha-lanc";
  const h2 = document.createElement("h2");
  h2.textContent = "Ficha do lançamento";
  const dl = document.createElement("dl");
  [["Marca", item.marca], ["Modelo", item.modelo], ["Tipo", item.tipo_veiculo],
   ["Fabricação", item.mercado === "Brasil" ? "Nacional" + (texto(item.uf) ? " (" + item.uf + ")" : "") : "Internacional"],
   ["Origem da informação", item.origem === "fabricante" ? "Fabricante" : "Imprensa"]]
    .filter(([, v]) => texto(v))
    .forEach(([k, v]) => {
      const dt = document.createElement("dt"); dt.textContent = k;
      const dd = document.createElement("dd"); dd.textContent = v;
      dl.append(dt, dd);
    });
  box.append(h2, dl);
  return box;
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
    meta.textContent = (ehLancamento(item) ? "Lançamento" : (ROTULO[categoria] || "Notícia")) + " · " + item.data;
    const h1 = document.createElement("h1");
    h1.textContent = item.titulo;
    const ab = document.createElement("p");
    ab.className = "abertura";
    ab.textContent = item.corpo.abertura || item.resumo || "";
    corpo.append(meta, h1, ab);
    if (ehLancamento(item)) corpo.appendChild(fichaLancamento(item));

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

// ---------- Fabricantes ----------
const CORES_FAB = ["#0e4a57", "#e8622c", "#3b6e4f", "#8a5a2b", "#2f4f7a"];
const FILTROS_FAB = ["Todos", "Trailers", "Motorhomes e vans", "Campers", "Revendas e importadores"];

function siteFabricante(v) {
  try {
    const u = new URL(v);
    if (u.protocol === "https:" || u.protocol === "http:") return u.href;
  } catch (e) {}
  return null;
}

async function carregarFabricantes() {
  const r = await fetch("fabricantes.json", { cache: "no-store" });
  if (!r.ok) throw new Error("fabricantes.json indisponível");
  const dados = await r.json();
  return (Array.isArray(dados) ? dados : [])
    .filter(f => f && texto(f.nome) && siteFabricante(f.site))
    .sort((a, b) => a.nome.localeCompare(b.nome, "pt-BR"));
}

function cartaoFabricante(f, i) {
  const c = document.createElement("article");
  c.className = "fab";
  const topo = document.createElement("div");
  topo.className = "fab-topo";
  const ini = document.createElement("span");
  ini.className = "inicial";
  ini.style.background = CORES_FAB[i % CORES_FAB.length];
  ini.textContent = f.nome.charAt(0);
  const nome = document.createElement("div");
  const h3 = document.createElement("h3");
  h3.textContent = f.nome;
  nome.appendChild(h3);
  if (texto(f.local)) {
    const l = document.createElement("p");
    l.className = "fab-local";
    l.textContent = "📍 " + f.local;
    nome.appendChild(l);
  }
  topo.append(ini, nome);
  const et = document.createElement("div");
  et.className = "etiquetas";
  (f.categorias || []).forEach(cat => {
    const e = document.createElement("span");
    e.className = "etiqueta";
    e.textContent = cat;
    et.appendChild(e);
  });
  const d = document.createElement("p");
  d.className = "desc";
  d.textContent = f.descricao || "";
  c.append(topo, et, d, criarLink("Visitar site oficial ↗", siteFabricante(f.site), "visitar", true));
  return c;
}

async function montarFabricantes() {
  const lista = document.getElementById("lista-fabricantes");
  if (!lista) return;
  const filtros = document.getElementById("filtros");
  const contagem = document.getElementById("contagem");
  try {
    const todos = await carregarFabricantes();
    const exibir = filtro => {
      const itens = filtro === "Todos" ? todos : todos.filter(f => (f.categorias || []).includes(filtro));
      lista.replaceChildren(...itens.map(cartaoFabricante));
      contagem.textContent = itens.length + (itens.length === 1 ? " empresa" : " empresas");
      filtros.querySelectorAll(".filtro").forEach(b => {
        const ativo = b.dataset.filtro === filtro;
        b.classList.toggle("ativo", ativo);
        b.setAttribute("aria-pressed", ativo ? "true" : "false");
      });
    };
    FILTROS_FAB.forEach(nome => {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "filtro";
      b.dataset.filtro = nome;
      b.textContent = nome;
      b.addEventListener("click", () => exibir(nome));
      filtros.appendChild(b);
    });
    exibir("Todos");
  } catch (e) {
    console.error(e);
    lista.textContent = "Não foi possível carregar a lista de fabricantes agora.";
  }
}

async function montarDestaqueFabricantes() {
  const alvo = document.getElementById("nomes-fab");
  if (!alvo) return;
  try {
    const todos = await carregarFabricantes();
    const links = todos.slice(0, 10).map(f => criarLink(f.nome, siteFabricante(f.site), "", true));
    links.push(criarLink("Ver todos os " + todos.length + " →", "fabricantes.html"));
    alvo.replaceChildren(...links);
  } catch (e) {
    console.error(e);
  }
}

// Nas páginas sem a faixa (matéria, fabricantes), o menu "Lançamentos"
// aparece só se houver lançamento nacional recente.
async function ajustarMenuForaDaInicial() {
  if (document.getElementById("lancamentos")) return;
  try {
    const itens = await carregarNoticias();
    if (!itens.some(ehLancamentoNacional)) esconderMenuLancamentos();
  } catch (e) {
    esconderMenuLancamentos();
  }
}

montarMenus();
montarInicio();
montarMateria();
montarFabricantes();
ajustarMenuForaDaInicial();
