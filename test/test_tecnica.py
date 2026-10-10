import numpy as np

from tablatura.tecnica import Evento, dalle_curve

PASSO = 0.01


def curve(pezzi, durata):
    """Una curva d'altezza e una d'attacchi: pezzi = (da, a, altezza o funzione, attacco)."""
    n = int(durata / PASSO)
    altezza = np.full(n, np.nan)
    attacchi = np.zeros(n)
    for da, a, alt, attacco in pezzi:
        i, j = int(da / PASSO), int(a / PASSO)
        t = np.arange(j - i) * PASSO
        altezza[i:j] = alt(t) if callable(alt) else alt
        attacchi[i] = attacco
    return altezza, attacchi


def test_legato_in_salita_e_in_discesa():
    # 5 pennata, 7 senza pennata (hammer), 5 senza pennata (pull), poi 5 pennata su un'altra nota.
    altezza, attacchi = curve([(0, .3, 45, 1), (.3, .6, 47, .1), (.6, .9, 45, .1), (1, 1.4, 40, 1)], 1.5)
    eventi = [Evento(0, 45, 1, .3), Evento(.3, 47, 1, .6), Evento(.6, 45, 1, .9), Evento(1, 40, 0, 1.4)]
    assert dalle_curve(eventi, altezza, attacchi, PASSO) == ["", "h", "p", ""]


def test_con_la_pennata_non_e_legato():
    altezza, attacchi = curve([(0, .3, 45, 1), (.3, .6, 47, 1), (.6, .9, 45, 1)], 1.0)
    eventi = [Evento(0, 45, 1, .3), Evento(.3, 47, 1, .6), Evento(.6, 45, 1, .9)]
    assert dalle_curve(eventi, altezza, attacchi, PASSO) == ["", "", ""]


def test_glissato():
    # Da 45 a 50 scivolando per 100 ms, senza pennata.
    altezza, attacchi = curve([(0, .3, 45, 1), (.3, .4, lambda t: 45 + 50 * t, 0), (.4, .8, 50, 0)], 1.0)
    eventi = [Evento(0, 45, 1, .3), Evento(.4, 50, 1, .8)]
    assert dalle_curve(eventi, altezza, attacchi, PASSO) == ["", "/"]


def test_bending():
    altezza, attacchi = curve([(0, .1, 50, 1), (.1, .3, lambda t: 50 + 5 * t, 0), (.3, .7, 51, 0)], 0.8)
    eventi = [Evento(0, 50, 2, .7)]
    assert dalle_curve(eventi, altezza, attacchi, PASSO) == ["b"]


def test_vibrato():
    altezza, attacchi = curve([(0, 1.0, lambda t: 50 + 0.3 * np.sin(2 * np.pi * 6 * t), 1)], 1.1)
    eventi = [Evento(0, 50, 2, 1.0)]
    assert dalle_curve(eventi, altezza, attacchi, PASSO) == ["~"]


def test_trillo():
    pezzi, eventi = [], []
    for k in range(6):
        nota = 50 if k % 2 == 0 else 52
        pezzi.append((k * .1, (k + 1) * .1, nota, 1 if k == 0 else .05))
        eventi.append(Evento(k * .1, nota, 2, (k + 1) * .1))
    altezza, attacchi = curve(pezzi, 0.7)
    assert dalle_curve(eventi, altezza, attacchi, PASSO) == ["tr", "h", "p", "h", "p", "h"]


def test_note_dai_colpi_ritrova_i_ribattuti():
    from tablatura.strumenti import Nota
    from tablatura.tecnica import note_dai_colpi

    # Quattro Re ribattuti: il trascrittore ne ha scritti due, gli attacchi sono quattro.
    altezza = np.full(200, 38.0)
    attacchi = np.zeros(200)
    for i in (10, 50, 90, 130):
        attacchi[i] = 1.0
    scritte = [Nota(38, 0.10, 0.3), Nota(38, 0.90, 0.3)]
    tutte = note_dai_colpi(scritte, altezza, attacchi, 0.01, 26, 67, percentile=0)
    assert [round(n.inizio, 2) for n in tutte] == [0.1, 0.5, 0.9, 1.3]
    assert all(n.midi == 38 for n in tutte)
