#!/bin/zsh
# Doppelklick im Finder startet "Bilder trennen" (öffnet sich in Terminal.app).
cd "$(dirname "$0")" || exit 1
exec ./start.sh "$@"
