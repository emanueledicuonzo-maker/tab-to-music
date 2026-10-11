# The .t2m format

A `.t2m` (Tab to Music) file keeps **all the work on one song** in a single, readable JSON file: the tab, how it is synced to a specific recording, and your manual fixes. Tab to Music writes it automatically every time a song is synced or corrected (`<Music>/tab/t2m/Artist - Title.t2m`), and reopens it instead of the archive tab.

```jsonc
{
  "format": "t2m",
  "version": 1,
  "song":      { "artista": "Michael Jackson", "titolo": "Beat It", "album": "HIStory…", "durata": 258.2 },
  "recording": {                       // fingerprint of the recording the tab is synced to
    "file": "01-10-Michael_Jackson-Beat_It-SMR.flac",
    "duration": 258.2,
    "chroma2s": ["0123…", …]           // 12 strings (C…B), one digit 0-9 every 2 seconds
  },
  "source":    { "type": "guitarpro-archive" | "guitarpro-file" | "text-tab", "name": "…" },
  "score":     { … },                  // the notation, as alphaTab's JSON score model
  "view":      { "track": 2 },         // the track shown (bass by default)
  "sync": {
    "automatica":  [0, 1765, 3530, …], // ms in the recording where each played bar starts
                                       // (bars in playback order, repeats expanded)
    "spostamento": 300,                // global offset in ms (the ±0.1 s buttons)
    "correzioni":  { "41": 220 }       // from bar 41 on, an extra offset in ms (click-to-fix)
  },
  "lyrics":    { "source": "lrclib", "lines": [{ "quando": 32.1, "testo": "…" }, …] },
  "credits":   "Tab to Music — https://getaweb.it"
}
```

**Opening a .t2m from elsewhere**: the recording is recognized by title, duration (±8 s) and the chroma fingerprint, then the file is linked to the matching song in your library.

**About sharing**: a `.t2m` contains the notation and, if present, the lyrics of the song, which are copyrighted. Share them only where you are allowed to. The `sync` block alone (bar → time) contains no notes or text.
