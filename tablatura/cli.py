"""La riga di comando: una canzone dentro, una tablatura fuori.

    python -m tablatura canzone.flac
    python -m tablatura canzone.flac --strumento chitarra --bpm 128
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .diteggiatura import diteggia, fuori_estensione
from .disegno import a_proporzione, disegna_battute, in_griglia
from .ostinato import analizza, riassunto
from .ottava import da_file, sposta
from .pulizia import ripulisci
from .separa import TRACCIA, separa
from .strumenti import STRUMENTI
from .trascrivi import trascrivi
from .visore import dati, scrivi


def argomenti(righe: list[str] | None = None) -> argparse.Namespace:
    lettore = argparse.ArgumentParser(
        prog="tablatura",
        description="Da una canzone alla tablatura di uno strumento, tutto sul tuo computer.",
    )
    lettore.add_argument("canzone", type=Path, help="il file mp3, flac o wav di partenza")
    lettore.add_argument(
        "--strumento", choices=sorted(STRUMENTI), default="basso", help="quale strumento tirare fuori"
    )
    lettore.add_argument("--dove", type=Path, help="cartella dei risultati (default: accanto alla canzone)")
    lettore.add_argument("--bpm", type=float, help="il metronomo, se lo sai; altrimenti lo cerca da solo")
    lettore.add_argument("--partenza", type=float, help="secondo in cui cade il primo movimento")
    lettore.add_argument(
        "--ottava", type=int, help="sposta la linea di tante ottave, invece di indovinarle"
    )
    lettore.add_argument("--tutto", action="store_true", help="stampa tutte le battute, anche se il giro si ripete")
    lettore.add_argument("--senza-battute", action="store_true", help="niente griglia: spazio in proporzione al tempo")
    lettore.add_argument("--polifonico", action="store_true", help="tiene gli accordi (per la chitarra)")
    lettore.add_argument("--gia-separato", type=Path, help="salta Demucs e usa questa traccia già isolata")
    return lettore.parse_args(righe)


def main(righe: list[str] | None = None) -> int:
    opzioni = argomenti(righe)
    if not opzioni.canzone.exists():
        print(f"non trovo {opzioni.canzone}", file=sys.stderr)
        return 1

    strumento = STRUMENTI[opzioni.strumento]
    dove = opzioni.dove or opzioni.canzone.parent / f"{opzioni.canzone.stem}-tablatura"
    dove.mkdir(parents=True, exist_ok=True)

    tracce: dict[str, Path] = {}
    if opzioni.gia_separato:
        isolata = opzioni.gia_separato
        tracce = {opzioni.strumento: isolata}
    else:
        nome_traccia, modello = TRACCIA[opzioni.strumento]
        print(f"separo le tracce con {modello} (la prima volta scarica il modello)…")
        tracce = separa(opzioni.canzone, dove, modello)
        if nome_traccia not in tracce:
            print(f"il modello non ha una traccia «{nome_traccia}»", file=sys.stderr)
            return 1
        isolata = tracce[nome_traccia]

    bpm, partenza = opzioni.bpm, opzioni.partenza
    if bpm is None and not opzioni.senza_battute:
        from .metronomo import metronomo

        print("cerco il metronomo…")
        bpm, trovata = metronomo(opzioni.canzone)
        partenza = trovata if partenza is None else partenza
        print(f"  {bpm} bpm, primo battito a {partenza}s")
    partenza = partenza or 0.0

    print(f"trascrivo il {strumento.nome}…")
    grezze = trascrivi(isolata, strumento)
    note = ripulisci(grezze, una_nota_alla_volta=not opzioni.polifonico)
    print(f"  {len(grezze)} note grezze → {len(note)} dopo la pulizia")

    if opzioni.ottava:
        note = sposta(note, opzioni.ottava)
        print(f"  linea spostata di {opzioni.ottava:+d} ottave, come chiesto")
    elif note and opzioni.ottava is None:
        # La fondamentale di un basso è debole: il trascrittore si aggancia
        # spesso alla seconda armonica e scrive tutto un'ottava sopra.
        ottave = da_file(isolata, note, strumento)
        if ottave:
            note = sposta(note, ottave)
            print("  le armoniche dicono che era scritta un'ottava sopra: abbassata")

    if bpm and opzioni.bpm is None and note:
        from .metronomo import affina

        bpm, partenza = affina([n.inizio for n in note], bpm, partenza)
        print(f"  tempo affinato sulle note: {bpm} bpm")

    scartate = fuori_estensione(note, strumento)
    if scartate:
        print(f"  {len(scartate)} note fuori dall'estensione di un {strumento.nome}: scartate")

    suonate = diteggia(note, strumento)
    if not suonate:
        print("non è uscita nessuna nota: prova un altro strumento o un'altra traccia", file=sys.stderr)
        return 1

    print()
    if opzioni.senza_battute or not bpm:
        tab = a_proporzione(suonate, strumento)
        print(tab)
    else:
        battute = in_griglia(suonate, bpm, partenza=partenza)
        tab = disegna_battute(battute, strumento)
        trovato = None if opzioni.tutto else analizza(battute)
        if trovato is None:
            print(tab)
        else:
            # Duecento battute uguali non si leggono: si mostra il giro, e
            # solo i punti in cui il bassista si è mosso.
            giro, inizio = trovato
            print(riassunto(giro))
            print()
            print(disegna_battute(battute[inizio : inizio + giro.periodo], strumento))
            for eccezione in giro.eccezioni:
                print(f"\nbattuta {eccezione + 1}:")
                print(disegna_battute(battute[eccezione : eccezione + 1], strumento))
            print("\nLa tablatura intera è nel file; con --tutto la stampa qui.")

    testo = dove / f"{opzioni.canzone.stem}-{opzioni.strumento}.txt"
    testo.write_text(f"{opzioni.canzone.stem} — {strumento.nome}\n\n{tab}\n", encoding="utf-8")

    if bpm:
        pagina = dove / "tablatura.html"
        scrivi(
            pagina,
            titolo=opzioni.canzone.stem,
            strumento=strumento,
            bpm=bpm,
            tab=dati(suonate, strumento, bpm=bpm, partenza=partenza),
            tracce=[{"nome": nome, "file": file.name} for nome, file in sorted(tracce.items())],
        )
        print(f"\ntablatura: {testo}\npagina:    {pagina}")
    else:
        print(f"\ntablatura: {testo}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
