# AI Berkshire Report Library

Mobile-friendly, searchable research reports published at
https://sudoli.github.io/ai-berkshire-reports/.

The reports are a snapshot of the local AI Berkshire research directory.
Original framework and upstream research: [xbtlin/ai-berkshire](https://github.com/xbtlin/ai-berkshire).
The upstream MIT license and attribution are preserved in `LICENSE`.
Research is for learning only, not investment advice; quoted prices are historical snapshots.

## Build

```powershell
python -m pip install -r requirements.txt
python tools\build_site.py --source ..\ai-berkshire --output docs
python -m unittest discover -s tests
```

The output directory must be empty. To rebuild without overwriting a published
snapshot, build into a new empty directory first, review it, and replace `docs`
only after checking the result.

The builder respects the source repository's Git ignore rules, including for
already-tracked files. `reports/portfolio-latest.md` is always excluded.
Only reports and their supporting document assets are published; source code,
runtime files, credentials and the rest of the local repository are not copied.
Do not remove these exclusions to make private reports public.

Existing HTML reports keep their layouts. Markdown reports receive a responsive
reading layout, scrollable tables, and a table of contents. Internal report
links are rewritten to their published pages. The index can be searched by
report title, company directory or filename.

GitHub Pages serves the `docs` directory on the `main` branch. Future local
reports are not published automatically; rebuild and push a reviewed snapshot.
