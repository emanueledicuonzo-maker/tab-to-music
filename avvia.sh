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
filtro="Audio | *.mp3 *.flac *.wav *.ogg *.m4a *.MP3 *.FLAC *.WAV *.OGG *.M4A"

apri_pagina() { xdg-open "$1" 9>&- >/dev/null 2>&1; }

# Dove sta la pagina di una canzone: accanto, nella cartella «nome-tablatura».
pagina_di() {
  local f=$1 nome
  nome=$(basename "${f%.*}")
  echo "$(dirname "$f")/$nome-tablatura/tablatura.html"
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
    mapfile -t canzoni < <(find "${scelte[0]}" -type f -iregex "$audio" -not -path '*-tablatura/*' | sort)
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
  scegli "apri" || return
  local pagine=() mancano=() righe=() p
  if [[ $tipo == canzoni ]]; then
    for f in "${scelte[@]}"; do
      p=$(pagina_di "$f")
      if [[ -f $p ]]; then pagine+=("$p"); else mancano+=("$(basename "$f")"); fi
    done
    for p in "${pagine[@]}"; do apri_pagina "$p"; done
    if [[ ${#mancano[@]} -gt 0 ]]; then
      zenity --info --title="Tablatura" --width=450 \
        --text="Queste non sono ancora state lavorate (usa Importa):\n\n$(printf '• %s\n' "${mancano[@]}")"
    fi
  else
    # Tutte le canzoni già fatte in quella cartella e nelle sottocartelle.
    while IFS= read -r p; do
      righe+=("fatta" "$(basename "$(dirname "$p")" | sed 's/-tablatura$//')" "$p")
    done < <(find "${scelte[0]}" -type f -path '*-tablatura/tablatura.html' | sort)
    if [[ ${#righe[@]} -eq 0 ]]; then
      zenity --info --title="Tablatura" --text="In quella cartella non c'è ancora nessuna canzone lavorata." --width=420
    elif [[ ${#righe[@]} -eq 3 ]]; then
      apri_pagina "${righe[2]}"
    else
      elenco_pagine "$(( ${#righe[@]} / 3 )) canzoni già fatte" "${righe[@]}"
    fi
  fi
}

# Il menu: resta aperto finché non lo chiudi.
while azione=$(zenity --list --title="Tablatura" --text="Cosa vuoi fare?" \
  --column="Azione" --column="" --width=420 --height=240 \
  "Importa" "lavora canzoni nuove" \
  "Apri" "riapri quelle già fatte"); do
  case $azione in
    Importa) importa ;;
    Apri) apri ;;
  esac
done
