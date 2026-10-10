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

# Un Chrome tutto suo, con un profilo a parte: se usasse il tuo, la prima
# volta che Chrome è chiuso lo accenderebbe lui, e GNOME metterebbe sotto
# l'icona Tablatura anche tutte le tue pagine normali.
exec google-chrome --user-data-dir="$HOME/.config/tablatura/chrome" --no-first-run --no-default-browser-check \
  --app="$INDIRIZZO" --class=Tablatura
