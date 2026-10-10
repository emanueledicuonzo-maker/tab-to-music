#!/usr/bin/env bash
# Lanciatore per l'icona: scegli la canzone e lo strumento, poi si apre la pagina.
cd "$(dirname "$(readlink -f "$0")")" || exit 1

canzone=$(zenity --file-selection --title="Tablatura: scegli la canzone" \
  --file-filter="Audio | *.mp3 *.flac *.wav *.ogg *.m4a *.MP3 *.FLAC *.WAV") || exit 0

strumento=$(zenity --list --radiolist --title="Tablatura" --text="Quale strumento?" \
  --column="" --column="Strumento" --height=280 \
  TRUE basso FALSE basso5 FALSE chitarra FALSE chitarra-dropd) || exit 0

opzioni=()
if zenity --question --title="Tablatura" --text="Trascrivo anche il testo cantato?" --ok-label="Sì" --cancel-label="No"; then
  opzioni+=(--testo)
fi
[[ $strumento == chitarra* ]] && opzioni+=(--polifonico)

registro=$(mktemp --suffix=.log)
.venv-311/bin/python -m tablatura "$canzone" --strumento "$strumento" "${opzioni[@]}" >"$registro" 2>&1 &
lavoro=$!
( while kill -0 $lavoro 2>/dev/null; do tail -n1 "$registro" | sed 's/^/# /'; sleep 1; done ) |
  zenity --progress --pulsate --auto-close --no-cancel --title="Tablatura" \
    --text="Sto lavorando su $(basename "$canzone")…" --width=500
wait $lavoro
esito=$?

pagina=$(grep -oP '^pagina:\s+\K.*' "$registro")
if [[ $esito -eq 0 && -n $pagina ]]; then
  xdg-open "$pagina"
elif [[ $esito -eq 0 ]]; then
  zenity --info --title="Tablatura" --text="Fatto. I risultati sono in:\n$(dirname "$canzone")" --width=400
else
  zenity --text-info --title="Tablatura: qualcosa è andato storto" --filename="$registro" --width=700 --height=450
fi
