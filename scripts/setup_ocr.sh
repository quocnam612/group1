#!/usr/bin/env bash
set -euo pipefail
OCR_PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$OCR_PROJECT_ROOT"
export UV_CACHE_DIR="$OCR_PROJECT_ROOT/.cache/uv"
export UV_PYTHON_INSTALL_DIR="$OCR_PROJECT_ROOT/.cache/uv-python"
export UV_HTTP_TIMEOUT=1800
export UV_CONCURRENT_DOWNLOADS=1
export UV_CONCURRENT_INSTALLS=1
export UV_CONCURRENT_BUILDS=1
OCR_TORCH_TARGET="${1:-cpu}"
case "$OCR_TORCH_TARGET" in
  cpu|cu128) ;;
  *) echo 'Usage: bash scripts/setup_ocr.sh [cpu|cu128]' >&2; exit 2 ;;
esac
command -v uv >/dev/null || { echo 'Install uv: https://docs.astral.sh/uv/getting-started/installation/' >&2; exit 1; }
uv python install 3.11
if [[ ! -x .venv-ocr/bin/python ]]; then
  uv venv --python 3.11 .venv-ocr
fi
if [[ "$OCR_TORCH_TARGET" == cu128 ]]; then
  # The PyPI Linux wheels of this pinned release use CUDA 12.8.
  uv pip install --python .venv-ocr/bin/python --index-url https://pypi.org/simple \
    --reinstall-package torch --reinstall-package torchvision 'torch==2.9.1' 'torchvision==0.24.1'
else
  uv pip install --python .venv-ocr/bin/python --index https://pypi.org/simple \
    --default-index https://download.pytorch.org/whl/cpu --index-strategy unsafe-first-match \
    'torch==2.9.1+cpu' 'torchvision==0.24.1+cpu'
fi
uv pip install --python .venv-ocr/bin/python -r requirements-ocr.txt
mkdir -p out/ocr
uv pip freeze --python .venv-ocr/bin/python > out/ocr/environment.txt
.venv-ocr/bin/python src/ocr.py doctor
