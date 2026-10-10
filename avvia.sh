#!/usr/bin/env bash
# L'icona: accende il programma (se non è già acceso) e apre la sua finestra.
cd "$(dirname "$(readlink -f "$0")")" || exit 1

INDIRIZZO=http://127.0.0.1:8777/

if ! curl -s -o /dev/null "$INDIRIZZO"; then
  setsid .venv-311/bin/python -m tablatura.app >"${XDG_RUNTIME_DIR:-/tmp}/tablatura.log" 2>&1 < /dev/null &
  for _ in $(seq 50); do
    curl -s -o /dev/null "$INDIRIZZO" && break
    sleep 0.1
  done
fi

exec google-chrome --app="$INDIRIZZO" --class=Tablatura
