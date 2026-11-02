# Night Survivors

A small pygame-ce survival game, playable on desktop and on phones through pygbag.

Hold and move a finger to walk; lift it to stop. On desktop, move the mouse. Weapons attack automatically. Collect gems and tap an upgrade card. Survive for two minutes; tap the end screen to restart. P pauses on desktop.

## Run locally

```sh
python3 -m venv .venv
.venv/bin/python -m pip install pygame-ce pillow pygbag
.venv/bin/python main.py
```

## Rebuild the website

Install FFmpeg, then run `.venv/bin/python build_web.py`. This converts finished WAV sounds to OGG, runs `python -m pygbag --build .`, and copies `build/web` into `docs` with an empty `.nojekyll`. Commit and push the updated `docs` folder. GitHub Pages serves `main` → `/docs`.

The first browser load downloads the Python runtime. Tap the start screen to begin and allow audio. An internet connection is needed for pygbag's runtime CDN.

## Checks and assets

Run `.venv/bin/python -m unittest`. Original art is Kenney CC0; see `raw_art/LICENSE-Kenney-CC0.txt`. `make_assets.py` and `make_sounds.py` are offline generators; the game only loads their finished output. Spoken WAV generation uses macOS's built-in speech tools.
