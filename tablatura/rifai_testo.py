"""Rifà solo il testo di una canzone già lavorata, in un'altra lingua.

    python -m tablatura.rifai_testo <cartella della canzone> <lingua> [modello]

Serve quando la lingua era sbagliata: con «inglese» su una canzone in
napoletano Whisper non trascrive, traduce e inventa. Si riascolta la traccia
della voce già separata, e si cambiano solo le parole in leggio.json: la
tablatura e gli accordi restano come sono.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from .testo import ascolta

# Per rifare il testo si usa un modello più grande di quello del primo giro:
# lo si fa su una canzone sola, e il dialetto ha bisogno di orecchio.
MODELLO = "large-v3"


def main(argomenti: list[str]) -> int:
    if len(argomenti) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    cartella, lingua = Path(argomenti[0]), argomenti[1] or None
    modello = argomenti[2] if len(argomenti) > 2 else MODELLO
    voce = cartella / "vocals.wav"
    descrizione = cartella / "leggio.json"
    if not voce.is_file() or not descrizione.is_file():
        print(f"in {cartella} manca la voce separata o leggio.json", file=sys.stderr)
        return 1
    print(f"trascrivo il testo con {modello} (la prima volta scarica il modello)…", flush=True)
    parole = ascolta(voce, lingua, modello)
    tab = json.loads(descrizione.read_text(encoding="utf-8"))
    tab["parole"] = [{"testo": p.testo, "quando": round(p.inizio, 3)} for p in parole]
    descrizione.write_text(json.dumps(tab), encoding="utf-8")
    print(f"  {len(parole)} parole", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
