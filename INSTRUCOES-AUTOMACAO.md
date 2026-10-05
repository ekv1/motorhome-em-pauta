# Automação do Motorhome em Pauta

## Comportamento

- Execução agendada: coleta, valida e publica automaticamente.
- Execução manual com `publicar_automaticamente` desmarcado: somente teste e artefatos.
- Execução manual com `publicar_automaticamente` marcado: publica os itens aprovados.
- Publicações são adicionadas ao `noticias.json`; o histórico do Git permite reversão.

## Proteções

- Categorias precisam estar na lista permitida.
- Campos obrigatórios, data, URL HTTPS e tamanho de título/resumo são validados.
- Duplicidades não são publicadas.
- Lançamentos sinalizados para revisão são retidos.
- No máximo uma candidata é avaliada pelo Groq por execução.

## Arquivos

- `publicar_pendentes.py`: valida e inclui os pendentes no `noticias.json`.
- `.github/workflows/executar-coletor.yml`: agenda, testa, publica e faz commit.
