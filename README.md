# tablatura

Prendi una canzone, spegni gli strumenti che non ti interessano, e leggi la
tablatura di quello che ti interessa. Tutto sul tuo computer: nessun account,
nessun caricamento, nessun tasto per esportare o condividere.

```
canzone.flac
   └─ Demucs ────────► voce · basso · batteria · resto
                          └─ Basic Pitch ──► note
                                └─ pulizia ──► note vere
                                     └─ diteggiatura ──► corda e tasto
                                          └─ tablatura + pagina da leggere
```

## Come si usa

```bash
pip install -r requirements.txt
python -m tablatura canzone.flac                      # basso, che è quello che viene meglio
python -m tablatura canzone.flac --strumento chitarra # serve il modello a sei tracce
python -m tablatura canzone.flac --bpm 128            # se il tempo lo sai già, diglielo
```

Escono due cose, nella cartella `canzone-tablatura/`:

- un file di testo con la tablatura, da stampare o da tenere aperto;
- una pagina `tablatura.html` da aprire nel browser: le tracce separate con
  una manopola a testa, e la tablatura che scorre mentre suona. Spegnendo il
  basso senti il pezzo senza basso — audio vero, non un sintetizzatore.

### Se il basso ripete sempre lo stesso giro

Un ostinato di sei note su un pezzo di sette minuti riempirebbe duecento
battute identiche, che non si leggono. Quando trova un giro che torna, il
programma mostra **quello** una volta sola, dice quante volte si ripete, e
stampa solo le battute in cui il bassista ha fatto qualcosa di diverso:

```
Giro di battuta, uguale in 21 battute su 26. Cambia alle battute 1, 10, 11, 19, 26.

G|--------------0-----------------|
D|----0-----3---------3---------0-|
A|------------------------3-------|
E|--------------------------------|
```

Con `--tutto` stampa comunque tutte le battute; nel file di testo ci sono
sempre tutte.

Opzioni utili: `--senza-battute` se il pezzo non ha un tempo stabile,
`--partenza` se la prima stanghetta cade sul movimento sbagliato,
`--polifonico` per tenere gli accordi invece di una nota alla volta,
`--gia-separato` per saltare Demucs se la traccia isolata ce l'hai già.

## Quanto ci si può fidare

Onestamente, dipende dallo strumento:

| | come viene |
|---|---|
| basso | bene: è quasi sempre una nota alla volta, ed è il caso per cui è fatto questo programma |
| batteria | non è previsto qui: serve un modello dedicato (ADTOF, Omnizart) |
| chitarra pulita | discreta, ma va corretta a mano |
| chitarra distorta dentro un mix | poco: accordi, bend e palm mute confondono il trascrittore |

Quello che esce è **una bozza da correggere**, non uno spartito finito. Il
punto è arrivare in venti secondi dove a orecchio ci vorrebbe un'ora.

## Com'è fatto dentro

Cinque pezzi indipendenti, in ordine di catena:

- `separa.py` — Demucs, la canzone in quattro (o sei) tracce.
- `trascrivi.py` — Basic Pitch, con la finestra di frequenze stretta intorno
  all'estensione dello strumento: a un basso non serve cercare note sopra il
  Sol4, e non cercandole smette di inventarsele.
- `pulizia.py` — le quattro pulizie che cambiano la faccia al risultato: via
  le briciole, riattacca le code, **butta le armoniche** (una corda di basso
  produce anche l'ottava e la doppia ottava, e il trascrittore le scrive come
  note a sé), tieni una nota alla volta.
- `diteggiatura.py` — la stessa nota si prende su più corde, e la scelta non
  si fa nota per nota ma sull'intera frase: programmazione dinamica dove ogni
  passo paga lo spostamento della mano rispetto al passo prima. Più tempo
  passa fra due note, meno costa spostarsi.
- `disegno.py` / `visore.py` — la tablatura in battute, su carta e a schermo.
- `ostinato.py` — il giro che si ripete, e i punti in cui non si ripete. Il
  confronto fra battute tollera un sedicesimo di scarto: una nota letta
  storta dal trascrittore non deve far sembrare diverse due battute uguali.

`metronomo.py` trova il tempo con Librosa e poi lo **affina sulle note**, e
corregge due errori diversi. Il primo è di precisione: il battito viene
trovato a 99.4 invece di 100, e mezzo punto dopo dieci secondi è mezza
casella. Il secondo è più grave, ed è di livello: su un ostinato sincopato
Librosa ha risposto **136 bpm dove ce n'erano 100**, e nessun ritocco fine
può salvare una griglia sbagliata di un terzo. Quindi si provano anche i
livelli metrici vicini — metà, doppio, puntato — e si tiene quello su cui
cade più roba. Il livello rilevato si scavalca solo con una prova netta.

## Prove

```bash
python -m pytest test
```

Ventinove prove sulla parte che non dipende da nessun modello: pulizia,
diteggiatura, griglia, disegno. Non serve installare niente di pesante per
farle girare.

La catena `trascrivi → pulizia → diteggiatura → disegno` è stata provata due
volte su basso sintetizzato, perché su musica registrata non ci si arriva da
qui (vedi sotto).

1. **Otto note pulite, ripetute** (Mi Mi Sol La Si La Sol Mi, 100 bpm):
   sedici note su sedici corrette, tempo ritrovato a 100.18 bpm.
2. **Un ostinato di sei note per un minuto**, con ±20 ms di tremolio negli
   attacchi, dinamica variabile, un fondo di rumore che imita la sbavatura
   che Demucs lascia, e due giri alterati di proposito su ventiquattro. Il
   tempo è stato raddrizzato da 136 a 99.96 bpm, il giro è stato riconosciuto
   e mostrato una volta al posto di ventisei battute, e **le due variazioni
   sono state trovate entrambe**, con un falso allarme.
**La separazione con Demucs non è stata provata**: i pesi del modello si
scaricano da internet e la macchina su cui è stato scritto questo codice non
ci arriva. È l'unico pezzo della catena che gira a scatola chiusa.
