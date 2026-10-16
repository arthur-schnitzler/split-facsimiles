#!/bin/zsh
# Startet "Bilder trennen" mit der lokalen .venv (Pillow ist dort installiert).
cd "$(dirname "$0")" || exit 1
if [ ! -x .venv/bin/python ] || ! .venv/bin/python -c "import PIL" 2>/dev/null; then
  echo "Richte .venv ein ..."
  python3 -m venv .venv && .venv/bin/pip install --quiet pillow || exit 1
fi
exec .venv/bin/python script/bilder-trennen.py "$@"
