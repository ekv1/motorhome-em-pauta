import json, pathlib, shutil, tempfile, subprocess
ROOT=pathlib.Path(__file__).resolve().parent
required=['arquivo.html','arquivo.js','arquivo.css','regras_exibicao.json','aplicar_layout.py','descobrir_tendencias.py','preparar_publicacao.py','.github/workflows/radar-e-aprovacao.yml']
for f in required: assert (ROOT/f).exists(), f'ausente: {f}'
json.loads((ROOT/'regras_exibicao.json').read_text(encoding='utf-8'))
assert json.loads((ROOT/'noticias.json').read_text(encoding='utf-8'))==[]
html=(ROOT/'arquivo.html').read_text(encoding='utf-8'); js=(ROOT/'arquivo.js').read_text(encoding='utf-8')
for x in ['busca-arquivo','categoria-arquivo','ano-arquivo','paginacao-arquivo']:assert x in html
for x in ['POR_PAGINA = 12','aria-current','noticias.json']:assert x in js
subprocess.run(['python3','-m','py_compile',str(ROOT/'aplicar_layout.py'),str(ROOT/'descobrir_tendencias.py'),str(ROOT/'preparar_publicacao.py')],check=True)
print('TESTES OK: pacote, JSON, Python, filtros e paginação')
