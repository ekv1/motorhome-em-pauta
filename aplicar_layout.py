from pathlib import Path
INDEX=Path('index.html'); SITE=Path('site.js')

def once(text, old, new, name):
    if new in text:return text
    if old not in text:raise SystemExit(f'Ponto de alteração não encontrado em {name}')
    return text.replace(old,new,1)

def main():
    h=INDEX.read_text(encoding='utf-8')
    h=once(h,'<main>','''<main>\n  <section id="novidades" class="faixa novidades">\n    <div class="largura">\n      <div class="cabecalho cabecalho-com-link"><div><p class="chapeu">Conteúdo recente</p><h2>Novidades</h2><p>As publicações mais recentes do Motorhome em Pauta.</p></div><a class="botao arquivo-link" href="arquivo.html">Ver todas as publicações</a></div>\n      <div id="grade-novidades" class="grade grade-novidades"></div>\n    </div>\n  </section>''','index.html')
    h=once(h,'<section id="fabricantes" class="faixa petroleo">','''<section class="faixa chamada-arquivo"><div class="largura chamada-arquivo-inner"><div><p class="chapeu">Biblioteca editorial</p><h2>Continue explorando</h2><p>Encontre notícias, guias e referências anteriores por categoria, ano ou palavra-chave.</p></div><a class="botao" href="arquivo.html">Abrir arquivo de publicações</a></div></section>\n  <section id="fabricantes" class="faixa petroleo">''','index.html')
    INDEX.write_text(h,encoding='utf-8')
    s=SITE.read_text(encoding='utf-8')
    s=once(s,'["Fabricantes", "fabricantes.html"]','["Fabricantes", "fabricantes.html"], ["Arquivo", "arquivo.html"]','site.js')
    marker='async function montarInicio() {'
    helper='''const DIAS_HOME_PADRAO = 30;\nfunction permaneceNaHome(item) {\n  const idade = idadeEmDias(item);\n  if (idade < 0) return false;\n  if (item.tipo_conteudo === "evento" && item.data_evento) return paraData(item.data_evento) >= Date.now() - DIA;\n  if (item.destaque === "lancamento" && item.mercado === "Brasil") return idade <= 90;\n  if (item.tipo_conteudo === "equipamento") return idade <= 45;\n  if (item.tipo_conteudo === "tendencia_internacional") return idade <= 15;\n  if (item.tipo_conteudo === "destino") return idade <= 45;\n  return idade <= DIAS_HOME_PADRAO;\n}\nfunction montarNovidades(itens) {\n  const grade = document.getElementById("grade-novidades");\n  if (!grade) return;\n  const cards = itens.filter(i => idadeEmDias(i) >= 0 && idadeEmDias(i) <= DIAS_HOME_PADRAO).slice(0, 6).map(cartao).filter(Boolean);\n  if (cards.length) grade.replaceChildren(...cards);\n  else { const v=document.createElement("div"); v.className="vazio"; v.textContent="Em breve, novas publicações."; grade.replaceChildren(v); }\n}\n'''
    if helper not in s:s=s.replace(marker,helper+marker,1)
    s=once(s,'montarLancamentos(itens);','montarNovidades(itens);\n    montarLancamentos(itens);','site.js')
    s=once(s,'.filter(i => !ehLancamentoNacional(i))   // evita repetir o que já está na faixa','.filter(i => !ehLancamentoNacional(i))   // evita repetir o que já está na faixa\n        .filter(permaneceNaHome)','site.js')
    SITE.write_text(s,encoding='utf-8')
    print('Layout atualizado: Novidades + Arquivo + regras de permanência')
if __name__=='__main__':main()
