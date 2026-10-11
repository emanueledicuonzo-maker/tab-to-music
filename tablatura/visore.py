"""Una pagina che sta sul tuo computer: la tablatura, e le manopole.

Il vantaggio di partire dall'mp3 è che le tracce che spegni sono audio vero,
non un sintetizzatore: togli il basso e senti il disco senza basso. La pagina
apre un lettore per ogni traccia separata, li tiene allineati, e fa scorrere
la tablatura sopra. Non c'è nessun tasto per esportare o condividere: i file
restano dove sono, e la pagina non parla con nessuno.
"""

from __future__ import annotations

import html
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
    segni=(),
) -> dict:
    """La tablatura in una forma che il browser sa disegnare e far scorrere."""
    if suonate:
        partenza = allinea_partenza(partenza, min(s.nota.inizio for s in suonate), bpm, movimenti)
    battute = in_griglia(suonate, bpm, suddivisione, movimenti, partenza)
    cella = 60.0 / bpm / suddivisione
    # Il segno di ogni nota (legato, glissato…), nella stessa casella in cui finisce la nota.
    tecniche = {
        (round((s.nota.inizio - partenza) / cella), s.posizione.corda): segno
        for s, segno in zip(suonate, segni)
        if segno
    }
    per_battuta = movimenti * suddivisione
    note = []
    for b, battuta in enumerate(battute):
        for i, colonna in enumerate(battuta):
            for corda, tasto in colonna.items():
                indice = b * per_battuta + i
                nota = {
                    "corda": corda,
                    "tasto": tasto,
                    "cella": indice,
                    "quando": round(partenza + indice * cella, 3),
                }
                if (indice, corda) in tecniche:
                    nota["segno"] = tecniche[(indice, corda)]
                note.append(nota)
    return {
        "strumento": strumento.nome,
        "corde": [NOMI_CORDE[n % 12] for n in strumento.corde],
        "cordeMidi": list(strumento.corde),
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
  :root {
    color-scheme: dark;
    --fondo: #06060b; --pannello: #ffffff08; --pannello2: #ffffff0d; --bordo: #ffffff14; --testo: #eef0f6;
    --tenue: #9aa0b4; --acceso: #ffb020; --rosa: #ff3d81; --ciano: #2de2e6; --viola: #a78bfa;
    --bagliore: 0 0 18px #ffb02088, 0 0 2px #ffb020;
  }
  * { box-sizing: border-box; }
  [hidden] { display: none !important; }
  html { --respiro: 0; min-height: 100%;
         background: radial-gradient(1200px 600px at 15% -10%, rgb(255 61 129 / calc(.10 + var(--respiro) * .25)), transparent 60%),
                     radial-gradient(1000px 500px at 95% 0%, #2de2e61c, transparent 60%), var(--fondo); background-attachment: fixed; }
  body { margin: 0; padding: 0 28px 80px; font: 15px/1.5 system-ui, "Ubuntu", sans-serif; color: var(--testo);
         min-height: 100vh; overflow-x: hidden; }
  #lampo { position: fixed; inset: 0; pointer-events: none; z-index: 50; opacity: 0;
           background: radial-gradient(circle at 50% 30%, #ffffff, #ffb020 40%, transparent 75%); mix-blend-mode: screen; }
  button { font: inherit; padding: 8px 14px; border: 1px solid var(--bordo); border-radius: 10px; color: var(--testo);
           background: var(--pannello); cursor: pointer; transition: border-color .15s, box-shadow .15s, color .15s; }
  button:hover { border-color: #ffffff33; }
  button.attivo { border-color: var(--acceso); color: var(--acceso); box-shadow: inset 0 0 12px #ffb02022; }

  .testata { display: grid; grid-template-columns: 1fr auto auto; gap: 28px; align-items: center; padding: 26px 0 18px; }
  #alone { position: fixed; inset: -10%; z-index: -1; background-size: cover; background-position: center;
           filter: blur(90px) saturate(1.6); opacity: .22; pointer-events: none; }
  #alone[style*="url('')"] { display: none; }
  .chi { display: flex; align-items: center; gap: 22px; min-width: 0; }
  #copertina { width: 132px; height: 132px; flex: none; border-radius: 14px; object-fit: cover;
               box-shadow: 0 18px 50px #000a, 0 0 0 1px #ffffff1a; }
  #copertina[src=""] { display: none; }
  .album { margin-top: 6px; color: var(--tenue); font-size: 14px; }
  .accordatura { display: inline-flex; gap: 8px; align-items: center; margin-top: 10px; padding: 4px 12px;
                 border-radius: 999px; border: 1px solid #2de2e655; background: #2de2e612; color: var(--ciano);
                 font-weight: 700; font-size: 13px; letter-spacing: .04em; }
  .accordatura b { color: #fff; }
  .etichetta { font-size: 12px; letter-spacing: .18em; text-transform: uppercase; color: var(--tenue); }
  .etichetta b { color: var(--ciano); font-weight: 600; }
  h1 { font-size: clamp(22px, 2.6vw, 38px); line-height: 1.1; margin: 6px 0 0; font-weight: 800; letter-spacing: -.02em;
       background: linear-gradient(90deg, #fff, #ffd38a 55%, #ff9bc0); -webkit-background-clip: text; background-clip: text; color: transparent; }
  .ora-accordo { text-align: right; min-width: 170px; }
  #accordoOra { display: block; font: 800 64px/1 system-ui, sans-serif; color: var(--acceso); text-shadow: var(--bagliore);
                transition: transform .12s; }
  #accordoOra.salto { transform: scale(1.12); }
  #accordoDopo { font-size: 13px; color: var(--tenue); letter-spacing: .08em; }
  #battiti { display: flex; gap: 10px; }
  #battiti i { width: 18px; height: 18px; border-radius: 50%; background: #ffffff12; border: 1px solid var(--bordo);
               transition: background .08s, box-shadow .08s; }
  #battiti i.su { background: var(--ciano); box-shadow: 0 0 16px var(--ciano); }
  #battiti i.su:first-child { background: var(--rosa); box-shadow: 0 0 20px var(--rosa); }

  .trasporto { position: sticky; top: 0; z-index: 5; display: flex; align-items: center; gap: 14px; padding: 12px 16px;
               margin: 0 -16px 18px; border-radius: 16px; background: #0b0b14cc; backdrop-filter: blur(14px);
               border: 1px solid var(--bordo); box-shadow: 0 10px 40px #0008; }
  #via { width: 56px; height: 56px; border-radius: 50%; padding: 0; font-size: 22px; border: 0; color: #111; flex: none;
         background: linear-gradient(135deg, var(--acceso), var(--rosa)); box-shadow: 0 0 24px #ff3d8166; }
  #via:hover { box-shadow: 0 0 34px #ff3d81aa; }
  .linea { flex: 1; position: relative; height: 56px; }
  #spettro { position: absolute; inset: 0; width: 100%; height: 100%; border-radius: 10px; }
  #scorri { position: absolute; left: 0; right: 0; bottom: 0; width: 100%; margin: 0; appearance: none; height: 4px;
            background: linear-gradient(90deg, var(--acceso) var(--fatto, 0%), #ffffff1a var(--fatto, 0%)); border-radius: 4px; cursor: pointer; }
  #scorri::-webkit-slider-thumb { appearance: none; width: 14px; height: 14px; border-radius: 50%; background: #fff; box-shadow: 0 0 10px var(--acceso); }
  #tempo { font: 600 15px ui-monospace, monospace; color: var(--tenue); min-width: 92px; text-align: center; }
  #velocita { display: flex; gap: 4px; }
  #velocita button { padding: 7px 10px; font-size: 13px; }
  #luci { font-size: 13px; }

  #tracce { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 12px; margin-bottom: 22px; }
  /* Sugli schermi larghi il mixer sta fisso a destra, sempre a portata di mano. */
  @media (min-width: 1000px) {
    body { padding-right: 230px; }
    #tracce { position: fixed; right: 20px; top: 20px; bottom: 20px; width: 190px; z-index: 6; margin: 0;
              display: flex; flex-direction: column; gap: 10px; overflow-y: auto; }
    .striscia canvas { height: 78px; }
  }
  .striscia { --c: var(--acceso); display: grid; grid-template-columns: 14px 1fr; gap: 6px 12px; padding: 12px;
              border-radius: 14px; background: var(--pannello); border: 1px solid var(--bordo); }
  .striscia.zitta { opacity: .45; }
  .striscia canvas { grid-row: span 3; width: 14px; height: 92px; border-radius: 4px; background: #0008; }
  .striscia .nome { font-weight: 700; text-transform: capitalize; color: var(--c); letter-spacing: .02em; }
  .striscia .tasti { display: flex; gap: 6px; }
  .striscia .tasti button { padding: 4px 10px; font-size: 12px; }
  .striscia .tasti button.attivo { border-color: var(--c); color: var(--c); box-shadow: inset 0 0 10px color-mix(in srgb, var(--c) 25%, transparent); }
  .striscia input[type=range] { width: 100%; accent-color: var(--c); }

  #vista { display: inline-flex; gap: 4px; padding: 4px; margin-bottom: 14px; border-radius: 12px; background: var(--pannello); border: 1px solid var(--bordo); }
  #vista button { border: 0; background: transparent; }
  #vista button.attivo { background: #ffb0201a; box-shadow: none; }
  #diagrammi { position: sticky; top: 88px; z-index: 4; display: flex; flex-wrap: wrap; gap: 8px; padding: 10px 0; margin-bottom: 14px;
               background: linear-gradient(#06060bee, #06060bcc); backdrop-filter: blur(8px); }
  .diagramma { text-align: center; padding: 6px 8px 4px; border: 1px solid var(--bordo); border-radius: 12px; background: var(--pannello);
               font-weight: 700; font-size: 14px; color: var(--tenue); transition: all .15s; }
  .diagramma svg { display: block; color: #d9dcea; }
  .diagramma.ora { border-color: var(--acceso); color: var(--acceso); background: #ffb02014; box-shadow: 0 0 22px #ffb02044;
                   transform: translateY(-2px); }
  .diagramma.ora svg { color: var(--acceso); }

  #tab { font: 14px/1.75 ui-monospace, "Ubuntu Mono", monospace; }
  .rigo { white-space: pre; padding: 12px 14px 8px; margin-bottom: 12px; border-radius: 14px; cursor: pointer; overflow-x: auto;
          border: 1px solid transparent; color: #b9bdd0; transition: background .2s, border-color .2s; }
  .rigo:hover { background: var(--pannello); }
  .giri { font-size: 12px; color: var(--viola); margin-bottom: 2px; }
  .giro.variazione { color: var(--rosa); }
  #bGiro { margin: 0 0 14px 10px; vertical-align: top; }
  .rigo.ora { background: linear-gradient(90deg, #ffb02012, #ff3d810a); border-color: #ffb02044; color: var(--testo); }
  .parole { color: var(--tenue); margin-top: 3px; }
  .rigo.ora .parole { color: #dfe2ee; }
  .parola.ora { color: var(--ciano); text-shadow: 0 0 10px #2de2e6aa; }
  .n { padding: 1px 0; border-radius: 4px; }
  .n.ora { background: var(--acceso); color: #000; box-shadow: 0 0 14px var(--acceso); }
  .accordi { font-weight: 800; color: var(--acceso); margin-bottom: 2px; }
  .seg { color: var(--ciano); font-weight: 800; }
  .n.ora .seg { color: #000; }
  #legenda { display: flex; flex-wrap: wrap; gap: 6px 16px; margin: -4px 0 14px; font-size: 13px; color: var(--tenue); }
  #legenda b { color: var(--ciano); font-family: ui-monospace, monospace; margin-right: 4px; }
  .accordo.ora { color: #000; background: var(--acceso); border-radius: 4px; box-shadow: 0 0 14px var(--acceso); }

  #gp { display: none; }
  body.sologp #gp { display: block; }
  body.sologp #tab, body.sologp #canzoniere, body.sologp #legenda, body.sologp #diagrammi, body.sologp #bGiro { display: none !important; }
  #gpStrumenti { position: sticky; top: 92px; z-index: 4; display: flex; flex-wrap: wrap; gap: 8px; padding: 10px 0;
                 margin-bottom: 8px; background: linear-gradient(#06060bf0, #06060bd0); backdrop-filter: blur(8px); }
  .strumento { display: flex; align-items: center; gap: 10px; padding: 8px 14px; text-align: left; }
  .strumento .icona { font-size: 22px; }
  .strumento small { display: block; color: var(--tenue); font-size: 11px; }
  .strumento.basso { border-color: #ffb02066; }
  .strumento.attivo { border-color: var(--acceso); background: #ffb0201a; box-shadow: 0 0 18px #ffb02033; }
  .gpBarra { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-bottom: 12px; }
  .gpBarra select { font: inherit; padding: 6px 10px; border-radius: 10px; border: 1px solid var(--bordo); background: #ffffff08; color: inherit; }
  .gpBarra select option { background: #111; }
  #gpStato { color: var(--tenue); font-size: 13px; }
  #alphaTab { background: #0b0b14; border: 1px solid var(--bordo); border-radius: 14px; padding: 10px; min-height: 300px; }
  #alphaTab .at-cursor-bar { background: #ffb02022; }
  #alphaTab .at-cursor-beat { background: var(--acceso); width: 3px; box-shadow: 0 0 12px var(--acceso); }
  #alphaTab .at-highlight * { fill: var(--acceso); stroke: var(--acceso); }
  #bGP { margin: 0 0 14px 10px; vertical-align: top; }
  #dGP { border: 1px solid var(--bordo); border-radius: 16px; background: #0d0d16f2; color: inherit; width: min(720px, 94vw); padding: 0; }
  #dGP::backdrop { background: #000a; }
  .gpTesta { display: flex; justify-content: space-between; align-items: center; padding: 14px 18px; border-bottom: 1px solid var(--bordo); }
  .gpTesta .chiudi { border: 0; background: transparent; font-size: 22px; color: var(--tenue); }
  #gpElenco { display: flex; flex-direction: column; gap: 6px; padding: 12px 18px; max-height: 50vh; overflow: auto; }
  .gpVoce { text-align: left; display: flex; flex-direction: column; gap: 2px; }
  .gpVoce small { color: var(--tenue); font-size: 12px; }
  .gpVoce.ha small { color: #6bffa0; }
  .gpCarica { display: block; padding: 12px 18px 18px; color: var(--tenue); font-size: 13px; }
  .gpCarica input { display: block; margin-top: 8px; color: var(--testo); }
  #canzoniere { display: none; font: 20px/1.55 ui-monospace, "Ubuntu Mono", monospace; }
  body.soloaccordi #tab { display: none; }
  body.soloaccordi #canzoniere { display: block; }
  .frase { white-space: pre; padding: 8px 14px; margin-bottom: 8px; border-radius: 14px; cursor: pointer; overflow-x: auto;
           border: 1px solid transparent; color: #c3c7d8; transition: background .2s; }
  .frase:hover { background: var(--pannello); }
  .frase.ora { background: linear-gradient(90deg, #ffb02012, #ff3d810a); border-color: #ffb02044; color: #fff; }
  .frase .accordi { margin-bottom: 0; }
  ::-webkit-scrollbar { height: 8px; width: 10px; } ::-webkit-scrollbar-thumb { background: #ffffff22; border-radius: 8px; }
</style>
<div id="lampo"></div>
<div id="alone" style="background-image:url('__COPERTINA__')"></div>
<section class="testata">
  <div class="chi">
    <img id="copertina" src="__COPERTINA__" alt="">
    <div>
      <div class="etichetta">Tablatura · <b>__STRUMENTO__</b> · __BPM__ bpm</div>
      <h1>__TITOLO__</h1>
      <div class="album">__ALBUM__</div>
      <div class="accordatura" title="Accordatura, dalla corda più grave">__ACCORDATURA__</div>
    </div>
  </div>
  <div id="battiti" title="I movimenti della battuta"><i></i><i></i><i></i><i></i></div>
  <div class="ora-accordo"><span id="accordoOra">—</span><span id="accordoDopo"></span></div>
</section>

<div class="trasporto">
  <button id="via" title="Suona / ferma (spazio)">▶</button>
  <div class="linea">
    <canvas id="spettro"></canvas>
    <input id="scorri" type="range" min="0" max="1000" value="0">
  </div>
  <span id="tempo">0:00</span>
  <span id="velocita">
    <button data-v="0.5">0,5×</button><button data-v="0.75">0,75×</button><button data-v="1" class="attivo">1×</button>
  </span>
  <button id="luci" title="Luci a tempo">Luci</button>
</div>

<div id="tracce"></div>
<div id="vista" hidden>
  <button data-vista="tab" class="attivo">Tablatura</button><button data-vista="accordi">Accordi e testo</button><button data-vista="gp" id="vistaGP" hidden>Guitar Pro</button>
</div>
<button id="bGP" title="Collega una tablatura Guitar Pro a questa canzone">Guitar Pro…</button>
<button id="bGiro" hidden title="Le ripetizioni del giro rese uguali, o la tablatura come l'ha sentita il programma">Giro pulito</button>
<div id="diagrammi"></div>
<div id="legenda" hidden></div>
<div id="tab"></div>
<div id="canzoniere"></div>
<section id="gp">
  <div id="gpStrumenti"></div>
  <div class="gpBarra">
    <button id="gpPrima" title="Tutta la tablatura un decimo di secondo prima">−0,1 s</button>
    <button id="gpDopo" title="Tutta la tablatura un decimo di secondo dopo">+0,1 s</button>
    <button id="gpRifai" title="Rifà la sincronia automatica, buttando le correzioni">Risincronizza</button>
    <span id="gpStato"></span>
  </div>
  <div id="alphaTab"></div>
</section>
<dialog id="dGP">
  <div class="gpTesta"><b>Tablatura Guitar Pro</b><button class="chiudi" aria-label="Chiudi">×</button></div>
  <div id="gpElenco"></div>
  <label class="gpCarica">…oppure carica un file scaricato da te (.gp, .gpx, .gp5, .gp4, .gp3)
    <input type="file" id="gpFile" accept=".gp,.gpx,.gp5,.gp4,.gp3,.gtp"></label>
</dialog>

<script>
const DATI = __DATI__;
const GP = __GUITARPRO__;
let VISTA_RICORDATA = null;
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
    if (t.guadagno) t.guadagno.gain.value = zitto ? 0 : t.volume;
    else t.audio.volume = zitto ? 0 : t.volume;
    t.striscia?.classList.toggle("zitta", zitto);
  }
}

// I colori delle tracce, come le strisce di un mixer.
const COLORI = { bass: "#ffb020", drums: "#ff3d81", other: "#2de2e6", vocals: "#a78bfa", guitar: "#7cff6b", piano: "#60a5fa" };
const tabella = document.getElementById("tracce");
for (const t of tracce) {
  const riga = document.createElement("div");
  riga.className = "striscia";
  riga.style.setProperty("--c", COLORI[t.nome] || "#ffb020");
  riga.innerHTML = `<canvas width="14" height="92"></canvas><span class="nome">${t.nome}</span>
    <span class="tasti"><button class="spegni">suona</button><button class="solo">solo</button></span>
    <input type="range" min="0" max="100" value="100">`;
  t.metro = riga.querySelector("canvas");
  t.striscia = riga;
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
// La casella è larga abbastanza per il tasto più lungo col suo segno, più un
// trattino: senza, 12 seguito da 9 si leggeva «129», e h2 seguito da 2 «h22».
const CELLA = Math.min(4, 1 + Math.max(1, ...DATI.note.map(n => String(n.tasto).length + (n.segno || "").length)));
const SPIEGA = { h: "legato in salita (hammer-on)", p: "legato in discesa (pull-off)", "/": "glissato in salita",
                 "\\\\": "glissato in discesa", b: "bending", "~": "vibrato", tr: "trillo" };
const PREFISSO = 3;  // " G|"
const tab = document.getElementById("tab");
const PB = DATI.perBattuta;
const battuteTotali = Math.ceil(DATI.celle / PB);
const partenza = DATI.partenza ??
  (DATI.note.length ? DATI.note[0].quando - DATI.note[0].cella * DATI.durataCella : 0);
let notaIn = new Map(DATI.note.map(n => [`${n.corda}:${n.cella}`, n]));
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
}

// Le viste: la nostra tablatura, accordi e testo, e Guitar Pro quando c'è.
let scegliVista = () => {};
{
  const vista = document.getElementById("vista");
  const vistaAccordi = vista.querySelector('[data-vista="accordi"]');
  vistaAccordi.hidden = !accordi.length && !(DATI.parole || []).length;
  document.getElementById("vistaGP").hidden = !GP.file;
  vista.hidden = vistaAccordi.hidden && !GP.file;
  {
    scegliVista = nome => {
      if (nome === "gp" && !GP.file) nome = "tab";
      document.body.classList.toggle("soloaccordi", nome === "accordi");
      document.body.classList.toggle("sologp", nome === "gp");
      if (nome === "gp") apriGP();
      for (const x of vista.querySelectorAll("button")) x.classList.toggle("attivo", x.dataset.vista === nome);
      try { localStorage.setItem("vista", nome); } catch {}
    };
    for (const b of vista.querySelectorAll("button")) b.onclick = () => scegliVista(b.dataset.vista);
    // La vista scelta l'ultima volta vale anche per la canzone dopo.
    let ricordata = location.hash === "#accordi" ? "accordi" : null;
    try { ricordata ??= localStorage.getItem("vista"); } catch {}
    // «gp» si rimette alla fine, quando la parte Guitar Pro è pronta.
    if (ricordata === "accordi") scegliVista(ricordata);
    VISTA_RICORDATA = ricordata;
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

// ---------------------------------------------------------------- i giri
// Il trascrittore sente ogni ripetizione del giro un po' diversa: una nota in
// più qui, un ribattuto perso là. Il bassista invece suona quasi sempre lo
// stesso giro. Si raggruppano le battute che si somigliano, si fa il «giro
// medio» (in ogni punto della battuta la nota che c'è nella maggior parte
// delle ripetizioni), e le battute vicine al giro medio diventano uguali a
// lui. Quelle davvero diverse restano come sono: sono le variazioni.
const SOMIGLIA = 0.6, NORMALIZZA = 0.7, MINIMO_GIRO = 3;
const chiave = n => `${n.corda}:${n.tasto}`;

function somiglianza(a, b) {
  // a, b: Map(punto della battuta -> nota). Una nota vale se l'altra battuta
  // ha la stessa nota nello stesso punto o in quello accanto.
  if (!a.size || !b.size) return 0;
  const usate = new Set();
  let pari = 0;
  for (const [punto, n] of a) {
    for (const d of [0, -1, 1]) {
      const m = b.get(punto + d);
      if (m && !usate.has(punto + d) && chiave(m) === chiave(n)) { usate.add(punto + d); pari++; break; }
    }
  }
  return pari / Math.max(a.size, b.size);
}

function trovaGiri(note) {
  const battute = Array.from({ length: battuteTotali }, () => new Map());
  for (const n of note) {
    const b = Math.floor(n.cella / PB), punto = n.cella % PB;
    if (!battute[b].has(punto)) battute[b].set(punto, n);
  }
  const gruppi = [];   // { modello, membri: [b] }
  battute.forEach((m, b) => {
    if (m.size < 2) return;
    let migliore = null, punteggio = SOMIGLIA;
    for (const g of gruppi) {
      const s = somiglianza(m, g.modello);
      if (s >= punteggio) { migliore = g; punteggio = s; }
    }
    if (migliore) migliore.membri.push(b);
    else gruppi.push({ modello: m, membri: [b] });
  });

  const pulite = new Map(battute.map((m, b) => [b, m]));
  const etichette = new Map();
  let lettera = 0;
  for (const g of gruppi.filter(g => g.membri.length >= MINIMO_GIRO)) {
    // Il giro medio: in ogni punto vince la nota più frequente, o il silenzio.
    const medio = new Map();
    for (let punto = 0; punto < PB; punto++) {
      const voti = new Map();
      let vuoti = 0;
      for (const b of g.membri) {
        const n = battute[b].get(punto);
        if (!n) { vuoti++; continue; }
        const k = chiave(n);
        voti.set(k, (voti.get(k) || { n, conta: 0 })), voti.get(k).conta++;
      }
      const primo = [...voti.values()].sort((x, y) => y.conta - x.conta)[0];
      if (primo && primo.conta > vuoti) medio.set(punto, primo.n);
    }
    const nome = String.fromCharCode(65 + (lettera++ % 26));
    for (const b of g.membri) {
      const vicina = somiglianza(battute[b], medio) >= NORMALIZZA;
      etichette.set(b, { nome, variazione: !vicina, volte: g.membri.length });
      if (vicina) {
        pulite.set(b, new Map([...medio].map(([punto, n]) => {
          const cella = b * PB + punto;
          return [punto, { corda: n.corda, tasto: n.tasto, cella, quando: +(partenza + cella * DATI.durataCella).toFixed(3) }];
        })));
      }
    }
  }
  const tutte = [];
  for (const m of pulite.values()) tutte.push(...m.values());
  // Le note su altre corde nella stessa casella (accordi) restano dall'originale.
  for (const n of note) {
    const b = Math.floor(n.cella / PB);
    if (pulite.get(b) === battute[b] && battute[b].get(n.cella % PB) !== n) tutte.push(n);
  }
  tutte.sort((x, y) => x.cella - y.cella || x.corda - y.corda);
  return { note: tutte, etichette };
}

const GIRI = trovaGiri(DATI.note);
let giroPulito = true;
try { giroPulito = localStorage.getItem("giro") !== "sentito"; } catch {}
let noteAttive = giroPulito ? GIRI.note : DATI.note;
notaIn = new Map(noteAttive.map(n => [`${n.corda}:${n.cella}`, n]));

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
    if (GIRI.etichette.size) {
      // Sopra ogni battuta, il giro a cui appartiene: «A», o «A*» se è una variazione.
      const sopra = document.createElement("div");
      sopra.className = "giri";
      let colonna = 0;
      for (let b = b0; b < Math.min(battuteTotali, b0 + perRigo); b++) {
        const e = GIRI.etichette.get(b);
        if (!e) continue;
        const dove = PREFISSO + (b - b0) * (PB * CELLA + 1);
        sopra.append(" ".repeat(Math.max(0, dove - colonna)));
        const s = document.createElement("span");
        s.className = e.variazione ? "giro variazione" : "giro";
        s.textContent = `giro ${e.nome}${e.variazione ? "*" : ""}`;
        s.title = e.variazione ? `variazione del giro ${e.nome}` : `giro ${e.nome}, ripetuto ${e.volte} volte`;
        sopra.append(s);
        colonna = dove + s.textContent.length;
      }
      if (sopra.childNodes.length) rigo.append(sopra);
    }
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
        if (nota && nota.segno) {
          // h p / \ vanno prima del tasto (5h7), b ~ tr dopo (7b, 7~).
          const prima = ["h", "p", "/", "\\\\"].includes(nota.segno);
          const seg = `<b class="seg" title="${SPIEGA[nota.segno] || ""}">${nota.segno}</b>`;
          const testo = prima ? seg + nota.tasto : nota.tasto + seg;
          const lungo = String(nota.tasto).length + nota.segno.length;
          span.innerHTML = testo + "-".repeat(Math.max(0, CELLA - lungo));
        } else {
          span.textContent = nota ? String(nota.tasto).padEnd(CELLA, "-") : "-".repeat(CELLA);
        }
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

{
  // La legenda dei segni, solo quelli che in questa canzone ci sono.
  const usati = [...new Set(DATI.note.map(n => n.segno).filter(Boolean))];
  const legenda = document.getElementById("legenda");
  legenda.hidden = !usati.length;
  for (const s of usati) {
    const voce = document.createElement("span");
    voce.innerHTML = `<b>${s}</b>`;
    voce.append(SPIEGA[s] || "");
    legenda.append(voce);
  }
}

{
  const b = document.getElementById("bGiro");
  b.hidden = !GIRI.etichette.size;
  const mostra = () => { b.classList.toggle("attivo", giroPulito); b.textContent = giroPulito ? "Giro pulito" : "Come l'ha sentito"; };
  mostra();
  b.onclick = () => {
    giroPulito = !giroPulito;
    try { localStorage.setItem("giro", giroPulito ? "pulito" : "sentito"); } catch {}
    noteAttive = giroPulito ? GIRI.note : DATI.note;
    notaIn = new Map(noteAttive.map(n => [`${n.corda}:${n.cella}`, n]));
    mostra();
    disegna();
  };
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
  if (guida.paused) { accendiAudio(); audio.forEach(a => { a.currentTime = guida.currentTime; a.play(); }); via.textContent = "⏸"; at?.play(); }
  else { audio.forEach(a => a.pause()); via.textContent = "▶"; at?.pause(); }
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

  const vicina = noteAttive.reduce(
    (scelta, n) => (n.quando <= ora + DATI.durataCella / 2 ? n : scelta), null);
  const chiave = vicina ? `${vicina.corda}:${vicina.cella}` : null;
  if (chiave !== acceso) {
    if (acceso) caselle.get(acceso)?.classList.remove("ora");
    if (chiave) caselle.get(chiave)?.classList.add("ora");
    acceso = chiave;
  }
}, 100);

// ---------------------------------------------------------------- luci e livelli
// Ogni traccia passa da un analizzatore: da lì escono i livelli delle
// strisce, lo spettro nella barra e il bagliore dello sfondo. L'AudioContext
// nasce al primo «suona», perché il browser lo permette solo dopo un clic.
let contesto = null, analisiTotale = null;
function accendiAudio() {
  if (contesto) return contesto.resume();
  contesto = new AudioContext();
  analisiTotale = contesto.createAnalyser();
  analisiTotale.fftSize = 2048;
  analisiTotale.smoothingTimeConstant = 0.78;
  analisiTotale.connect(contesto.destination);
  for (const t of tracce) {
    const sorgente = contesto.createMediaElementSource(t.audio);
    t.guadagno = contesto.createGain();
    t.analisi = contesto.createAnalyser();
    t.analisi.fftSize = 1024;
    sorgente.connect(t.guadagno).connect(t.analisi).connect(analisiTotale);
    t.audio.volume = 1;
  }
  applicaVolumi();
}

const spettro = document.getElementById("spettro");
const lampo = document.getElementById("lampo");
const battitiEl = [...document.querySelectorAll("#battiti i")];
const accordoOra = document.getElementById("accordoOra");
const accordoDopo = document.getElementById("accordoDopo");
const BATTITO = DATI.durataCella * 4;
let luci = true;
try { luci = localStorage.getItem("luci") !== "spente"; } catch {}
const bottoneLuci = document.getElementById("luci");
const mostraLuci = () => { bottoneLuci.classList.toggle("attivo", luci); bottoneLuci.textContent = luci ? "Luci accese" : "Luci spente"; };
mostraLuci();
bottoneLuci.onclick = () => { luci = !luci; try { localStorage.setItem("luci", luci ? "accese" : "spente"); } catch {} mostraLuci(); };

let ultimoBattito = -1, ultimoAccordo = null, picchi = new Map(), bagliore = 0;
const campioni = new Float32Array(1024);
let frequenze = null;

function disegnaMetro(t) {
  const c = t.metro, g = c.getContext("2d");
  let livello = 0;
  if (t.analisi && !guida.paused) {
    t.analisi.getFloatTimeDomainData(campioni);
    let somma = 0;
    for (let i = 0; i < t.analisi.fftSize; i++) somma += campioni[i] * campioni[i];
    livello = Math.min(1, Math.sqrt(somma / t.analisi.fftSize) * 3.2);
  }
  const picco = Math.max(livello, (picchi.get(t.nome) || 0) - 0.012);
  picchi.set(t.nome, picco);
  g.clearRect(0, 0, c.width, c.height);
  const tacche = 18, alta = c.height / tacche;
  const colore = COLORI[t.nome] || "#ffb020";
  for (let i = 0; i < tacche; i++) {
    const soglia = (i + 1) / tacche;
    g.fillStyle = soglia <= livello ? (i > tacche - 3 ? "#ff3d81" : colore) : "#ffffff10";
    g.fillRect(2, c.height - (i + 1) * alta + 1, c.width - 4, alta - 2);
  }
  g.fillStyle = "#fff";
  g.fillRect(2, c.height - Math.max(1, Math.round(picco * tacche)) * alta + 1, c.width - 4, 2);
}

function disegnaSpettro() {
  const r = spettro.getBoundingClientRect(), dpr = devicePixelRatio || 1;
  if (spettro.width !== Math.round(r.width * dpr)) { spettro.width = Math.round(r.width * dpr); spettro.height = Math.round(r.height * dpr); }
  const g = spettro.getContext("2d"), L = spettro.width, A = spettro.height;
  g.clearRect(0, 0, L, A);
  if (!analisiTotale) return 0;
  frequenze ??= new Uint8Array(analisiTotale.frequencyBinCount);
  analisiTotale.getByteFrequencyData(frequenze);
  const barre = Math.max(24, Math.floor(L / (7 * dpr)));
  const passo = L / barre;
  const sfumatura = g.createLinearGradient(0, 0, L, 0);
  sfumatura.addColorStop(0, "#ffb020"); sfumatura.addColorStop(.5, "#ff3d81"); sfumatura.addColorStop(1, "#2de2e6");
  g.fillStyle = sfumatura;
  let bassi = 0;
  for (let i = 0; i < barre; i++) {
    // Scala logaritmica: i bassi occupano spazio quanto gli acuti, come all'orecchio.
    const da = Math.floor(Math.pow(frequenze.length, i / barre)), a = Math.max(da + 1, Math.floor(Math.pow(frequenze.length, (i + 1) / barre)));
    let m = 0;
    for (let j = da; j < a && j < frequenze.length; j++) m = Math.max(m, frequenze[j]);
    const h = (m / 255) ** 1.6 * (A - 8 * dpr);
    g.globalAlpha = 0.85;
    g.fillRect(i * passo + 1, (A - 6 * dpr) - h, passo - 2 * dpr, h);
    if (i < barre / 6) bassi += m / 255;
  }
  g.globalAlpha = 1;
  return bassi / (barre / 6);
}

function giro() {
  const ora = guida.currentTime;
  // La tablatura Guitar Pro segue il nostro audio, non il contrario.
  try { at?.player?.output?.updatePosition?.(ora * 1000); } catch {}
  tracce.forEach(disegnaMetro);
  const bassi = guida.paused ? 0 : disegnaSpettro();
  if (guida.paused && analisiTotale) disegnaSpettro();
  // Il bagliore dello sfondo respira coi bassi.
  bagliore = Math.max(bassi, bagliore * 0.9);
  document.documentElement.style.setProperty("--respiro", bagliore.toFixed(3));

  // I movimenti: il primo della battuta rosa, gli altri azzurri; sul primo, se le luci sono accese, un lampo.
  const n = Math.floor((ora - partenza) / BATTITO + 1e-6);
  if (!guida.paused && n !== ultimoBattito && ora >= partenza) {
    ultimoBattito = n;
    const m = ((n % 4) + 4) % 4;
    battitiEl.forEach((b, i) => b.classList.toggle("su", i === m));
    if (luci) {
      lampo.animate([{ opacity: m === 0 ? 0.22 : 0.07 }, { opacity: 0 }], { duration: m === 0 ? 260 : 160, easing: "ease-out" });
    }
  }
  if (guida.paused) battitiEl.forEach(b => b.classList.remove("su"));

  // L'accordo che suona, in grande, e quello che arriva.
  let k = -1;
  while (k + 1 < accordi.length && accordi[k + 1].quando <= ora) k++;
  const nome = k >= 0 ? accordi[k].nome : "—";
  if (nome !== ultimoAccordo) {
    ultimoAccordo = nome;
    accordoOra.textContent = nome;
    accordoOra.classList.add("salto");
    setTimeout(() => accordoOra.classList.remove("salto"), 120);
  }
  const dopo = accordi[k + 1];
  accordoDopo.textContent = dopo ? `poi ${dopo.nome} tra ${Math.max(0, dopo.quando - ora).toFixed(1)}s` : "";
  if (guida.duration) scorri.style.setProperty("--fatto", (ora / guida.duration * 100).toFixed(2) + "%");
  requestAnimationFrame(giro);
}
if (!accordi.length) document.querySelector(".ora-accordo").style.visibility = "hidden";
requestAnimationFrame(giro);

// La barra spaziatrice suona e ferma, come in ogni programma di musica.
addEventListener("keydown", e => {
  if (e.code === "Space" && !/INPUT|BUTTON/.test(document.activeElement.tagName)) { e.preventDefault(); via.click(); }
});

// ---------------------------------------------------------------- Guitar Pro
// La tablatura vera, da un file Guitar Pro, disegnata da alphaTab e fatta
// scorrere sulle nostre tracce separate. Il file ha un tempo suo, il disco un
// altro: la sincronia dice a che istante del disco comincia ogni battuta, e
// la si trova confrontando le note del file con quelle che abbiamo sentito.
let gpManuale = false;
function disegnaStrumenti() {
  // Una fila di pulsanti, uno per traccia del file: si vede subito cosa c'è.
  const fila = document.getElementById("gpStrumenti");
  fila.textContent = "";
  gpScore.tracks.forEach((t, i) => {
    const tipo = strumentoDi(t);
    const b = document.createElement("button");
    b.className = "strumento" + (i === gpTraccia ? " attivo" : "") + (tipo === "Basso" ? " basso" : "");
    b.innerHTML = `<span class="icona">${ICONE[tipo] || "🎵"}</span><span><b></b><small></small></span>`;
    b.querySelector("b").textContent = t.name?.trim() || tipo;
    b.querySelector("small").textContent = t.name?.trim() ? tipo : `traccia ${i + 1}`;
    b.onclick = () => {
      gpTraccia = i; gpManuale = true;
      disegnaStrumenti();
      at.renderTracks([gpScore.tracks[i]]);
      applicaPunti(gpPunti);
    };
    fila.append(b);
  });
  if (!gpScore.tracks.some(t => strumentoDi(t) === "Basso") && (DATI.strumento || "").includes("basso")) {
    statoGP.textContent = "In questo file non c'è il basso: con «Guitar Pro…» scegline un altro.";
  }
}
let at = null, gpScore = null, gpTraccia = 0, gpTempi = [], gpPunti = [];
const statoGP = document.getElementById("gpStato");

function caricaScript(src) {
  return new Promise((ok, ko) => { const s = document.createElement("script"); s.src = src; s.onload = ok; s.onerror = ko; document.head.append(s); });
}

// Le battute nell'ordine in cui si suonano (con i ritornelli), e quando cadono
// nel tempo del file: millisecondi dall'inizio, al tempo scritto.
function tempiDelFile(score) {
  const fuori = [];
  let bpm = score.tempo || 120, t = 0, i = 0, inizioRip = 0;
  const giri = new Map();
  while (i < score.masterBars.length && fuori.length < 5000) {
    const mb = score.masterBars[i];
    if (mb.isRepeatStart) inizioRip = i;
    for (const a of mb.tempoAutomations || []) bpm = a.value || bpm;
    const durata = mb.calculateDuration() / 960 * 60000 / bpm;
    const occ = fuori.filter(x => x.bar === i).length;
    fuori.push({ bar: i, occ, inizio: t, durata, bpm });
    t += durata;
    if (mb.repeatCount > 0) {
      const fatti = giri.get(i) || 0;
      if (fatti < mb.repeatCount - 1) { giri.set(i, fatti + 1); i = inizioRip; continue; }
      giri.delete(i);
    }
    i++;
  }
  return fuori;
}

// Ogni quanto si confronta: un decimo di secondo.
const PASSO_SYNC = 100;
function suoniDelFile(traccia) {
  // La nota che suona in ogni decimo di secondo, nel tempo del file (classe di altezza, -1 = niente).
  const fine = gpTempi.length ? gpTempi.at(-1).inizio + gpTempi.at(-1).durata : 0;
  const quadri = new Int8Array(Math.ceil(fine / PASSO_SYNC) + 1).fill(-1);
  const staff = traccia.staves[0];
  for (const o of gpTempi) {
    const bar = staff.bars[o.bar];
    if (!bar) continue;
    const durataBar = gpScore.masterBars[o.bar].calculateDuration();
    for (const voce of bar.voices) for (const beat of voce.beats) {
      if (beat.isRest || !beat.notes.length) continue;
      const nota = beat.notes.reduce((a, b) => (a.realValue < b.realValue ? a : b));
      const da = o.inizio + beat.playbackStart / durataBar * o.durata;
      const a = da + beat.playbackDuration / durataBar * o.durata;
      for (let q = Math.floor(da / PASSO_SYNC); q < Math.min(quadri.length, Math.ceil(a / PASSO_SYNC)); q++) quadri[q] = nota.realValue % 12;
    }
  }
  return quadri;
}
function suoniDelDisco() {
  const corde = DATI.cordeMidi || [];
  const fine = (guida.duration || 0) * 1000;
  const quadri = new Int8Array(Math.ceil(fine / PASSO_SYNC) + 1).fill(-1);
  const note = [...DATI.note].sort((a, b) => a.quando - b.quando);
  note.forEach((n, k) => {
    if (corde[n.corda] === undefined) return;
    const da = n.quando * 1000, a = Math.min(da + 500, k + 1 < note.length ? note[k + 1].quando * 1000 : da + 500);
    for (let q = Math.floor(da / PASSO_SYNC); q < Math.min(quadri.length, Math.ceil(a / PASSO_SYNC)); q++) quadri[q] = (corde[n.corda] + n.tasto) % 12;
  });
  return quadri;
}

// Allineamento dinamico (DTW) fra le due sequenze: restituisce, per ogni
// decimo di secondo del file, il decimo di secondo del disco.
function allinea(a, b) {
  const N = a.length, M = b.length;
  const costo = (x, y) => (x < 0 && y < 0 ? 0.2 : x < 0 || y < 0 ? 0.6 : x === y ? 0 : 1);
  const da = new Uint8Array(N * M);
  let prima = new Float32Array(M).fill(Infinity), ora = new Float32Array(M);
  for (let i = 0; i < N; i++) {
    for (let j = 0; j < M; j++) {
      const c = costo(a[i], b[j]);
      if (i === 0 && j === 0) { ora[j] = c; continue; }
      const diag = i > 0 && j > 0 ? prima[j - 1] : Infinity;
      const su = i > 0 ? prima[j] + 0.15 : Infinity;
      const sx = j > 0 ? ora[j - 1] + 0.15 : Infinity;
      if (diag <= su && diag <= sx) { ora[j] = diag + c; da[i * M + j] = 0; }
      else if (su <= sx) { ora[j] = su + c; da[i * M + j] = 1; }
      else { ora[j] = sx + c; da[i * M + j] = 2; }
    }
    [prima, ora] = [ora, prima];
  }
  const verso = new Int32Array(N);
  let i = N - 1, j = M - 1;
  while (i >= 0 && j >= 0) {
    verso[i] = j;
    const d = da[i * M + j];
    if (i === 0 && j === 0) break;
    if (d === 0) { i--; j--; } else if (d === 1) i--; else j--;
  }
  return verso;
}

function sincroniaAutomatica() {
  const file = suoniDelFile(gpScore.tracks[gpTraccia]);
  const disco = suoniDelDisco();
  if (!file.length || !disco.length) return [];
  // Il DTW costa N×M: oltre i 6000 decimi (10 minuti) si dimezza il dettaglio.
  const verso = allinea(file, disco);
  return gpTempi.map(o => ({
    barIndex: o.bar, barOccurence: o.occ, barPosition: 0,
    millisecondOffset: verso[Math.min(verso.length - 1, Math.round(o.inizio / PASSO_SYNC))] * PASSO_SYNC,
  }));
}

function applicaPunti(punti, salva = true) {
  gpPunti = punti;
  gpScore.applyFlatSyncPoints(punti);
  at.updateSyncPoints();
  if (salva) fetch("/api/sincronia", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id: GP.id, sincronia: { v: 2, traccia: gpTraccia, manuale: gpManuale, punti } }) }).catch(() => {});
}

// Lo strumento di una traccia, dal suono che il file le assegna (i numeri
// General MIDI) e non dal nome: molti file hanno le tracce senza nome.
const FAMIGLIE = ["Pianoforte", "Percussioni", "Organo", "Chitarra", "Basso", "Archi", "Archi", "Ottoni",
                  "Fiati", "Flauti", "Synth", "Synth", "Effetti", "Etnici", "Percussioni", "Effetti"];
const ICONE = { Pianoforte: "🎹", Organo: "🎹", Chitarra: "🎸", Basso: "🎸", Batteria: "🥁", Archi: "🎻", Ottoni: "🎺",
                Fiati: "🎷", Flauti: "🪈", Synth: "🎛️", Voce: "🎤" };
function strumentoDi(t) {
  if (t.playbackInfo?.primaryChannel === 9 || t.staves[0]?.isPercussion) return "Batteria";
  if (/voc|voz|voix|voice|vox|sing|canto|coro|choir/i.test(t.name || "")) return "Voce";
  const p = t.playbackInfo?.program ?? 0;
  return FAMIGLIE[Math.floor(p / 8)] || "Strumento";
}
function tracciaDelBasso(score) {
  const vuole = (DATI.strumento || "").includes("basso") ? "Basso" : "Chitarra";
  const indice = score.tracks.findIndex(t => strumentoDi(t) === vuole);
  return Math.max(0, indice);
}

async function apriGP() {
  if (at || !GP.file) return;
  statoGP.textContent = "Carico la tablatura…";
  await caricaScript("/pwa/alphatab/alphaTab.min.js");
  at = new alphaTab.AlphaTabApi(document.getElementById("alphaTab"), {
    core: { file: GP.file, fontDirectory: "/pwa/alphatab/font/", scriptFile: "/pwa/alphatab/alphaTab.min.js", useWorkers: false },
    display: { staveProfile: alphaTab.StaveProfile.Tab, resources: { mainGlyphColor: "#d9dcea", secondaryGlyphColor: "#9aa0b4",
               staffLineColor: "#ffffff33", barSeparatorColor: "#ffffff44", scoreInfoColor: "#eef0f6" } },
    player: { playerMode: alphaTab.PlayerMode.EnabledExternalMedia, enableCursor: true, enableAnimatedBeatCursor: true,
              enableUserInteraction: true, scrollMode: alphaTab.ScrollMode.Continuous, scrollOffsetY: -180 },
  });
  at.playerReady.on(() => {
    at.player.output.handler = {
      get backingTrackDuration() { return (guida.duration || 0) * 1000; },
      get playbackRate() { return guida.playbackRate; }, set playbackRate(v) {},
      get masterVolume() { return 1; }, set masterVolume(v) {},
      seekTo(ms) { audio.forEach(a => { a.currentTime = ms / 1000; }); },
      play() { if (guida.paused) via.click(); },
      pause() { if (!guida.paused) via.click(); },
    };
  });
  at.scoreLoaded.on(async score => {
    gpScore = score;
    gpTempi = tempiDelFile(score);
    const salvata = await fetch("/api/sincronia?id=" + encodeURIComponent(GP.id)).then(r => r.json()).catch(() => ({}));
    // La traccia salvata vale solo se l'hai scelta tu; se no si parte dal basso.
    gpTraccia = salvata.manuale ? salvata.traccia : tracciaDelBasso(score);
    disegnaStrumenti();
    at.renderTracks([score.tracks[gpTraccia]]);
    const pronto = () => {
      // La sincronia salvata vale se era fatta sulla stessa traccia (o sistemata a mano).
      if (salvata.punti && salvata.punti.length && (salvata.manuale || (salvata.v === 2 && salvata.traccia === gpTraccia))) {
        gpManuale = !!salvata.manuale; applicaPunti(salvata.punti, false); statoGP.textContent = "Sincronia salvata.";
      }
      else { statoGP.textContent = "Sincronizzo con le note sentite…"; setTimeout(() => { applicaPunti(sincroniaAutomatica()); statoGP.textContent = "Sincronizzata in automatico. Se una battuta parte storta: falla suonare e cliccala nel momento giusto."; }, 30); }
    };
    if (guida.duration) pronto(); else guida.addEventListener("loadedmetadata", pronto, { once: true });
  });
  // Correzione a mano: mentre suona, un clic su una battuta dice «comincia adesso».
  at.beatMouseDown.on(beat => {
    if (!gpPunti.length || guida.paused) return;
    const bar = beat.voice.bar.index, adesso = guida.currentTime * 1000;
    let k = -1, distanza = Infinity;
    gpPunti.forEach((p, i) => { if (p.barIndex === bar && Math.abs(p.millisecondOffset - adesso) < distanza) { k = i; distanza = Math.abs(p.millisecondOffset - adesso); } });
    if (k < 0) return;
    const delta = adesso - gpPunti[k].millisecondOffset;
    applicaPunti(gpPunti.map((p, i) => (i >= k ? { ...p, millisecondOffset: Math.max(0, p.millisecondOffset + delta) } : p)));
    statoGP.textContent = `Battuta ${bar + 1} agganciata a ${orologio(adesso / 1000)}.`;
  });
  gpManuale = false;
  document.getElementById("gpPrima").onclick = () => applicaPunti(gpPunti.map(p => ({ ...p, millisecondOffset: Math.max(0, p.millisecondOffset - 100) })));
  document.getElementById("gpDopo").onclick = () => applicaPunti(gpPunti.map(p => ({ ...p, millisecondOffset: p.millisecondOffset + 100 })));
  document.getElementById("gpRifai").onclick = () => { applicaPunti(sincroniaAutomatica()); statoGP.textContent = "Rifatta la sincronia automatica."; };
}

// Scegliere la tablatura: dall'archivio Guitar Pro, o un file scaricato da te.
async function scegliGP() {
  const d = document.getElementById("dGP");
  const elenco = document.getElementById("gpElenco");
  elenco.innerHTML = "<p>Cerco nell'archivio…</p>";
  d.showModal();
  const trovate = await fetch("/api/gp/cerca?id=" + encodeURIComponent(GP.id)).then(r => r.json()).catch(() => []);
  elenco.textContent = "";
  if (!trovate.length) elenco.innerHTML = "<p>Nell'archivio non c'è. Carica un file Guitar Pro scaricato da te.</p>";
  for (const t of trovate) {
    const r = document.createElement("button");
    r.className = "gpVoce";
    r.innerHTML = `<b></b><small></small>`;
    r.querySelector("b").textContent = t.nome.split("/").slice(-1)[0];
    r.querySelector("small").textContent = (t.ha ? "✓ " : "✗ ") + (t.strumenti || []).join(", ");
    if (t.ha) r.classList.add("ha");
    r.title = t.archivio + " · " + t.nome;
    r.onclick = async () => {
      r.disabled = true;
      await fetch("/api/gp/scegli", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ id: GP.id, archivio: t.archivio, nome: t.nome }) });
      try { localStorage.setItem("vista", "gp"); } catch {}
      location.reload();
    };
    elenco.append(r);
  }
}
document.getElementById("gpFile").onchange = async e => {
  const f = e.target.files[0];
  if (!f) return;
  await fetch(`/api/gp/carica?id=${encodeURIComponent(GP.id)}&nome=${encodeURIComponent(f.name)}`, { method: "POST", body: await f.arrayBuffer() });
  try { localStorage.setItem("vista", "gp"); } catch {}
  location.reload();
};
document.getElementById("bGP").onclick = scegliGP;
document.querySelector("#dGP .chiudi").onclick = () => document.getElementById("dGP").close();
if (VISTA_RICORDATA === "gp" && GP.file) scegliVista("gp");
</script>
</html>
"""


ITALIANO = {"C": "Do", "C#": "Do#", "D": "Re", "D#": "Re#", "E": "Mi", "F": "Fa", "F#": "Fa#", "G": "Sol",
            "G#": "Sol#", "A": "La", "A#": "La#", "B": "Si"}


def accordatura(strumento: str, corde: list[str]) -> str:
    """«Drop D · Re La Re Sol»: come va accordato lo strumento, ben in vista."""
    nomi = " ".join(ITALIANO.get(c, c) for c in corde)
    tipo = "Drop D" if "drop" in strumento.lower() else "Standard"
    return f"<b>{tipo}</b> {html.escape(nomi)}"


def pagina(
    titolo: str, strumento: str, bpm: float, tab: dict, tracce: list[dict], copertina: str = "", album: str = "",
    guitarpro: str = "", id_canzone: str = "",
) -> str:
    """La pagina di una canzone, come testo."""
    return (
        PAGINA.replace("__GUITARPRO__", json.dumps({"file": guitarpro, "id": id_canzone}))
        .replace("__ACCORDATURA__", accordatura(strumento, tab.get("corde", [])))
        .replace("__COPERTINA__", html.escape(copertina, quote=True))
        .replace("__ALBUM__", html.escape(album))
        .replace("__TITOLO__", titolo)
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
