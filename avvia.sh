#!/usr/bin/env bash
# Il programma dell'icona: Importa (lavora canzoni nuove) o Apri (quelle già fatte).
cd "$(dirname "$(readlink -f "$0")")" || exit 1

# Una sola alla volta: un secondo clic non ne apre un'altra.
exec 9>"${XDG_RUNTIME_DIR:-/tmp}/tablatura.lock"
if ! flock -n 9; then
  notify-send -i audio-x-generic "Tablatura" "È già aperta: guarda le sue finestre."
  exit 0
fi

audio='.*\.\(mp3\|flac\|wav\|ogg\|m4a\)'
# Le canzoni lavorate stanno tutte qui, una cartella per album, così non si
# mescolano con la musica vera e propria.
TAB="$(xdg-user-dir MUSIC 2>/dev/null || echo "$HOME/Musica")/tab"
filtro="Audio | *.mp3 *.flac *.wav *.ogg *.m4a *.MP3 *.FLAC *.WAV *.OGG *.M4A"

apri_pagina() { xdg-open "$1" 9>&- >/dev/null 2>&1; }

# Dove vanno i risultati di una canzone: tab/<album>/<canzone>.
cartella_di() {
  local f=$1
  echo "$TAB/$(basename "$(dirname "$f")")/$(basename "${f%.*}")"
}

# Canzoni o cartella? Riempie l'array «scelte» (file, oppure una cartella).
scegli() {
  local titolo=$1 cosa elenco
  cosa=$(zenity --list --radiolist --title="Tablatura: $titolo" --text="Cosa scegli?" \
    --column="" --column="Cosa" --height=220 \
    TRUE "Una o più canzoni" FALSE "Una cartella") || return 1
  if [[ $cosa == "Una o più canzoni" ]]; then
    elenco=$(zenity --file-selection --multiple --separator=$'\n' \
      --title="Tablatura: $titolo le canzoni" --file-filter="$filtro") || return 1
    mapfile -t scelte <<<"$elenco"
    tipo=canzoni
  else
    elenco=$(zenity --file-selection --directory --title="Tablatura: $titolo la cartella") || return 1
    scelte=("$elenco")
    tipo=cartella
  fi
}

# L'elenco che resta aperto: doppio clic su una riga apre la pagina (o l'errore).
elenco_pagine() {
  local titolo=$1; shift
  local scelto
  while scelto=$(zenity --list --title="Tablatura: $titolo" \
    --text="Doppio clic su una canzone per aprirla. Chiudi per tornare al menu." --width=750 --height=480 \
    --column="Esito" --column="Canzone" --column="File" --print-column=3 --hide-column=3 \
    "$@"); do
    [[ -z $scelto ]] && continue
    if [[ $scelto == *.log ]]; then
      zenity --text-info --title="Tablatura: cosa è andato storto" --filename="$scelto" --width=700 --height=450
    else
      apri_pagina "$scelto"
    fi
  done
}

importa() {
  scegli "importa" || return
  local canzoni=()
  if [[ $tipo == canzoni ]]; then
    canzoni=("${scelte[@]}")
  else
    # Le canzoni anche nelle sottocartelle, ma non quelle già separate da Demucs.
    mapfile -t canzoni < <(find "${scelte[0]}" -type f -iregex "$audio" -not -path '*-tablatura/*' -not -path "$TAB/*" | sort)
  fi
  if [[ ${#canzoni[@]} -eq 0 ]]; then
    zenity --info --title="Tablatura" --text="In quella cartella non ho trovato canzoni." --width=400
    return
  fi

  local strumento lingua
  strumento=$(zenity --list --radiolist --title="Tablatura" --text="Quale strumento?" \
    --column="" --column="Strumento" --height=280 \
    TRUE basso FALSE basso5 FALSE chitarra FALSE chitarra-dropd) || return

  local opzioni=()
  if zenity --question --title="Tablatura" --text="Trascrivo anche il testo cantato?" --ok-label="Sì" --cancel-label="No"; then
    opzioni+=(--testo)
    # Se la lasci indovinare, Whisper sbaglia facile (Billie Jean in portoghese).
    lingua=$(zenity --list --radiolist --title="Tablatura" --text="In che lingua si canta?" \
      --column="" --column="Codice" --column="Lingua" --print-column=2 --hide-column=2 --height=300 \
      TRUE en "Inglese" FALSE it "Italiano" FALSE es "Spagnolo" FALSE fr "Francese" FALSE "" "La indovina lui") || return
    [[ -n $lingua ]] && opzioni+=(--lingua "$lingua")
  fi
  [[ $strumento == chitarra* ]] && opzioni+=(--polifonico)

  local registri totale
  registri=$(mktemp -d)
  totale=${#canzoni[@]}
  (
    for i in "${!canzoni[@]}"; do
      echo "$(( i * 100 / totale ))"
      echo "# $((i + 1)) di $totale: $(basename "${canzoni[$i]}")"
      .venv-311/bin/python -m tablatura "${canzoni[$i]}" --strumento "$strumento" "${opzioni[@]}" \
        --dove "$(cartella_di "${canzoni[$i]}")" \
        >"$registri/$i.log" 2>&1
      echo $? >"$registri/$i.esito"
    done
    echo 100
  ) | zenity --progress --auto-close --title="Tablatura" --text="Comincio…" --width=500
  # Se la barra è stata annullata, il ciclo si ferma alla canzone in corso.

  local pagine=() righe=() nome pagina
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

  if [[ $totale -eq 1 && ${#pagine[@]} -eq 1 && -n ${pagine[0]} ]]; then
    apri_pagina "${pagine[0]}"
  else
    elenco_pagine "${#pagine[@]} su $totale fatte" "${righe[@]}"
  fi
}

apri() {
  local righe=() p canzone album
  while IFS= read -r p; do
    canzone=$(dirname "$p"); album=$(dirname "$canzone")
    righe+=("$(basename "$album")" "$(basename "$canzone")" "$p")
  done < <(find "$TAB" -mindepth 3 -maxdepth 3 -type f -name tablatura.html 2>/dev/null | sort)
  if [[ ${#righe[@]} -eq 0 ]]; then
    zenity --info --title="Tablatura" --width=420 \
      --text="Non c'è ancora nessuna canzone lavorata: usa Importa."
    return
  fi
  local scelte_pagine scelte_elenco
  while scelte_pagine=$(zenity --list --multiple --separator=$'\n' \
    --title="Tablatura: $(( ${#righe[@]} / 3 )) canzoni" \
    --text="Seleziona una o più canzoni (Ctrl o Maiusc per sceglierne più di una), poi Apri.\nChiudi per tornare al menu." \
    --ok-label="Apri" --cancel-label="Menu" --width=800 --height=520 \
    --column="Album" --column="Canzone" --column="File" --print-column=3 --hide-column=3 \
    "${righe[@]}"); do
    mapfile -t scelte_elenco <<<"$scelte_pagine"
    for p in "${scelte_elenco[@]}"; do [[ -n $p ]] && apri_pagina "$p"; done
  done
}

# Il menu: resta aperto finché non lo chiudi.
while azione=$(zenity --list --title="Tablatura" --text="Cosa vuoi fare?" \
  --column="Azione" --column="" --width=420 --height=240 \
  "Importa" "lavora canzoni nuove" \
  "Apri" "le canzoni già fatte, in Musica/tab"); do
  case $azione in
    Importa) importa ;;
    Apri) apri ;;
  esac
done
