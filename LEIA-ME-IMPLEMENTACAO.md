# Implementação completa

Este pacote reúne os dois assuntos discutidos:

1. radar editorial com publicação somente após aprovação por Pull Request;
2. homepage com Novidades e página de Arquivo de publicações.

## Instalação

1. Copie para a raiz: `arquivo.html`, `arquivo.js`, `arquivo.css`, `regras_exibicao.json`, `descobrir_tendencias.py`, `preparar_publicacao.py` e `aplicar_layout.py`.
2. Substitua `noticias.json` pelo arquivo vazio fornecido para limpar as notícias atuais.
3. Copie os dois workflows para `.github/workflows` e desative o workflow antigo que publica diretamente na `main`.
4. Na raiz do repositório, execute `python3 aplicar_layout.py` uma única vez. O script altera os arquivos existentes `index.html` e `site.js` sem substituir o restante do layout.
5. Acrescente o conteúdo de `arquivo.css` ao site mantendo também o arquivo separado referenciado por `arquivo.html`.
6. Faça commit das alterações.
7. Habilite em GitHub: **Settings > Actions > General > Workflow permissions > Read and write permissions** e **Allow GitHub Actions to create and approve pull requests**.
8. Execute manualmente **Radar editorial e aprovação**.

## Comportamento

- selo Novo: até 7 dias;
- bloco Novidades: até 30 dias e no máximo 6 itens;
- notícia comum na homepage: até 30 dias;
- lançamento nacional: até 90 dias;
- equipamento: até 45 dias;
- destino: até 45 dias;
- tendência internacional: até 15 dias;
- evento futuro permanece visível;
- todos os itens continuam em `arquivo.html`;
- arquivo com busca, categoria, ano, ordenação e 12 itens por página;
- mesma URL da matéria, sem mover registros para outro JSON;
- nenhuma matéria entra na `main` sem merge do Pull Request.

## Teste local estrutural

Execute:

```bash
python3 testar_implementacao.py
```
