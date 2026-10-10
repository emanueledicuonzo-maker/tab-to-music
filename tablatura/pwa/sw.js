// L'app anche a programma spento: la finestra, l'elenco delle canzoni e le
// canzoni già aperte una volta si riaprono dalla cache. Importare no: quello
// lo fa il programma Python, e senza di lui non si può.
const GUSCIO = "tablatura-guscio-v1";
const CANZONI = "tablatura-canzoni-v1";

self.addEventListener("install", e => {
  e.waitUntil(caches.open(GUSCIO).then(c => c.addAll(["/", "/pwa/manifest.webmanifest", "/pwa/icona-192.png", "/pwa/icona-512.png"])));
  self.skipWaiting();
});
self.addEventListener("activate", e => e.waitUntil(self.clients.claim()));

// Prima la rete (così, col programma acceso, si vede sempre l'ultima versione),
// poi la copia salvata.
async function primaLaRete(richiesta, cassa) {
  try {
    const risposta = await fetch(richiesta);
    if (risposta.ok && risposta.status === 200) (await caches.open(cassa)).put(richiesta, risposta.clone());
    return risposta;
  } catch {
    const salvata = await caches.match(richiesta);
    if (salvata) return salvata;
    throw new Error("spento");
  }
}

// Le tracce si chiedono a pezzi (Range): dalla cache si serve il pezzo
// ritagliato dal file intero, che si scarica la prima volta che la canzone suona.
async function traccia(richiesta) {
  const url = new URL(richiesta.url); url.search = "";
  const cassa = await caches.open(CANZONI);
  let intera = await cassa.match(url.href);
  if (!intera) {
    try {
      const risposta = await fetch(richiesta);
      // In sottofondo, il file intero per la volta che il programma sarà spento.
      fetch(url.href).then(r => { if (r.ok && r.status === 200) cassa.put(url.href, r); }).catch(() => {});
      return risposta;
    } catch { return new Response("", { status: 504 }); }
  }
  const intervallo = richiesta.headers.get("Range");
  if (!intervallo) return intera;
  const dati = await intera.blob();
  const [, da, a] = /bytes=(\d*)-(\d*)/.exec(intervallo) || [];
  const inizio = Number(da || 0), fine = a ? Number(a) : dati.size - 1;
  return new Response(dati.slice(inizio, fine + 1), {
    status: 206,
    headers: { "Content-Type": intera.headers.get("Content-Type") || "audio/wav",
               "Content-Range": `bytes ${inizio}-${fine}/${dati.size}`, "Content-Length": String(fine - inizio + 1), "Accept-Ranges": "bytes" },
  });
}

self.addEventListener("fetch", e => {
  const url = new URL(e.request.url);
  if (url.origin !== location.origin || e.request.method !== "GET") return;
  if (url.pathname.endsWith(".wav")) return e.respondWith(traccia(e.request));
  if (url.pathname === "/api/stato") {
    // A programma spento si risponde «niente in coda», e la finestra lo dice.
    return e.respondWith(fetch(e.request).catch(() => new Response(JSON.stringify({ coda: [], fasi: [], preferenze: {}, spento: true }),
      { headers: { "Content-Type": "application/json" } })));
  }
  if (url.pathname.startsWith("/api/sfoglia") || url.pathname.startsWith("/api/importa")) return;
  const cassa = url.pathname.startsWith("/tab/") ? CANZONI : GUSCIO;
  e.respondWith(primaLaRete(e.request, cassa));
});
