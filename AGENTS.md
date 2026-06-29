## Project Notes

- Project purpose: generate Chinese mnemonic study artifacts, including an Anki deck via `anki_memodevice.py`.
- Python environment: use `~/.venv/venv/bin/python`.
- Data layout: canonical inputs live under `data/source`, generated outputs under `data/derived`, caches under `data/cache`, packaged assets under `assets`, and final deck artifacts under `build`.
- Audio packaging: bundled pinyin audio for the deck lives under `assets/anki/audio/`.
- Loci names: `loci_name/` is not part of the active build input; `tools/name_loci.py` should write generated named-image outputs only under `data/cache/loci_name/`.
- Gloss translation: `data/source/authored/gloss_translated.json` is the stable deck input; gloss-translation tooling lives under `tools/gloss_translation/` and should write only under `data/cache/gloss_translation/`.
- Definition selection: `data/source/authored/definitions_selected.json` is the stable deck input; definition-selection tooling lives under `tools/definition_selection/` and should write only under `data/cache/definition_selection/`.
- Components: `data/derived/components/components.json` is the current card-targeted component approach, built from `family` plus normalized depth-1 direct components, with final ordering taken from structural appearance rather than forcing family components first. The final generator keeps direct chunks instead of recursively unwrapping them, prevents mixed-granularity and partial-loss cases, and normalizes learner-facing forms such as `⺌->小`, `⺮->竹`, `𧾷->足`, `𤣩->王`, `礻->示`, and `⻏/⻖->阝`. Legacy non-final approach outputs live under `data/derived/components/approaches/`, and the legacy multi-approach generator lives under `tools/components/`.
- Media packaging: `genanki.Package.media_files` preserves source paths only during collection, but the final deck media names are flattened to `os.path.basename(...)`.
- Font implication: bundled font source files may live in a repo subdirectory, but CSS `@font-face` URLs for Anki media must still reference the basename only.
- Question handling: when user input is needed, use `request_user_input` instead of a plain text question when that tool is available.
- Scope preference: keep deck-generation changes narrow and avoid unrelated cleanup.
