#!/usr/bin/env bash
# L'icona: accende il programma (se non è già acceso) e apre l'app.
cd "$(dirname "$(readlink -f "$0")")" || exit 1

INDIRIZZO=http://127.0.0.1:8777/
PROFILO="$HOME/.config/tablatura/chrome"

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
#
# Se l'app è già installata (Chrome scrive un suo .desktop con l'app-id), si
# apre quella, e la sua finestra si raccoglie sotto la nostra icona.
installata=$(grep -l -F -- "--user-data-dir=$PROFILO" "$HOME"/.local/share/applications/chrome-*-*.desktop 2>/dev/null | head -1)
if [[ -n $installata ]]; then
  id=$(grep -oP -- '--app-id=\K[a-p]+' "$installata" | head -1)
  for icona in "$HOME/.local/share/applications/tablatura.desktop" "$HOME/Scrivania/tablatura.desktop"; do
    [[ -f $icona ]] && sed -i "s/^StartupWMClass=.*/StartupWMClass=crx_$id/" "$icona"
  done
  # Il suo doppione nel menu non serve: c'è già la nostra icona.
  grep -q '^NoDisplay=true' "$installata" || echo "NoDisplay=true" >> "$installata"
  exec google-chrome --user-data-dir="$PROFILO" --profile-directory=Default --app-id="$id"
fi

# Non ancora installata: una finestra normale, con il pulsante «Installa» in alto.
exec google-chrome --user-data-dir="$PROFILO" --no-first-run --no-default-browser-check --new-window "$INDIRIZZO"
