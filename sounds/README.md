# Audio source files (Track C — C64 scene)

Originals downloaded from [freesound.org](https://freesound.org), all under **CC0** (public domain). No attribution legally required, but kept here for provenance.

| File | Source page | Used for |
|---|---|---|
| `source/crton.mp3` | _(add freesound URL)_ | CRT power-on / degauss thunk |
| `source/harddrive.mp3` | _(add freesound URL)_ | HDD spin-up + clicks |
| `source/keyboardtyping-short.mp3` | _(add freesound URL)_ | Auto-typing keystroke loop |
| `source/keyboardtyping-long.mp3` | _(add freesound URL)_ | (unused — preserved as alternate) |
| `source/modemsound.mp3` | _(add freesound URL)_ | Dial-up modem handshake |

## Web-optimized cuts

Production scene loads trimmed/transcoded versions from `docs/scene/audio/` (mono, 96 kbps, with fade in/out). See `scripts/encode-scene-audio.sh` for the exact ffmpeg recipe used to regenerate them.

| Web file | Size | Length |
|---|---|---|
| `crt-on.mp3` | ~22 KB | 1.8s |
| `hdd-spinup.mp3` | ~72 KB | 6.0s |
| `keytype.mp3` | ~36 KB | 3.0s |
| `modem-handshake.mp3` | ~227 KB | 19.3s |
| **Total** | **~360 KB** | lazy-loaded only when "Terminal" theme selected |
