"""Prove sulla parte che non dipende da nessun modello: note dentro, tab fuori."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tablatura.diteggiatura import diteggia, fuori_estensione, posizioni_possibili
from tablatura.metronomo import affina
from tablatura.disegno import a_battute, a_proporzione, allinea_partenza, in_griglia
from tablatura.pulizia import (
    monofonico,
    ripulisci,
    scarta_armonici,
    scarta_briciole,
    unisci_ripetizioni,
)
from tablatura.strumenti import BASSO, Nota


def _riff(altezze, passo=0.5):
    return [Nota(midi=m, inizio=i * passo, durata=passo * 0.9) for i, m in enumerate(altezze)]


def test_stessa_nota_su_piu_corde():
    # Il Sol2 sul basso si prende in quattro modi, corda a vuoto compresa.
    posizioni = posizioni_possibili(43, BASSO)
    assert [(p.corda, p.tasto) for p in posizioni] == [(0, 15), (1, 10), (2, 5), (3, 0)]


def test_note_fuori_estensione():
    assert fuori_estensione([Nota(20, 0.0, 1.0)], BASSO)  # sotto il Mi basso
    assert not fuori_estensione([Nota(28, 0.0, 1.0)], BASSO)
    assert diteggia([Nota(20, 0.0, 1.0), Nota(28, 1.0, 1.0)], BASSO) == diteggia(
        [Nota(28, 1.0, 1.0)], BASSO
    )


def test_la_mano_resta_ferma():
    # Un giro in Mi: deve restare in prima posizione, non salire al dodicesimo.
    suonate = diteggia(_riff([28, 31, 33, 35, 33, 31]), BASSO)
    assert len(suonate) == 6
    assert max(s.posizione.tasto for s in suonate) <= 5


def test_una_frase_alta_non_scende_a_forza():
    # Sopra il manico si sta in zona, senza rimbalzare fra corde lontane.
    suonate = diteggia(_riff([55, 57, 59, 57], passo=0.25), BASSO)
    tasti = [s.posizione.tasto for s in suonate]
    assert max(tasti) - min(tasti) <= 4


def test_la_pausa_lunga_lascia_spostare_la_mano():
    # Due frasi separate da cinque secondi: la seconda sceglie la sua comodità,
    # non l'inerzia della prima.
    # Il Sol4 sul basso esiste solo al ventiquattresimo: da lì la mano deve
    # tornare giù, e la fretta decide quanto.
    vicine = diteggia([Nota(67, 0.0, 0.05), Nota(44, 0.05, 0.2)], BASSO)
    lontane = diteggia([Nota(67, 0.0, 0.05), Nota(44, 5.0, 0.2)], BASSO)
    assert lontane[1].posizione.tasto < vicine[1].posizione.tasto


def test_via_le_briciole():
    note = [Nota(28, 0.0, 0.5), Nota(35, 0.6, 0.02)]
    assert scarta_briciole(note) == [note[0]]


def test_la_coda_si_riattacca_alla_nota():
    # Numeri veri: un frammento da 80 ms attaccato alla nota che lo segue.
    unite = unisci_ripetizioni([Nota(28, 4.14, 0.08), Nota(28, 4.22, 0.55)])
    assert len(unite) == 1
    assert unite[0].inizio == 4.14
    assert round(unite[0].durata, 2) == 0.63


def test_due_note_uguali_restano_due():
    # Mi, poi ancora Mi: due pulsazioni del pezzo, non una nota lunga.
    ripetute = [Nota(28, 0.01, 0.55, 0.66), Nota(28, 0.57, 0.58, 0.66)]
    assert unisci_ripetizioni(ripetute) == ripetute


def test_una_nota_lunga_non_mangia_quella_dopo():
    # Il basso tiene la nota, e intanto entra la successiva: sono due note.
    tenute = monofonico([Nota(28, 0.0, 2.0, 0.9), Nota(33, 1.0, 1.0, 0.5)])
    assert [n.midi for n in tenute] == [28, 33]


def test_il_fantasma_di_ottava_sparisce():
    # Il modello raddoppia la nota un'ottava sopra, più corta e più debole.
    vera = Nota(28, 0.0, 0.5, intensita=0.9)
    fantasma = Nota(40, 0.02, 0.1, intensita=0.3)
    assert monofonico([vera, fantasma]) == [vera]


def test_le_note_non_si_accavallano():
    tenute = monofonico([Nota(28, 0.0, 2.0), Nota(33, 1.0, 1.0)])
    assert len(tenute) == 2
    assert tenute[0].fine == tenute[1].inizio


def test_le_armoniche_del_basso_spariscono():
    # Numeri veri, presi da una trascrizione: sotto il Mi1 pieno il modello
    # scrive anche la doppia ottava e la diciassettesima, più deboli e corte.
    fondamentale = Nota(28, 0.01, 0.55, 0.66)
    grezze = [fondamentale, Nota(56, 0.03, 0.39, 0.36), Nota(52, 0.05, 0.38, 0.36)]
    assert scarta_armonici(grezze) == [fondamentale]


def test_un_salto_di_ottava_vero_resta():
    # Stesso intervallo, ma la nota sopra è piena quanto quella sotto e parte
    # quando la prima è finita: è musica, non un fantasma.
    basse = Nota(28, 0.0, 0.5, 0.7)
    alta = Nota(40, 0.5, 0.5, 0.7)
    assert scarta_armonici([basse, alta]) == [basse, alta]


def test_ripulisci_fa_le_quattro_cose():
    grezze = [
        Nota(28, 0.00, 0.30, 0.9),
        Nota(28, 0.32, 0.10, 0.9),   # la coda della stessa nota
        Nota(40, 0.10, 0.03, 0.2),   # briciola un'ottava sopra
        Nota(33, 1.00, 0.40, 0.8),
    ]
    pulite = ripulisci(grezze)
    assert [n.midi for n in pulite] == [28, 33]


def test_griglia_quantizza_sui_sedicesimi():
    # A 120 bpm il sedicesimo dura 0.125 s: 0.130 va nella casella 1.
    suonate = diteggia([Nota(28, 0.0, 0.1), Nota(33, 0.130, 0.1)], BASSO)
    battute = in_griglia(suonate, bpm=120)
    assert len(battute) == 1
    assert battute[0][0] and battute[0][1]
    assert not battute[0][2]


def test_il_primo_movimento_arretra_prima_della_musica():
    # A 100 bpm la battuta dura 2.4 s: un battito trovato a 0.63 va riportato
    # indietro di una battuta intera, non spostato a caso.
    assert round(allinea_partenza(0.627, 0.01, bpm=100), 3) == -1.773
    # Se invece precede già la musica, non si tocca.
    assert allinea_partenza(0.0, 0.5, bpm=100) == 0.0


def test_la_griglia_non_accatasta_le_note_iniziali():
    # Note in quarti a 100 bpm, con il battito trovato in ritardo: devono
    # restare distanti quattro sedicesimi l'una dall'altra.
    note = [Nota(28, 0.6 * i, 0.5) for i in range(4)]
    battute = in_griglia(diteggia(note, BASSO), bpm=100, partenza=0.627)
    piene = [
        b * len(battuta) + i
        for b, battuta in enumerate(battute)
        for i, colonna in enumerate(battuta)
        if colonna
    ]
    assert len(piene) == 4
    assert [b - a for a, b in zip(piene, piene[1:])] == [4, 4, 4]


def test_il_tempo_si_affina_sulle_note():
    # Quarti veri a 100 bpm con un po' di tremolio negli attacchi, e un tempo
    # di partenza sbagliato dello 0,6%: deve tornare vicino a 100.
    tremolio = [0.01, -0.03, 0.01, 0.02, -0.02, 0.01, -0.01, 0.0]
    inizi = [round(0.6 * i + t, 3) for i, t in enumerate(tremolio)]
    bpm, partenza = affina(inizi, bpm=99.38, partenza=0.0)
    assert abs(bpm - 100) < 1.0
    # E con quel tempo le note cadono a quattro sedicesimi l'una dall'altra.
    suonate = diteggia([Nota(28, i, 0.4) for i in inizi], BASSO)
    battute = in_griglia(suonate, bpm=bpm, partenza=partenza)
    piene = [
        b * len(battuta) + i
        for b, battuta in enumerate(battute)
        for i, colonna in enumerate(battuta)
        if colonna
    ]
    assert [b - a for a, b in zip(piene, piene[1:])] == [4] * 7


def test_il_disegno_ha_una_riga_per_corda():
    suonate = diteggia(_riff([28, 31, 33]), BASSO)
    tab = a_battute(suonate, BASSO, bpm=120)
    righe = tab.splitlines()
    assert len(righe) == 4
    assert righe[0].startswith("G|") and righe[-1].startswith("E|")
    assert all(riga.count("|") >= 2 for riga in righe)


def test_senza_metronomo_si_disegna_lo_stesso():
    tab = a_proporzione(diteggia(_riff([28, 31, 33]), BASSO), BASSO)
    assert len(tab.splitlines()) == 4
    assert "(nessuna nota)" not in tab


def test_niente_note_niente_tab():
    assert a_battute([], BASSO, bpm=120) == "(nessuna nota)"
    assert a_proporzione([], BASSO) == "(nessuna nota)"


# --- il giro che si ripete -------------------------------------------------

from tablatura.ostinato import analizza, cerca, rappresentativo, riassunto, somiglianza


def _battuta(note, celle=16):
    """Una battuta da (cella, corda, tasto)."""
    colonne = [{} for _ in range(celle)]
    for cella, corda, tasto in note:
        colonne[cella][corda] = tasto
    return colonne


# Sei note che tornano: la forma di Papa Was a Rollin' Stone o di Walking
# on the Moon, che è il caso per cui serve tutto questo.
SEI_NOTE = [(0, 0, 0), (3, 0, 0), (6, 1, 2), (8, 1, 0), (11, 0, 3), (14, 0, 0)]


def test_due_battute_quasi_uguali_sono_la_stessa():
    spostata = SEI_NOTE[:-1] + [(15, 0, 0)]  # una nota un sedicesimo più in là
    assert somiglianza(_battuta(SEI_NOTE), _battuta(spostata)) == 1.0
    assert somiglianza(_battuta(SEI_NOTE), _battuta(SEI_NOTE)) == 1.0
    # Ma un tasto diverso è un'altra nota, per quanto vicina nel tempo.
    altro_tasto = SEI_NOTE[:-1] + [(14, 0, 5)]
    assert somiglianza(_battuta(SEI_NOTE), _battuta(altro_tasto)) < 0.9


def test_una_nota_non_ne_giustifica_due():
    # Due note uguali ravvicinate non si accoppiano entrambe alla stessa.
    una = _battuta([(4, 0, 3)])
    due = _battuta([(4, 0, 3), (5, 0, 3)])
    assert somiglianza(una, due) == 0.5


def test_trova_il_giro_di_una_battuta():
    battute = [_battuta(SEI_NOTE) for _ in range(24)]
    giro, inizio = analizza(battute)
    assert giro.periodo == 1
    assert inizio == 0
    assert giro.ripetizioni == 24
    assert giro.eccezioni == ()
    assert "Non cambia mai" in riassunto(giro)


def test_segnala_dove_il_bassista_cambia():
    battute = [_battuta(SEI_NOTE) for _ in range(24)]
    battute[11] = _battuta([(0, 2, 5), (4, 2, 7), (8, 2, 5), (12, 1, 3)])
    giro, _ = analizza(battute)
    assert giro.periodo == 1
    # Una battuta cambiata è una sola eccezione, non due.
    assert giro.eccezioni == (11,)
    assert "battute 12" in riassunto(giro)


def test_il_giro_da_mostrare_salta_l_attacco():
    attacco = _battuta([(12, 0, 0), (14, 0, 3)])
    battute = [attacco] + [_battuta(SEI_NOTE) for _ in range(20)]
    giro, inizio = analizza(battute)
    assert inizio == 1
    # L'attacco è l'unica battuta che non è il giro.
    assert giro.eccezioni == (0,)


def test_niente_giro_se_non_si_ripete_niente():
    battute = [_battuta([(i % 16, i % 4, i % 5)]) for i in range(20)]
    assert cerca(battute) is None
    assert analizza(battute) is None
    assert "Nessun giro" in riassunto(None)


def test_il_tempo_sbagliato_di_livello_si_raddrizza():
    # Il caso vero: su un ostinato sincopato il rilevatore sente 136 bpm dove
    # ce ne sono 100. Nessun ritocco fine può salvarlo; serve provare i livelli.
    celle = [0, 3, 6, 8, 11, 14]
    sedicesimo = 60.0 / 100 / 4
    inizi = [
        round(giro * 16 * sedicesimo + c * sedicesimo, 3)
        for giro in range(12)
        for c in celle
    ]
    bpm, _ = affina(inizi, bpm=136.0, partenza=0.0)
    assert abs(bpm - 100) < 2.0


def test_non_scavalca_il_livello_senza_una_prova_chiara():
    # Quarti puliti a 100: mezzo tempo li spiega altrettanto bene, ma non c'è
    # motivo di scegliere 50 invece del tempo rilevato.
    inizi = [round(0.6 * i, 3) for i in range(16)]
    bpm, _ = affina(inizi, bpm=99.38, partenza=0.0)
    assert abs(bpm - 100) < 2.0
