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

from .accordi import DITEGGIATURE
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
    accordi=(),
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
        "accordi": [{"nome": a.nome, "quando": round(a.inizio, 3)} for a in accordi],
        "diteggiature": {a.nome: DITEGGIATURE[a.nome] for a in accordi if a.nome in DITEGGIATURE},
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
          border-left: 3px solid transparent; cursor: pointer; overflow-x: auto; }
  .rigo.ora { border-left-color: var(--acceso); background: #e8a33d14; }
  .parole { opacity: .6; margin-top: 2px; }
  .rigo.ora .parole { opacity: .9; }
  .parola.ora { color: var(--acceso); font-weight: 600; }
  .n { padding: 1px 0; border-radius: 3px; }
  .n.ora { background: var(--acceso); color: #000; }
  .accordi { font-weight: 700; color: var(--acceso); margin-bottom: 2px; }
  .accordo.ora { background: var(--acceso); color: #000; border-radius: 3px; }
  #vista { display: flex; gap: 4px; margin-bottom: 12px; }
  #diagrammi { position: sticky; top: 0; z-index: 1; display: flex; flex-wrap: wrap; gap: 6px;
               padding: 8px 0; margin-bottom: 12px; background: Canvas; }
  .diagramma { text-align: center; padding: 4px 6px; border: 1px solid var(--bordo); border-radius: 8px;
               font-weight: 600; font-size: 13px; }
  .diagramma.ora { border-color: var(--acceso); color: var(--acceso); box-shadow: 0 0 0 1px var(--acceso); }
  .diagramma svg { display: block; }
  #canzoniere { display: none; font: 18px/1.5 ui-monospace, monospace; }
  body.soloaccordi #tab { display: none; }
  body.soloaccordi #canzoniere { display: block; }
  .frase { white-space: pre; padding: 6px 10px; margin-bottom: 8px; border-radius: 8px; cursor: pointer;
           border-left: 3px solid transparent; overflow-x: auto; }
  .frase.ora { border-left-color: var(--acceso); background: #e8a33d14; }
  .frase .accordi { margin-bottom: 0; }
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
<div id="vista" hidden>
  <button data-vista="tab" class="attivo">Tablatura</button><button data-vista="accordi">Accordi e testo</button>
</div>
<div id="diagrammi"></div>
<div id="tab"></div>
<div id="canzoniere"></div>

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
// stanno nella finestra, sopra ogni rigo gli accordi e sotto le parole
// cantate in quel tratto, ognuna sopra o sotto la casella in cui cade. Il testo serve a sapere dove si è
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
const accordi = DATI.accordi || [];
const DITA = DATI.diteggiature || {};
let accordiEl = [], accordoAcceso = -1;
const diagrammiEl = new Map();

// Una riga di voci (accordi o parole), ognuna alla colonna della sua casella;
// se due si pestano i piedi, la seconda scivola a destra. Quelle dopo l'ultima
// battuta finiscono nell'ultimo rigo.
function incolonna(voci, indice, da, a, ultimo, classe, classeVoce, testoDi, spans) {
  const el = document.createElement("div");
  el.className = classe;
  let colonna = 0;
  while (indice < voci.length && (ultimo || cellaDi(voci[indice].quando) < a)) {
    const locale = Math.min(a - da, Math.max(0, cellaDi(voci[indice].quando) - da));
    const voluta = PREFISSO + locale * CELLA + Math.floor(locale / PB);
    const dove = Math.max(voluta, colonna > 0 ? colonna + 1 : 0);
    el.append(" ".repeat(dove - colonna));
    const span = document.createElement("span");
    span.className = classeVoce;
    span.textContent = testoDi(voci[indice]);
    el.append(span);
    spans[indice] = span;
    colonna = dove + span.textContent.length;
    indice++;
  }
  if (!el.childNodes.length) el.textContent = " ";
  return { el, indice };
}

// Il disegno di un accordo: sei corde in verticale, cinque tasti, i pallini
// dove vanno le dita, x sulle corde da non suonare, o su quelle a vuoto.
function diagramma(forma) {
  const tasti = [...forma].map(c => (c === "x" ? -1 : Number(c)));
  const premuti = tasti.filter(t => t > 0);
  const massimo = Math.max(0, ...premuti);
  const base = massimo <= 4 ? 1 : Math.min(...premuti);
  const L = 64, A = 80, x0 = 10, y0 = 16, dx = (L - 2 * x0) / 5, dy = (A - y0 - 6) / 5;
  const X = c => x0 + c * dx, Y = t => y0 + (t - base + 0.5) * dy;
  let svg = `<svg width="${L}" height="${A}" viewBox="0 0 ${L} ${A}" fill="none" stroke="currentColor">`;
  for (let c = 0; c < 6; c++) svg += `<line x1="${X(c)}" y1="${y0}" x2="${X(c)}" y2="${y0 + 5 * dy}" stroke-width="1"/>`;
  for (let t = 0; t <= 5; t++)
    svg += `<line x1="${X(0)}" y1="${y0 + t * dy}" x2="${X(5)}" y2="${y0 + t * dy}" stroke-width="${t === 0 && base === 1 ? 3 : 1}"/>`;
  if (base > 1) svg += `<text x="1" y="${y0 + dy * 0.75}" font-size="9" fill="currentColor" stroke="none">${base}</text>`;
  // Il barrè: niente corde a vuoto e il tasto più basso preso da più corde.
  const minimo = premuti.length ? Math.min(...premuti) : 0;
  const sulMinimo = tasti.map((t, c) => (t === minimo ? c : -1)).filter(c => c >= 0);
  if (!forma.includes("0") && sulMinimo.length >= 2)
    svg += `<line x1="${X(sulMinimo[0])}" y1="${Y(minimo)}" x2="${X(sulMinimo.at(-1))}" y2="${Y(minimo)}" stroke-width="7" stroke-linecap="round"/>`;
  tasti.forEach((t, c) => {
    if (t < 0) svg += `<text x="${X(c) - 3}" y="11" font-size="9" fill="currentColor" stroke="none">×</text>`;
    else if (t === 0) svg += `<circle cx="${X(c)}" cy="8" r="3"/>`;
    else svg += `<circle cx="${X(c)}" cy="${Y(t)}" r="4" fill="currentColor"/>`;
  });
  return svg + "</svg>";
}

{
  // In cima, ogni accordo della canzone una volta sola, nell'ordine in cui arriva.
  const contenitore = document.getElementById("diagrammi");
  for (const nome of new Set(accordi.map(a => a.nome))) {
    if (!DITA[nome]) continue;
    const box = document.createElement("div");
    box.className = "diagramma";
    box.innerHTML = `${nome}${diagramma(DITA[nome])}`;
    contenitore.append(box);
    diagrammiEl.set(nome, box);
  }
  if (!accordi.length) contenitore.remove();
  else {
    const vista = document.getElementById("vista");
    vista.hidden = false;
    const scegliVista = nome => {
      document.body.classList.toggle("soloaccordi", nome === "accordi");
      for (const x of vista.querySelectorAll("button")) x.classList.toggle("attivo", x.dataset.vista === nome);
      try { localStorage.setItem("vista", nome); } catch {}
    };
    for (const b of vista.querySelectorAll("button")) b.onclick = () => scegliVista(b.dataset.vista);
    // La vista scelta l'ultima volta vale anche per la canzone dopo.
    let ricordata = location.hash === "#accordi" ? "accordi" : null;
    try { ricordata ??= localStorage.getItem("vista"); } catch {}
    if (ricordata === "accordi") scegliVista("accordi");
  }
}

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
  accordiEl = new Array(accordi.length);
  let a_ = 0;
  righi = [];
  paroleEl = new Array(parole.length);
  tab.textContent = "";
  let p = 0;
  for (let b0 = 0; b0 < battuteTotali; b0 += perRigo) {
    const da = b0 * PB, a = Math.min(DATI.celle, (b0 + perRigo) * PB);
    const ultimo = b0 + perRigo >= battuteTotali;
    const rigo = document.createElement("div");
    rigo.className = "rigo";
    if (accordi.length) {
      const fatto = incolonna(accordi, a_, da, a, ultimo, "accordi", "accordo", x => x.nome, accordiEl);
      a_ = fatto.indice;
      rigo.append(fatto.el);
    }
    for (let corda = DATI.corde.length - 1; corda >= 0; corda--) {
      const riga = document.createElement("div");
      riga.className = "corda";
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
    if (parole.length) {
      const fatto = incolonna(parole, p, da, a, ultimo, "parole", "parola", x => x.testo, paroleEl);
      p = fatto.indice;
      rigo.append(fatto.el);
    }
    rigo.onclick = () => {
      const quando = partenza + da * DATI.durataCella;
      audio.forEach(x => { x.currentTime = quando; });
    };
    tab.append(rigo);
    righi.push({ el: rigo, da, a });
  }
  rigoAcceso = -1;
  parolaAccesa = -1;
  accordoAcceso = -1;
  acceso = null;
}

// Accordi e testo, come su un canzoniere: una riga per frase cantata, che
// parte da sinistra, con ogni accordo sopra la parola su cui arriva. Le parti
// senza voce diventano una riga di soli accordi.
let frasi = [];          // { el, da, a } in secondi
let paroleC = [], accordiC = [], fraseAccesa = -1;
function disegnaCanzoniere() {
  const el = document.getElementById("canzoniere");
  const parole = DATI.parole || [];
  el.textContent = "";
  frasi = []; paroleC = new Array(parole.length); accordiC = new Array(accordi.length);
  // Le frasi: si va a capo dopo una pausa, o dopo un punto se la riga è già lunga.
  const gruppi = [];
  let corrente = [];
  parole.forEach((p, i) => {
    const prima = parole[i - 1];
    const lunga = corrente.reduce((n, j) => n + parole[j].testo.length + 1, 0);
    if (corrente.length && (p.quando - prima.quando > 2.2 || (/[.?!,]$/.test(prima.testo) && lunga > 28) || lunga > 60)) {
      gruppi.push(corrente); corrente = [];
    }
    corrente.push(i);
  });
  if (corrente.length) gruppi.push(corrente);

  let k = 0;
  const fine = (guida.duration || 1e9);
  const soliAccordi = (finoA) => {
    // Gli accordi suonati prima della prossima frase, tutti su una riga.
    const qui = [];
    while (k < accordi.length && accordi[k].quando < finoA - 0.3) qui.push(k++);
    if (!qui.length) return;
    const riga = document.createElement("div");
    riga.className = "frase";
    const sopra = document.createElement("div");
    sopra.className = "accordi";
    qui.forEach((j, n) => {
      if (n) sopra.append("   ");
      const span = document.createElement("span");
      span.className = "accordo"; span.textContent = accordi[j].nome;
      sopra.append(span); accordiC[j] = span;
    });
    riga.append(sopra);
    const da = accordi[qui[0]].quando;
    riga.onclick = () => audio.forEach(x => { x.currentTime = da; });
    el.append(riga);
    frasi.push({ el: riga, da, a: finoA });
  };
  gruppi.forEach((g, n) => {
    const da = parole[g[0]].quando;
    const a = n + 1 < gruppi.length ? parole[gruppi[n + 1][0]].quando : fine;
    soliAccordi(da);
    const riga = document.createElement("div");
    riga.className = "frase";
    const sopra = document.createElement("div");
    sopra.className = "accordi";
    const sotto = document.createElement("div");
    let colSopra = 0, colSotto = 0;
    g.forEach((i, m) => {
      const parola = parole[i];
      const finoA = m + 1 < g.length ? parole[g[m + 1]].quando : a;
      if (m) { sotto.append(" "); colSotto++; }
      // Gli accordi che arrivano mentre si canta questa parola, sopra di lei.
      while (k < accordi.length && accordi[k].quando < finoA - 0.05) {
        const dove = Math.max(colSotto, colSopra ? colSopra + 1 : 0);
        sopra.append(" ".repeat(dove - colSopra));
        const span = document.createElement("span");
        span.className = "accordo"; span.textContent = accordi[k].nome;
        sopra.append(span); accordiC[k] = span;
        colSopra = dove + span.textContent.length;
        k++;
      }
      const span = document.createElement("span");
      span.className = "parola"; span.textContent = parola.testo;
      sotto.append(span); paroleC[i] = span;
      colSotto += parola.testo.length;
    });
    if (!sopra.childNodes.length) sopra.textContent = " ";
    riga.append(sopra, sotto);
    riga.onclick = () => audio.forEach(x => { x.currentTime = da; });
    el.append(riga);
    frasi.push({ el: riga, da, a });
  });
  soliAccordi(Infinity);
  fraseAccesa = -1;
}

function seguiRighi(ora) {
  if (document.body.classList.contains("soloaccordi")) {
    const f = frasi.findIndex(x => ora >= x.da - 0.3 && ora < x.a - 0.3);
    if (f !== fraseAccesa) {
      frasi[fraseAccesa]?.el.classList.remove("ora");
      if (f >= 0) {
        frasi[f].el.classList.add("ora");
        if (!guida.paused) frasi[f].el.scrollIntoView({ block: "center", behavior: "smooth" });
      }
      fraseAccesa = f;
    }
  }
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
    paroleC[parolaAccesa]?.classList.remove("ora");
    paroleC[i]?.classList.add("ora");
    parolaAccesa = i;
  }
  let k = -1;
  while (k + 1 < accordi.length && accordi[k + 1].quando <= ora) k++;
  if (k !== accordoAcceso) {
    accordiEl[accordoAcceso]?.classList.remove("ora");
    accordiC[accordoAcceso]?.classList.remove("ora");
    accordiC[k]?.classList.add("ora");
    diagrammiEl.get(accordi[accordoAcceso]?.nome)?.classList.remove("ora");
    accordiEl[k]?.classList.add("ora");
    diagrammiEl.get(accordi[k]?.nome)?.classList.add("ora");
    accordoAcceso = k;
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
disegnaCanzoniere();
guida.addEventListener("loadedmetadata", disegnaCanzoniere);

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


def pagina(titolo: str, strumento: str, bpm: float, tab: dict, tracce: list[dict]) -> str:
    """La pagina di una canzone, come testo."""
    return (
        PAGINA.replace("__TITOLO__", titolo)
        .replace("__STRUMENTO__", strumento)
        .replace("__BPM__", f"{bpm:g}")
        .replace("__DATI__", json.dumps(tab))
        .replace("__TRACCE__", json.dumps(tracce))
    )


def scrivi(
    dove: Path,
    titolo: str,
    strumento: Strumento,
    bpm: float,
    tab: dict,
    tracce: list[dict],
) -> Path:
    """Scrive la pagina accanto alle tracce separate."""
    dove.write_text(pagina(titolo, strumento.nome, bpm, tab, tracce), encoding="utf-8")
    return dove
