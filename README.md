# UDub signs

Station signs for the UDub Minecraft server, made with the **Wayfinder** sign
builder and shown in-game as map art through ImageFrame.

## Making a sign

1. Double-click **`Start Wayfinder.bat`**. The builder opens in your browser at
   <http://127.0.0.1:8765>. Keep the black Wayfinder window open while you work.
2. Build the sign, give it a **Sign name**, and click **Export to GitHub**.
3. Copy the ImageFrame command it shows and paste it in chat in-game, then place
   the map on a grid of item frames of the size shown.

Export also saves the sign under **My signs**. A name can belong to only one
saved sign; exporting the same sign again makes `name_v2`, `name_v3`…, so
ImageFrame never gets a name twice.

## How export works

The builder sends the PNG to `serve.py`, which commits it to this repo with your
`gh` login (`gh auth login`) — no token is typed or stored by the page. Each
upload is a new file, `signs/<name>-<hash>.png`, and the image URL is pinned to
the commit that added it, so it always serves exactly that image. The sign's
layout is saved next to it as `signs/<name>.json` (paste it into the builder's
JSON box to edit the sign again).

The repo is public because ImageFrame downloads images without logging in.

## Files

- `wayfinder.html` — the builder (also published as a claude.ai artifact, which
  can download PNGs but cannot export to GitHub)
- `serve.py` — local helper: serves the builder and handles exports
- `Start Wayfinder.bat` — starts the helper and opens the builder
- `signs/` — exported sign images and their layouts
