# Implantação da aprovação editorial

1. Substitua `noticias.json` pelo arquivo vazio deste pacote.
2. Adicione `descobrir_tendencias.py`, `consultas_tendencias.json` e `preparar_publicacao.py` na raiz.
3. Em `.github/workflows`, remova/desative o workflow antigo que publica diretamente na `main`.
4. Adicione `radar-e-aprovacao.yml` e `validar-publicacao-aprovada.yml`.
5. Em **Settings > Actions > General > Workflow permissions**, selecione **Read and write permissions** e habilite **Allow GitHub Actions to create and approve pull requests**.
6. Execute **Radar editorial e aprovação** manualmente.
7. A matéria será criada em um Pull Request. Revise **Files changed**.
8. Para publicar, selecione **Merge pull request**. Para rejeitar, feche sem merge.

O arquivo `noticias.json` foi intencionalmente zerado para limpar as publicações atuais do site. As imagens antigas não são removidas automaticamente neste pacote, pois podem ser usadas como imagens padrão ou em outras páginas.
