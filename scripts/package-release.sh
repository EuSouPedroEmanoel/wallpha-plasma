#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VERSION="$(sed -n 's/^version = "\([^"]*\)"/\1/p' "$ROOT_DIR/pyproject.toml" | head -1)"
OUT_DIR="${1:-$ROOT_DIR/dist}"

if [[ ! "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "Versão inválida em pyproject.toml: $VERSION" >&2
    exit 1
fi
if [[ -n "${GITHUB_REF_NAME:-}" && "$GITHUB_REF_NAME" != "v$VERSION" ]]; then
    echo "A tag $GITHUB_REF_NAME não corresponde à versão v$VERSION" >&2
    exit 1
fi
if ! grep -Eq "project\(wallpha-plasma VERSION $VERSION\)" "$ROOT_DIR/CMakeLists.txt" || ! grep -Eq '"Version": "'"$VERSION"'"' "$ROOT_DIR/metadata.json"; then
    echo "Versões de CMake/metadata não correspondem a $VERSION" >&2
    exit 1
fi

STAGE_DIR="$(mktemp -d)"
trap 'rm -rf "$STAGE_DIR"' EXIT
mkdir -p "$OUT_DIR"
NAME="wallpha-plasma-$VERSION"
mkdir -p "$STAGE_DIR/$NAME"

for item in CMakeLists.txt LICENSE README.md bin contents install.sh metadata.json pyproject.toml scripts src systemd tools; do
    cp -a "$ROOT_DIR/$item" "$STAGE_DIR/$NAME/"
done
find "$STAGE_DIR" -type d \( -name __pycache__ -o -name .pytest_cache -o -name .venv -o -name build -o -name dist \) -prune -exec rm -rf {} +

tar -C "$STAGE_DIR" -czf "$OUT_DIR/$NAME.tar.gz" "$NAME"
(cd "$STAGE_DIR" && zip -qr "$OUT_DIR/$NAME.zip" "$NAME")

for artifact in "$OUT_DIR/$NAME.tar.gz" "$OUT_DIR/$NAME.zip"; do
    test -s "$artifact"
done
printf 'Artefatos gerados em %s\n' "$OUT_DIR"
