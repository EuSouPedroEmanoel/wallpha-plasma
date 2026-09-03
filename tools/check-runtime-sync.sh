#!/usr/bin/env bash
# Verifica se o runtime Python compartilhado continua alinhado entre CLI e Plasma.
# Os arquivos abaixo têm diferenças deliberadas: o CLI delega o daemon ao Plasma
# e o Plasma executa o daemon localmente.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WORKSPACE_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
CLI_DIR="${WALLPHA_CLI_DIR:-$WORKSPACE_DIR/wallpha-cli/src/wallpha}"
PLASMA_DIR="$WORKSPACE_DIR/wallpha-plasma/src/wallpha"

if [[ ! -d "$CLI_DIR" || ! -d "$PLASMA_DIR" ]]; then
    echo "Erro: execute este script dentro do workspace que contém wallpha-cli e wallpha-plasma." >&2
    exit 2
fi

declare -A EXPECTED_DIVERGENCES=(
    ["__init__.py"]=1
    ["daemon.py"]=1
    ["mode_ps.py"]=1
    ["service.py"]=1
)

status=0

while IFS= read -r rel; do
    if [[ ! -f "$PLASMA_DIR/$rel" ]]; then
        echo "Ausente no Plasma: $rel" >&2
        status=1
        continue
    fi
    if ! cmp -s "$CLI_DIR/$rel" "$PLASMA_DIR/$rel" && [[ -z "${EXPECTED_DIVERGENCES[$rel]:-}" ]]; then
        echo "Divergência inesperada: $rel" >&2
        status=1
    fi
done < <(cd "$CLI_DIR" && find . -type f -name '*.py' -printf '%P\n' | sort)

while IFS= read -r rel; do
    if [[ ! -f "$CLI_DIR/$rel" ]]; then
        echo "Ausente no CLI: $rel" >&2
        status=1
    fi
done < <(cd "$PLASMA_DIR" && find . -type f -name '*.py' -printf '%P\n' | sort)

if [[ "$status" -ne 0 ]]; then
    exit "$status"
fi

echo "Runtime sincronizado; divergências deliberadas: ${!EXPECTED_DIVERGENCES[*]}"
