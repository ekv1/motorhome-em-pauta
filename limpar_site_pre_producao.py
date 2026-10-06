#!/usr/bin/env python3
"""Limpa conteúdo editorial de teste e mantém somente a Expo Motorhome 2026."""
from pathlib import Path
import json
import shutil

ARQUIVOS_JSON = [
    Path('noticias.json'),
    Path('pautas-selecionadas.json'),
    Path('pautas-descobertas.json'),
    Path('rascunhos-coletor.json'),
    Path('rascunhos-internacionais.json'),
    Path('pendentes-conferencia.json'),
]

expo = {
  "titulo": "Expo Motorhome 2026 confirma edição de 10 anos em Pinhais",
  "slug": "expo-motorhome-2026-edicao-10-anos-pinhais",
  "resumo": "A 10ª Expo Motorhome será realizada de 25 a 29 de novembro de 2026, no Expotrade Convention Center, em Pinhais (PR), reunindo o setor de campismo e caravanismo.",
  "categoria_sugerida": "Eventos e feiras",
  "origem": "Brasil",
  "tipo": "Evento/encontro",
  "data": "2026-11-25",
  "data_fim": "2026-11-29",
  "fonte": "Expo Motorhome",
  "link": "https://www.expomotorhome.com/",
  "status": "publicado",
  "destaque": True,
  "corpo": {
    "abertura": "A Expo Motorhome chega à 10ª edição em 2026. O evento está confirmado para o período de 25 a 29 de novembro, no Expotrade Convention Center, em Pinhais, no Paraná.",
    "secoes": [
      {
        "subtitulo": "Datas, local e horários",
        "paragrafos": [
          "A feira será realizada de quarta-feira, 25 de novembro, até domingo, 29 de novembro de 2026.",
          "Na quarta e na quinta-feira, o funcionamento será das 14h às 21h. Na sexta-feira, das 12h às 21h. No sábado, das 10h às 21h, e no domingo, das 10h às 17h."
        ]
      },
      {
        "subtitulo": "Campismo e caravanismo reunidos",
        "paragrafos": [
          "A organização apresenta a Expo Motorhome como uma feira voltada ao campismo e ao caravanismo. O site oficial reúne áreas dedicadas a expositores, programação, fórum, camping da Expo, notícias e ingressos.",
          "A edição de 2026 também marca os dez anos da feira."
        ]
      },
      {
        "subtitulo": "Ingressos e planejamento da visita",
        "paragrafos": [
          "A página oficial de ingressos informa que cada ingresso dá direito ao acesso de uma pessoa em um único dia, na data escolhida no momento da compra.",
          "Antes da viagem, o visitante deve confirmar as condições atualizadas, a programação e as regras diretamente nos canais oficiais do evento."
        ]
      }
    ],
    "contexto_brasil": "Por ocorrer no Paraná e reunir empresas e público ligados ao turismo sobre rodas, a Expo Motorhome é uma pauta nacional prioritária para o Motorhome em Pauta."
  },
  "imagem": "",
  "imagem_alt": "Expo Motorhome 2026 em Pinhais, Paraná",
  "fontes_complementares": [
    {
      "titulo": "10ª Expo Motorhome - ingressos e horários",
      "url": "https://minhaentrada.com.br/evento/10a-expomotorhome-29686"
    }
  ]
}

# Backup do conteúdo atual rastreável no repositório.
backup = Path('backup-pre-producao')
backup.mkdir(exist_ok=True)
for arq in ARQUIVOS_JSON:
    if arq.exists():
        shutil.copy2(arq, backup / arq.name)

Path('noticias.json').write_text(
    json.dumps([expo], ensure_ascii=False, indent=2) + '\n',
    encoding='utf-8'
)

# Arquivos transitórios ficam vazios para evitar reaproveitar pautas de teste.
for arq in ARQUIVOS_JSON[1:]:
    if arq.exists():
        arq.write_text('[]\n', encoding='utf-8')

print('Limpeza concluída: noticias.json contém somente a Expo Motorhome 2026.')
print('Backup criado em backup-pre-producao/.')
