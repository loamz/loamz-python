#!/usr/bin/env bash
# Copies an engine's OpenAPI from the checkout next to this repository: contracts/vendor.sh data
set -euo pipefail
engine=${1:?engine name, for example data}
here=$(cd "$(dirname "$0")/.." && pwd)
src=${ENGINE_REPO:-$here/../loamz-$engine}
mkdir -p "$here/contracts/$engine/v1"
cp "$src/specs/$engine/v1/openapi.yaml" "$here/contracts/$engine/v1/openapi.yaml"
sha256sum "$here/contracts/$engine/v1/openapi.yaml" | cut -d' ' -f1 > "$here/contracts/$engine/v1/SHA256"
git -C "$src" rev-parse HEAD > "$here/contracts/$engine/v1/COMMIT"
echo "vendored $engine at $(cat "$here/contracts/$engine/v1/COMMIT")"
