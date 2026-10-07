#!/usr/bin/env bash
set -euo pipefail

cd /workspaces/motorhome-em-pauta
mkdir -p .github/workflows

cp /mnt/data/escolher_pauta.py escolher_pauta.py
cp /mnt/data/escolher-pauta.yml .github/workflows/escolher-pauta.yml
chmod +x escolher_pauta.py

python3 -m py_compile escolher_pauta.py

if [ -x /go/bin/actionlint ]; then
  /go/bin/actionlint .github/workflows/escolher-pauta.yml
fi

git diff --check
git add escolher_pauta.py .github/workflows/escolher-pauta.yml
git commit -m "Implementar aprovacao de pauta por comentario"
git push origin main

echo "APROVACAO INSTALADA. Publique um NOVO comentario /escolher N no PR de selecao."
