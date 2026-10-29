#!/usr/bin/env bash
# Sube los JSON de respaldo (CLIMAPP_RESPALDO_DIR, ver climapp_etl/redis.py) a la etiqueta `datos` del
# repositorio. La web los lee desde raw.githubusercontent.com si Upstash no responde.
#
# Se usa una etiqueta (no una rama) para que Vercel no despliegue en cada subida y `git fetch` no la
# descargue. Cada subida es un commit sin padre (no acumula historial): el árbol anterior + los archivos
# nuevos. Si dos flujos suben a la vez, --force-with-lease rechaza al segundo, que reintenta.
#
# Uso (GitHub Actions): GITHUB_TOKEN y GITHUB_REPOSITORY en el entorno; publicar_respaldo.sh <directorio>
set -euo pipefail

dir=$(cd "${1:?directorio}" 2>/dev/null && pwd) || { echo "Sin respaldo que subir"; exit 0; }
[ -n "$(find "$dir" -type f -name '*.json' -print -quit)" ] || { echo "Sin respaldo que subir"; exit 0; }
repo="https://x-access-token:${GITHUB_TOKEN}@github.com/${GITHUB_REPOSITORY}.git"
ref=refs/tags/datos

trabajo=$(mktemp -d)
cd "$trabajo"
git init -q
git config user.name "ClimApp ETL"
git config user.email "climapp-etl@users.noreply.github.com"

for intento in 1 2 3 4 5; do
  rm -rf arbol .git/index && mkdir arbol
  if git fetch -q --depth 1 "$repo" "+$ref:$ref" 2>/dev/null; then
    base=$(git rev-parse "$ref^{commit}")
    git --work-tree=arbol checkout -q "$base" -- .
  else
    base=""
  fi
  cp -R "$dir"/. arbol/
  git --work-tree=arbol add -A
  commit=$(git commit-tree "$(git write-tree)" -m "Datos $(date -u +%Y-%m-%dT%H:%M:%SZ)")
  if git push -q --force-with-lease="$ref:$base" "$repo" "$commit:$ref"; then
    echo "Respaldo subido: $(find "$dir" -type f -name '*.json' | wc -l) archivos (intento $intento)"
    exit 0
  fi
  sleep $((5 + RANDOM % 10))
done
echo "No se pudo subir el respaldo" >&2
exit 1
