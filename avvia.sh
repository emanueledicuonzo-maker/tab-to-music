#!/usr/bin/env bash
# Lanciatore per l'icona: scegli canzoni o cartelle e lo strumento, poi si aprono le pagine.
cd "$(dirname "$(readlink -f "$0")")" || exit 1

audio='.*\.\(mp3\|flac\|wav\|ogg\|m4a\)'

scelta=$(zenity --list --radiolist --title="Tablatura" --text="Cosa vuoi caricare?" \
  --column="" --column="Cosa" --height=220 \
  TRUE "Una o più canzoni" FALSE "Una o più cartelle") || exit 0

canzoni=()
if [[ $scelta == "Una o più canzoni" ]]; then
  elenco=$(zenity --file-selection --multiple --separator=$'\n' --title="Tablatura: scegli le canzoni" \
    --file-filter="Audio | *.mp3 *.flac *.wav *.ogg *.m4a *.MP3 *.FLAC *.WAV *.OGG *.M4A") || exit 0
  mapfile -t canzoni <<<"$elenco"
else
  elenco=$(zenity --file-selection --directory --multiple --separator=$'\n' \
    --title="Tablatura: scegli le cartelle") || exit 0
  mapfile -t cartelle <<<"$elenco"
  # Le canzoni anche nelle sottocartelle, ma non quelle già separate da Demucs.
  mapfile -t canzoni < <(find "${cartelle[@]}" -type f -iregex "$audio" \
    -not -path '*-tablatura/*' | sort)
fi

if [[ ${#canzoni[@]} -eq 0 ]]; then
  zenity --info --title="Tablatura" --text="In quelle cartelle non ho trovato canzoni." --width=400
  exit 0
fi

strumento=$(zenity --list --radiolist --title="Tablatura" --text="Quale strumento?" \
  --column="" --column="Strumento" --height=280 \
  TRUE basso FALSE basso5 FALSE chitarra FALSE chitarra-dropd) || exit 0

opzioni=()
if zenity --question --title="Tablatura" --text="Trascrivo anche il testo cantato?" --ok-label="Sì" --cancel-label="No"; then
  opzioni+=(--testo)
  # Se la lasci indovinare, Whisper sbaglia facile (Billie Jean in portoghese).
  lingua=$(zenity --list --radiolist --title="Tablatura" --text="In che lingua si canta?" \
    --column="" --column="Codice" --column="Lingua" --print-column=2 --hide-column=2 --height=300 \
    TRUE en "Inglese" FALSE it "Italiano" FALSE es "Spagnolo" FALSE fr "Francese" FALSE "" "La indovina lui") || exit 0
  [[ -n $lingua ]] && opzioni+=(--lingua "$lingua")
fi
[[ $strumento == chitarra* ]] && opzioni+=(--polifonico)

registri=$(mktemp -d)
totale=${#canzoni[@]}
(
  for i in "${!canzoni[@]}"; do
    canzone=${canzoni[$i]}
    registro="$registri/$i.log"
    echo "$(( i * 100 / totale ))"
    echo "# $((i + 1)) di $totale: $(basename "$canzone")"
    .venv-311/bin/python -m tablatura "$canzone" --strumento "$strumento" "${opzioni[@]}" >"$registro" 2>&1
    echo $? >"$registri/$i.esito"
  done
  echo 100
) | zenity --progress --auto-close --title="Tablatura" --text="Comincio…" --width=500
# Se la barra è stata annullata, il ciclo si ferma alla canzone in corso.

pagine=()
righe=()
for i in "${!canzoni[@]}"; do
  nome=$(basename "${canzoni[$i]}")
  if [[ ! -f "$registri/$i.esito" ]]; then
    righe+=("non fatta" "$nome" "")
  elif [[ $(cat "$registri/$i.esito") -eq 0 ]]; then
    pagina=$(grep -oP '^pagina:\s+\K.*' "$registri/$i.log")
    pagine+=("$pagina")
    righe+=("fatta" "$nome" "${pagina:-$registri/$i.log}")
  else
    righe+=("errore" "$nome" "$registri/$i.log")
  fi
done

# Una canzone sola: si apre la sua pagina e basta.
if [[ $totale -eq 1 && ${#pagine[@]} -eq 1 && -n ${pagine[0]} ]]; then
  xdg-open "${pagine[0]}"
  exit 0
fi

# Più canzoni: l'elenco resta aperto, e ogni doppio clic apre una pagina (o l'errore).
while scelto=$(zenity --list --title="Tablatura: ${#pagine[@]} su $totale fatte" \
  --text="Doppio clic su una canzone per aprirla." --width=700 --height=450 \
  --column="Esito" --column="Canzone" --column="File" --print-column=3 --hide-column=3 \
  "${righe[@]}"); do
  [[ -z $scelto ]] && continue
  if [[ $scelto == *.log ]]; then
    zenity --text-info --title="Tablatura: cosa è andato storto" --filename="$scelto" --width=700 --height=450
  else
    xdg-open "$scelto"
  fi
done
