"""Dalle tablature di testo (quelle dei siti, coi trattini) a una partitura alphaTex.

    G|-------------------|
    D|--5----------------|
    A|---3-3-033-5-------|
    E|-------------3(3)--|

Il testo dice quali tasti, non quanto durano: il ritmo si ricava dagli spazi
fra un numero e il successivo, in proporzione alla larghezza della battuta.
È approssimato, ma per la sincronia col disco bastano battute e note giuste.
Le indicazioni come «verse play 12 times» e «play bridge, play verse…»
diventano ripetizioni e ordine delle sezioni.
"""

from __future__ import annotations

import re

NOTE_CORDA = {"G": "G2", "D": "D2", "A": "A1", "E": "E1", "B": "B0", "C": "C3"}
RIGO = re.compile(r"^\s*([A-Ga-g][#b]?)\s*[|:]")
VOLTE = re.compile(r"(\d+)\s*(x|times|volte)\b|x\s*(\d+)", re.I)


def _sistemi(righe: list[str]) -> list[tuple[int, list[str], list[str]]]:
    """(riga d'inizio, nomi delle corde, righi) di ogni gruppo di righi consecutivi."""
    fuori, i = [], 0
    while i < len(righe):
        if RIGO.match(righe[i]):
            j = i
            while j < len(righe) and RIGO.match(righe[j]):
                j += 1
            if j - i >= 4:
                gruppo = righe[i:j]
                fuori.append((i, [RIGO.match(r).group(1).upper() for r in gruppo], gruppo))
            i = j
        else:
            i += 1
    return fuori


def _battute(righi: list[str]) -> list[list[tuple[float, list[tuple[int, int]]]]]:
    """Ogni battuta: lista di (posizione 0-1 nella battuta, [(corda dall'alto, tasto)])."""
    corpi = [re.sub(r"^\s*[A-Ga-g][#b]?\s*[|:]", "", r).rstrip() for r in righi]
    lunghezza = max(len(c) for c in corpi)
    corpi = [c.ljust(lunghezza, "-") for c in corpi]
    # Le stanghette: dove almeno metà dei righi ha «|».
    stanghette = [k for k in range(lunghezza) if sum(c[k] == "|" for c in corpi) * 2 >= len(corpi)]
    bordi = [-1] + stanghette + ([lunghezza] if not stanghette or stanghette[-1] < lunghezza - 1 else [])
    battute = []
    for a, b in zip(bordi, bordi[1:]):
        if b - a <= 2:
            continue
        colonne: dict[int, list[tuple[int, int]]] = {}
        for corda, c in enumerate(corpi):
            for m in re.finditer(r"\d+", c[a + 1:b]):
                # «033» o «5588» sono tasti attaccati, uno per colonna: un tasto
                # sopra il 24 non esiste, quindi le cifre si separano.
                if int(m.group()) > 24:
                    for k, cifra in enumerate(m.group()):
                        colonne.setdefault(m.start() + k, []).append((corda + 1, int(cifra)))
                else:
                    colonne.setdefault(m.start(), []).append((corda + 1, int(m.group())))
        larghezza = b - a - 1
        battute.append([(pos / larghezza, note) for pos, note in sorted(colonne.items())])
    return battute


def _alphatex_battuta(battuta, griglia: int = 32) -> str:
    """Una battuta di 4/4 in alphaTex: ogni nota dura fino alla successiva.

    Le posizioni vanno su una griglia di trentaduesimi, sempre in avanti e mai
    oltre la battuta: così la somma delle durate fa esattamente una battuta.
    """
    if not battuta:
        return "r.1"
    n = len(battuta)
    posizioni = []
    for k, (p, _) in enumerate(battuta):
        pos = round(p * griglia)
        if posizioni:
            pos = max(pos, posizioni[-1] + 1)
        posizioni.append(min(pos, griglia - (n - k)))
    posizioni.append(griglia)
    pezzi = []
    if posizioni[0] > 0:
        pezzi += [f"r.{d}" for d in _scomponi(posizioni[0], griglia)]
    for k, (_, note) in enumerate(battuta):
        testo = " ".join(f"{t}.{c}" for c, t in note)
        nota = f"({testo})" if len(note) > 1 else testo
        for d in _scomponi(posizioni[k + 1] - posizioni[k], griglia):
            pezzi.append(f"{nota}.{d}")
            nota = "r"   # il resto dello spazio è silenzio
    return " ".join(pezzi)


def _scomponi(spazio: int, griglia: int) -> list[int]:
    """Uno spazio sulla griglia, come somma di durate scrivibili (intera, metà, quarto…)."""
    fuori, valore = [], griglia
    while spazio > 0 and valore >= 1:
        while spazio >= valore:
            fuori.append(griglia // valore)
            spazio -= valore
        valore //= 2
    return fuori


def converti(testo: str, titolo: str = "", tempo: int = 100) -> str:
    """Tutta la tablatura di testo in alphaTex, sezioni ripetute e in ordine."""
    righe = testo.splitlines()
    sistemi = _sistemi(righe)
    if not sistemi:
        raise ValueError("non trovo righi di tablatura (righe che cominciano con G|, D|, A|, E|…)")
    sezioni = []   # (nome, volte, battute)
    for inizio, nomi, righi in sistemi:
        sopra = next((righe[k].strip() for k in range(inizio - 1, max(-1, inizio - 4), -1) if righe[k].strip()), "")
        m = VOLTE.search(sopra)
        volte = int(m.group(1) or m.group(3)) if m else 1
        nome = re.sub(r"\(.*?\)|play.*$|\d+\s*(x|times).*$", "", sopra, flags=re.I).strip(" :-").lower() or f"parte {len(sezioni) + 1}"
        sezioni.append((nome, min(volte, 32), _battute(righi), nomi))
    # L'ordine: le sezioni come sono scritte, poi l'eventuale «play bridge, play verse…».
    ordine = [s[0] for s in sezioni]
    coda = re.findall(r"play\s+(?:the\s+)?([a-z]+)", " ".join(r for r in righe[sistemi[-1][0]:] if not RIGO.match(r)), re.I)
    per_nome = {s[0].split()[0]: s for s in sezioni}
    ordine += [c.lower() for c in coda if c.lower() in per_nome]
    nomi_corde = sezioni[0][3]
    accordatura = " ".join(NOTE_CORDA.get(n, "E1") for n in nomi_corde)
    battute_tex = []
    for nome in ordine:
        sezione = per_nome.get(nome.split()[0])
        if not sezione:
            continue
        _, volte, battute, _ = sezione
        for _ in range(volte):
            battute_tex += [_alphatex_battuta(b) for b in battute]
    # Gli argomenti dell'accordatura fra parentesi: senza, alphaTab prende la
    # prima nota della battuta («r.8») come parte dell'accordatura.
    testa = f'\\title "{titolo}"\n\\tempo {tempo}\n\\track "Bass"\n\\instrument 33\n\\staff {{tabs}}\n\\tuning ({accordatura})\n'
    return testa + " |\n".join(battute_tex) + " |\n"
