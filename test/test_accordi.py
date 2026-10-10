import numpy as np

from tablatura.accordi import DITEGGIATURE, NOMI, TIPI, dal_croma


def croma_di(*note, rumore=0.0, rng=None):
    colonna = np.full(12, rumore)
    for n in note:
        colonna[n] += 1.0
    if rng is not None:
        colonna += rng.uniform(0, rumore, 12)
    return colonna


def test_giro_pop_riconosciuto():
    # C G Am F, quattro battiti ciascuno, con un po' di sporco.
    rng = np.random.default_rng(1)
    giro = [(0, 4, 7), (7, 11, 2), (9, 0, 4), (5, 9, 0)]
    colonne = [croma_di(*accordo, rumore=0.15, rng=rng) for accordo in giro for _ in range(4)]
    tempi = np.arange(len(colonne) + 1) * 0.5
    accordi = dal_croma(np.array(colonne).T, tempi)
    assert [a.nome for a in accordi] == ["C", "G", "Am", "F"]
    assert accordi[1].inizio == 2.0 and accordi[1].fine == 4.0


def test_una_nota_di_passaggio_non_cambia_accordo():
    colonne = [croma_di(9, 0, 4)] * 3 + [croma_di(2)] + [croma_di(9, 0, 4)] * 3
    accordi = dal_croma(np.array(colonne).T, np.arange(8) * 0.5)
    assert [a.nome for a in accordi] == ["Am"]


def test_settima():
    colonne = [croma_di(7, 11, 2, 5)] * 4
    accordi = dal_croma(np.array(colonne).T, np.arange(5) * 0.5)
    assert [a.nome for a in accordi] == ["G7"]


def test_silenzio_non_porta_accordi():
    colonne = [np.zeros(12)] * 4 + [croma_di(4, 7, 11)] * 4
    accordi = dal_croma(np.array(colonne).T, np.arange(9) * 0.5)
    assert [a.nome for a in accordi] == ["Em"]
    assert accordi[0].inizio == 2.0


def test_ogni_accordo_ha_la_sua_diteggiatura():
    for tipo in TIPI:
        for nome in NOMI:
            forma = DITEGGIATURE[nome + tipo]
            assert len(forma) == 6 and all(c == "x" or c.isdigit() for c in forma)


def test_i_cambi_si_agganciano_alla_mezza_battuta():
    from tablatura.accordi import Accordo, aggancia

    # Battuta di 2 secondi: la mezza battuta è 1. Un cambio a 2.4 va a 2,
    # uno a 4.6 va a 5, e un accordo da 5.1 a 5.4 era di passaggio.
    trovati = [Accordo("C", 0.0, 2.4), Accordo("G", 2.4, 4.6), Accordo("D", 5.1, 5.4), Accordo("Am", 4.6, 8.0)]
    trovati.sort(key=lambda a: a.inizio)
    fuori = aggancia(trovati, 0.0, 1.0)
    assert [(a.nome, a.inizio) for a in fuori] == [("C", 0.0), ("G", 2.0), ("Am", 5.0)]
