# Comando /refazer

## Instalação

Copie para a raiz:
- `refazer_materia.py`

Copie para `.github/workflows/`:
- `refazer-materia.yml`

Mantenha os Secrets:
- `GROQ_API_KEY`
- `GEMINI_API_KEY`
- `CLOUDFLARE_ACCOUNT_ID`
- `CLOUDFLARE_API_TOKEN`

## Uso

No Pull Request editorial, publique um comentário começando com:

`/refazer Faça uma comparação com o que existe ou não existe no Brasil e desenvolva mais o tema.`

A automação:
1. lê a orientação;
2. pesquisa contexto público com Gemini + Google Search, se disponível;
3. relê a fonte principal;
4. reescreve o item adicionado no PR;
5. atualiza ou gera a imagem;
6. grava um novo commit na mesma branch do PR;
7. comenta o resultado no PR.

A publicação só ocorre quando o proprietário fizer o merge.
