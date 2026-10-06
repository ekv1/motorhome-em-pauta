(() => {
  const POR_PAGINA = 12;
  const $ = s => document.querySelector(s);
  const texto = v => typeof v === 'string' && v.trim();
  const normalizar = v => (v || '').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
  const dataMs = d => { const m=/^(\d{2})\/(\d{2})\/(\d{4})$/.exec(d||''); return m ? new Date(+m[3],+m[2]-1,+m[1]).getTime() : 0; };
  const paginaAtual = () => Math.max(1, parseInt(new URLSearchParams(location.search).get('page') || '1',10) || 1);
  const urlPagina = p => { const u=new URL(location.href); p<=1?u.searchParams.delete('page'):u.searchParams.set('page',p); return u.pathname+u.search; };
  function linkItem(i){ return texto(i.slug)&&i.corpo ? `materia.html?id=${encodeURIComponent(i.slug)}` : i.link || '#'; }
  function card(i){
    const a=document.createElement('a'); a.className='cartao'; a.href=linkItem(i); if(/^https?:/.test(a.href)&&!a.href.startsWith(location.origin)){a.target='_blank';a.rel='noopener noreferrer'}
    const foto=document.createElement('div'); foto.className='foto'; if(i.imagem) foto.style.backgroundImage=`url("${i.imagem}")`;
    const selo=document.createElement('span'); selo.className='selo'; selo.textContent=i.selo||i.categoria_sugerida||'Publicação'; foto.appendChild(selo);
    const c=document.createElement('div'); c.className='conteudo';
    const h=document.createElement('h3'); h.textContent=i.titulo||''; const p=document.createElement('p'); p.textContent=i.resumo||'';
    const r=document.createElement('div'); r.className='rodape-cartao'; r.textContent=`${i.data||''}${i.fonte?' · '+i.fonte:''}`;
    c.append(h,p,r); a.append(foto,c); return a;
  }
  function paginar(total,atual){
    const nav=$('#paginacao-arquivo'); nav.replaceChildren(); const paginas=Math.max(1,Math.ceil(total/POR_PAGINA));
    const add=(rotulo,p,atualFlag=false,disabled=false)=>{const el=disabled?document.createElement('span'):document.createElement('a'); el.textContent=rotulo;if(disabled)el.className='desativado';else el.href=urlPagina(p);if(atualFlag)el.setAttribute('aria-current','page');nav.appendChild(el)};
    add('Anterior',Math.max(1,atual-1),false,atual===1);
    const inicio=Math.max(1,atual-2), fim=Math.min(paginas,inicio+4); for(let p=inicio;p<=fim;p++)add(String(p),p,p===atual);
    add('Próxima',Math.min(paginas,atual+1),false,atual===paginas);
  }
  async function iniciar(){
    const itens=await fetch('noticias.json',{cache:'no-store'}).then(r=>{if(!r.ok)throw Error();return r.json()});
    const categorias=[...new Set(itens.map(i=>i.categoria_sugerida).filter(Boolean))].sort(); const anos=[...new Set(itens.map(i=>(i.data||'').slice(-4)).filter(a=>/^\d{4}$/.test(a)))].sort().reverse();
    categorias.forEach(v=>$('#categoria-arquivo').add(new Option(v,v))); anos.forEach(v=>$('#ano-arquivo').add(new Option(v,v)));
    const q=new URLSearchParams(location.search); $('#busca-arquivo').value=q.get('q')||''; $('#categoria-arquivo').value=q.get('categoria')||''; $('#ano-arquivo').value=q.get('ano')||''; $('#ordem-arquivo').value=q.get('ordem')||'recentes';
    const aplicar=()=>{const u=new URL(location.href);['q','categoria','ano','ordem'].forEach(k=>{const el=$(`[name="${k}"]`); if(el&&el.value&&(k!=='ordem'||el.value!=='recentes'))u.searchParams.set(k,el.value);else u.searchParams.delete(k)});u.searchParams.delete('page');location.href=u.pathname+u.search};
    $('#filtros-arquivo').addEventListener('change',aplicar); $('#filtros-arquivo').addEventListener('submit',e=>{e.preventDefault();aplicar()}); $('#limpar-arquivo').onclick=()=>{location.href='arquivo.html'};
    const termo=normalizar($('#busca-arquivo').value), cat=$('#categoria-arquivo').value, ano=$('#ano-arquivo').value, ordem=$('#ordem-arquivo').value;
    let lista=itens.filter(i=>!termo||normalizar([i.titulo,i.resumo,i.fonte,i.marca,i.modelo,(i.tags||[]).join(' ')].join(' ')).includes(termo)).filter(i=>!cat||i.categoria_sugerida===cat).filter(i=>!ano||(i.data||'').endsWith(ano));
    lista.sort((a,b)=>(ordem==='antigas'?1:-1)*(dataMs(a.data)-dataMs(b.data))); const paginas=Math.max(1,Math.ceil(lista.length/POR_PAGINA)); const pagina=Math.min(paginaAtual(),paginas); const lote=lista.slice((pagina-1)*POR_PAGINA,pagina*POR_PAGINA);
    $('#contagem-arquivo').textContent=`${lista.length} publicação${lista.length===1?'':'ões'} · página ${pagina} de ${paginas}`; const grade=$('#grade-arquivo'); grade.replaceChildren(...lote.map(card)); if(!lote.length){const v=document.createElement('div');v.className='arquivo-vazio';v.textContent='Nenhuma publicação encontrada com estes filtros.';grade.appendChild(v)} paginar(lista.length,pagina);
  }
  iniciar().catch(()=>{$('#grade-arquivo').textContent='Não foi possível carregar o arquivo agora.'});
})();
