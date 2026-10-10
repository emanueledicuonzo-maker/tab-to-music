"""Una pagina che sta sul tuo computer: la tablatura, e le manopole.

Il vantaggio di partire dall'mp3 è che le tracce che spegni sono audio vero,
non un sintetizzatore: togli il basso e senti il disco senza basso. La pagina
apre un lettore per ogni traccia separata, li tiene allineati, e fa scorrere
la tablatura sopra. Non c'è nessun tasto per esportare o condividere: i file
restano dove sono, e la pagina non parla con nessuno.
"""

from __future__ import annotations

import json
from pathlib import Path

from .disegno import allinea_partenza, in_griglia
from .strumenti import NotaSuonata, Strumento

NOMI_CORDE = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")


def dati(
    suonate: list[NotaSuonata],
    strumento: Strumento,
    bpm: float,
    suddivisione: int = 4,
    movimenti: int = 4,
    partenza: float = 0.0,
    parole=(),
) -> dict:
    """La tablatura in una forma che il browser sa disegnare e far scorrere."""
    if suonate:
        partenza = allinea_partenza(partenza, min(s.nota.inizio for s in suonate), bpm, movimenti)
    battute = in_griglia(suonate, bpm, suddivisione, movimenti, partenza)
    cella = 60.0 / bpm / suddivisione
    per_battuta = movimenti * suddivisione
    note = []
    for b, battuta in enumerate(battute):
        for i, colonna in enumerate(battuta):
            for corda, tasto in colonna.items():
                indice = b * per_battuta + i
                note.append(
                    {
                        "corda": corda,
                        "tasto": tasto,
                        "cella": indice,
                        "quando": round(partenza + indice * cella, 3),
                    }
                )
    return {
        "strumento": strumento.nome,
        "corde": [NOMI_CORDE[n % 12] for n in strumento.corde],
        "celle": len(battute) * per_battuta,
        "perBattuta": per_battuta,
        "durataCella": round(cella, 4),
        "partenza": round(partenza, 3),
        "note": note,
        "parole": [{"testo": p.testo, "quando": round(p.inizio, 3)} for p in parole],
    }


PAGINA = """<!doctype html>
<html lang="it">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITOLO__</title>
<style>
  :root { color-scheme: light dark; --bordo: #8883; --acceso: #e8a33d; }
  body { margin: 0; font: 15px/1.5 system-ui, sans-serif; padding: 24px; max-width: 1400px; }
  h1 { font-size: 20px; margin: 0 0 4px; }
  p.nota { margin: 0 0 24px; opacity: .65; font-size: 13px; }
  .barra { display: flex; gap: 12px; align-items: center; margin-bottom: 20px; }
  button { font: inherit; padding: 8px 16px; border: 1px solid var(--bordo); border-radius: 8px;
           background: transparent; color: inherit; cursor: pointer; }
  button.attivo { border-color: var(--acceso); color: var(--acceso); }
  #tempo { font-variant-numeric: tabular-nums; opacity: .7; }
  #scorri { flex: 1; }
  #velocita { display: flex; gap: 4px; }
  #velocita button { padding: 8px 10px; }
  table { border-collapse: collapse; margin-bottom: 24px; }
  td { padding: 4px 8px; border-bottom: 1px solid var(--bordo); }
  td.nome { text-transform: capitalize; }
  #tab { font: 14px/1.7 ui-monospace, monospace; }
  .rigo { white-space: pre; padding: 10px 8px 6px; margin-bottom: 10px; border-radius: 8px;
          border-left: 3px solid transparent; cursor: pointer; }
  .rigo.ora { border-left-color: var(--acceso); background: #e8a33d14; }
  .parole { opacity: .6; margin-top: 2px; }
  .rigo.ora .parole { opacity: .9; }
  .parola.ora { color: var(--acceso); font-weight: 600; }
  .n { padding: 1px 0; border-radius: 3px; }
  .n.ora { background: var(--acceso); color: #000; }
</style>
<h1>__TITOLO__</h1>
<p class="nota">Tablatura per __STRUMENTO__ · __BPM__ bpm · tutto in locale, niente esportazione</p>

<div class="barra">
  <button id="via">▶ Suona</button>
  <input id="scorri" type="range" min="0" max="1000" value="0">
  <span id="tempo">0:00</span>
  <span id="velocita">
    <button data-v="0.5">0,5×</button><button data-v="0.75">0,75×</button><button data-v="1" class="attivo">1×</button>
  </span>
</div>

<table id="tracce"></table>
<div id="tab"></div>

<script>
const DATI = __DATI__;
const TRACCE = __TRACCE__;

const tracce = TRACCE.map(t => {
  const audio = new Audio(t.file);
  audio.preload = "auto";
  return { ...t, audio, spento: false, volume: 1 };
});
let solista = null;

function applicaVolumi() {
  for (const t of tracce) {
    const zitto = t.spento || (solista !== null && solista !== t.nome);
    t.audio.volume = zitto ? 0 : t.volume;
  }
}

const tabella = document.getElementById("tracce");
for (const t of tracce) {
  const riga = document.createElement("tr");
  riga.innerHTML = `<td class="nome">${t.nome}</td>
    <td><button class="spegni">suona</button></td>
    <td><button class="solo">solo</button></td>
    <td><input type="range" min="0" max="100" value="100"></td>`;
  const [spegni, solo] = riga.querySelectorAll("button");
  spegni.classList.add("attivo");
  spegni.onclick = () => {
    t.spento = !t.spento;
    spegni.textContent = t.spento ? "muta" : "suona";
    spegni.classList.toggle("attivo", !t.spento);
    applicaVolumi();
  };
  solo.onclick = () => {
    solista = solista === t.nome ? null : t.nome;
    for (const b of tabella.querySelectorAll(".solo"))
      b.classList.toggle("attivo", b === solo && solista !== null);
    applicaVolumi();
  };
  riga.querySelector("input").oninput = e => {
    t.volume = e.target.value / 100;
    applicaVolumi();
  };
  tabella.append(riga);
}

// La tablatura a righi, come su un foglio: tante battute per rigo quante ne
// stanno nella finestra, e sotto ogni rigo le parole cantate in quel tratto,
// ognuna sotto la casella in cui cade. Il testo serve a sapere dove si è
// dentro un giro che si ripete uguale per tutto il pezzo.
const CELLA = 2;
const PREFISSO = 3;  // " G|"
const tab = document.getElementById("tab");
const PB = DATI.perBattuta;
const battuteTotali = Math.ceil(DATI.celle / PB);
const partenza = DATI.partenza ??
  (DATI.note.length ? DATI.note[0].quando - DATI.note[0].cella * DATI.durataCella : 0);
const notaIn = new Map(DATI.note.map(n => [`${n.corda}:${n.cella}`, n]));
const cellaDi = quando => Math.max(0, Math.round((quando - partenza) / DATI.durataCella));
let caselle = new Map();
let righi = [];         // { el, da, a } in celle
let paroleEl = [];      // lo span di ogni parola, nello stesso ordine di DATI.parole
let rigoAcceso = -1, parolaAccesa = -1;

function larghezzaCarattere() {
  const prova = document.createElement("span");
  prova.textContent = "0".repeat(50);
  prova.style.cssText = "position:absolute;visibility:hidden;white-space:pre";
  tab.append(prova);
  const l = prova.getBoundingClientRect().width / 50;
  prova.remove();
  return l || 8.4;
}

function disegna() {
  const colonne = Math.floor((tab.clientWidth - 24) / larghezzaCarattere());
  const perRigo = Math.max(1, Math.floor((colonne - PREFISSO) / (PB * CELLA + 1)));
  const parole = DATI.parole || [];
  caselle = new Map();
  righi = [];
  paroleEl = new Array(parole.length);
  tab.textContent = "";
  let p = 0;
  for (let b0 = 0; b0 < battuteTotali; b0 += perRigo) {
    const da = b0 * PB, a = Math.min(DATI.celle, (b0 + perRigo) * PB);
    const rigo = document.createElement("div");
    rigo.className = "rigo";
    for (let corda = DATI.corde.length - 1; corda >= 0; corda--) {
      const riga = document.createElement("div");
      riga.append(DATI.corde[corda].padStart(2) + "|");
      for (let i = da; i < a; i++) {
        if (i > da && i % PB === 0) riga.append("|");
        const nota = notaIn.get(`${corda}:${i}`);
        const span = document.createElement("span");
        span.className = "n";
        span.textContent = nota ? String(nota.tasto).padEnd(CELLA, "-") : "-".repeat(CELLA);
        if (nota) caselle.set(`${corda}:${i}`, span);
        riga.append(span);
      }
      riga.append("|");
      rigo.append(riga);
    }
    // Le parole del rigo, ognuna alla colonna della sua casella; se due si
    // pestano i piedi, la seconda scivola a destra. Le parole dopo l'ultima
    // battuta finiscono nell'ultimo rigo.
    const ultimo = b0 + perRigo >= battuteTotali;
    const sotto = document.createElement("div");
    sotto.className = "parole";
    let colonna = 0;
    while (p < parole.length && (ultimo || cellaDi(parole[p].quando) < a)) {
      const locale = Math.min(a - da, Math.max(0, cellaDi(parole[p].quando) - da));
      const voluta = PREFISSO + locale * CELLA + Math.floor(locale / PB);
      const dove = Math.max(voluta, colonna > 0 ? colonna + 1 : 0);
      sotto.append(" ".repeat(dove - colonna));
      const span = document.createElement("span");
      span.className = "parola";
      span.textContent = parole[p].testo;
      sotto.append(span);
      paroleEl[p] = span;
      colonna = dove + parole[p].testo.length;
      p++;
    }
    if (parole.length) { if (!sotto.childNodes.length) sotto.textContent = " "; rigo.append(sotto); }
    rigo.onclick = () => {
      const quando = partenza + da * DATI.durataCella;
      audio.forEach(x => { x.currentTime = quando; });
    };
    tab.append(rigo);
    righi.push({ el: rigo, da, a });
  }
  rigoAcceso = -1;
  parolaAccesa = -1;
  acceso = null;
}

function seguiRighi(ora) {
  const cella = cellaDi(ora);
  const r = righi.findIndex(x => cella >= x.da && cella < x.a);
  if (r !== rigoAcceso) {
    righi[rigoAcceso]?.el.classList.remove("ora");
    if (r >= 0) {
      righi[r].el.classList.add("ora");
      if (!guida.paused) righi[r].el.scrollIntoView({ block: "center", behavior: "smooth" });
    }
    rigoAcceso = r;
  }
  const parole = DATI.parole || [];
  let i = -1;
  while (i + 1 < parole.length && parole[i + 1].quando <= ora) i++;
  if (i !== parolaAccesa) {
    paroleEl[parolaAccesa]?.classList.remove("ora");
    paroleEl[i]?.classList.add("ora");
    parolaAccesa = i;
  }
}

let rifai;
addEventListener("resize", () => { clearTimeout(rifai); rifai = setTimeout(disegna, 150); });

const audio = tracce.map(t => t.audio);
const guida = audio[0];
const via = document.getElementById("via");
const scorri = document.getElementById("scorri");
const tempo = document.getElementById("tempo");
let acceso = null;
disegna();

function orologio(s) {
  return `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;
}

via.onclick = () => {
  if (guida.paused) { audio.forEach(a => { a.currentTime = guida.currentTime; a.play(); }); via.textContent = "⏸ Ferma"; }
  else { audio.forEach(a => a.pause()); via.textContent = "▶ Suona"; }
};

// Rallentare senza cambiare intonazione: il browser tiene l'altezza delle note.
for (const b of document.querySelectorAll("#velocita button")) {
  b.onclick = () => {
    for (const a of audio) { a.preservesPitch = true; a.playbackRate = Number(b.dataset.v); }
    for (const x of document.querySelectorAll("#velocita button")) x.classList.toggle("attivo", x === b);
  };
}

scorri.oninput = () => {
  const quando = (scorri.value / 1000) * (guida.duration || 0);
  audio.forEach(a => { a.currentTime = quando; });
};

setInterval(() => {
  const ora = guida.currentTime;
  // I lettori vanno ognuno per conto suo: ogni tanto si riallineano alla guida.
  for (const a of audio) if (Math.abs(a.currentTime - ora) > 0.08) a.currentTime = ora;
  tempo.textContent = orologio(ora);
  seguiRighi(ora);
  if (guida.duration) scorri.value = Math.round((ora / guida.duration) * 1000);

  const vicina = DATI.note.reduce(
    (scelta, n) => (n.quando <= ora + DATI.durataCella / 2 ? n : scelta), null);
  const chiave = vicina ? `${vicina.corda}:${vicina.cella}` : null;
  if (chiave !== acceso) {
    if (acceso) caselle.get(acceso)?.classList.remove("ora");
    if (chiave) caselle.get(chiave)?.classList.add("ora");
    acceso = chiave;
  }
}, 100);
</script>
</html>
"""


def scrivi(
    dove: Path,
    titolo: str,
    strumento: Strumento,
    bpm: float,
    tab: dict,
    tracce: list[dict],
) -> Path:
    """Scrive la pagina accanto alle tracce separate."""
    pagina = (
        PAGINA.replace("__TITOLO__", titolo)
        .replace("__STRUMENTO__", strumento.nome)
        .replace("__BPM__", f"{bpm:g}")
        .replace("__DATI__", json.dumps(tab))
        .replace("__TRACCE__", json.dumps(tracce))
    )
    dove.write_text(pagina, encoding="utf-8")
    return dove
