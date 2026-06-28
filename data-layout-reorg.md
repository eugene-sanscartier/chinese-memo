# Work Stream: data layout reorganization

## Goal

Reorganize the mnemonic repo data into explicit source, derived, cache, assets, and build areas, while updating the code to use the new paths.

## Confirmed decisions

- Use `data/source`, not `raw/`.
- Use the stronger umbrella layout: `data/source`, `data/derived`, `data/cache`, plus top-level `assets` and `build`.
- Put `memo_anki.apkg` directly in `build/`.
- Replace symlinked reference inputs with real copied files in the repo.
- Keep bundled Anki font source files under `assets/anki/fonts/`.
- Keep CSS `@font-face` URLs as basenames because packaged Anki media names are flattened.
- Keep the accepted definition-selection result as `data/source/authored/definitions_selected.json`, separate from cache experiments.
- Treat `loci_name/` as generated cache output only, under `data/cache/loci_name/`.

## Planned structure

- `data/source/authored/`: authored JSON/text inputs.
- `data/source/reference/`: copied-in dictionary/reference files, including the flattened HSK JSON files.
- `data/derived/`: generated tables, JSON outputs, and named-loci images.
- `data/cache/`: resumable LLM caches and selected derived intermediate files used as inputs.
- `assets/anki/`: CSS, templates, fonts.
- `assets/anki/audio/`: bundled pinyin audio used by the deck.
- `assets/loci/`: loci images.
- `build/`: final packaged Anki output.

## Files in scope

- `anki_memodevice.py`
- `data_memodevice.py`
- `data_words.py`
- `tools/name_loci.py`
- `data_components.py`
- `data/source/authored/definitions_selected.json`
- `data/cache/loci_name/*`
- `data/cache/definition_selection/*`
- `tools/definition_selection/*.py`
- `tools/gloss_translation/*.py`
- `assets/anki/*`
- `assets/anki/audio/*`
- `COMPONENTS.md`
- `.gitignore`

## Progress

- Mapped the current inputs and outputs used by the main mnemonic pipeline scripts.
- Confirmed the current symlinked reference files: `dictionary_char.jsonl`, `ids_dictionary.json`, `dictionary_makemeahanzi.txt`.
- Confirmed the external HSK source file exists in the sibling repo.
- Moved authored inputs into `data/source/authored/`.
- Copied the symlinked reference inputs and HSK file into `data/source/reference/`.
- Folded the unused root symlink `dictionary_words.jsonl` into `data/source/reference/` so the reference tree is self-contained.
- Moved generated outputs into `data/derived/`, caches into `data/cache/`, Anki assets into `assets/`, and `memo_anki.apkg` into `build/`.
- Vendored the pinyin audio set into `assets/anki/audio/` and updated the deck builder to package audio from the repo instead of a sibling directory.
- Moved the bundled font source files out of repo root into `assets/anki/fonts/` without changing deck media behavior.
- Copied the accepted definition-selection result into `data/source/authored/definitions_selected.json` and moved definition-selection experiments under `data/cache/definition_selection/`.
- Moved definition-selection tooling into `tools/definition_selection/` and updated it to read and write in the reorganized tree.
- Moved `loci_name/` fully into `data/cache/loci_name/` and kept it out of the active authored inputs.
- Moved gloss-translation scripts into `tools/gloss_translation/` and kept their working files under `data/cache/gloss_translation/`.
- Moved leftover definition-related translation artifacts into `data/cache/definition_selection/translation_definitions/`.
- Normalized the moved gloss-translation scripts to use the cache/workdir paths that now exist in the reorganized tree, keeping the root review flow on `gloss_translation-qwen-max.json` and the `final-gloss-workdir` review flow on `gloss_translation.json`.
- Flattened the HSK reference path and now use `data/source/reference/hsk_vocabulary.json` as the canonical HSK input.
