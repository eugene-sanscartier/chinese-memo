# Work Stream: component gloss coverage

## Files in scope

- `data/derived/components/components.json`
- `data/source/authored/gloss_translated.json`
- `data/source/reference/dictionary_char.jsonl`
- `data/cache/component_gloss_translation/`
- `tools/gloss_translation/component_gloss.py`
- `AGENTS.md`

## Goal

Build only the missing component-gloss queue from the final component set and prepare the remaining missing French translations in cache.

## Confirmed decisions

- Use the final unique components from `data/derived/components/components.json` as the component set.
- Keep translation work files under `data/cache/component_gloss_translation/`.
- For components missing from `gloss_translated.json`, fill `gloss_en` from `dictionary_char.jsonl` when available.
- Reuse the existing gloss-translation tooling style rather than creating a separate larger pipeline.
- Do not write a merged component gloss file under `data/source/authored/`; only cache-side missing lists are needed.
- Keep all missing component glosses in a single cache file rather than split `missing_fr` / `missing_en` files.
- Do not use a dedicated `workdir/`; keep the translation input and translated output directly in `data/cache/component_gloss_translation/`.
- Keep the queue fields minimal; do not add bookkeeping fields such as `needs_gloss_en` or `example_count`.

## Evaluation criteria

- Existing authored `gloss_en` and `gloss_fr` values in `gloss_translated.json` remain untouched.
- All missing component glosses are represented once in a single cache file.
- Components with English gloss but missing French gloss remain identifiable for translation.
- Components with no usable English gloss remain identifiable for manual authoring.
- Translation can be run directly from the single cache file without a separate workdir.

## Current state

- Final component inventory currently has `1068` unique components.
- `1033` components already have both `gloss_en` and `gloss_fr` in `data/source/authored/gloss_translated.json`.
- `35` components are missing from `gloss_translated.json`.
- Of those `35`, `13` already have a usable English gloss in `data/source/reference/dictionary_char.jsonl` and need only French translation.
- The remaining `22` have no usable `dictionary_char` gloss and need an English gloss first.

## Pending output groups

- Combined missing-gloss queue in `data/cache/component_gloss_translation/missing_gloss.json`
- Optional translation output in `data/cache/component_gloss_translation/missing_gloss_translated.json`

## Completed

- Added `tools/gloss_translation/component_gloss.py` with two commands:
  - `build`
  - `google`
- Generated `data/cache/component_gloss_translation/missing_gloss.json` with all `35` missing component glosses.
- Wrote `data/cache/component_gloss_translation/summary.json` with the current counts.
- Removed the previously generated authored aggregate, the split missing files, and the old `workdir/` cache layout after scope correction.

## Translation workflow

- Build or refresh the missing-component-gloss queues:
  - `~/.venv/venv/bin/python tools/gloss_translation/component_gloss.py build`
- Translate the subset with non-empty `gloss_en` using the existing Google translation helper:
  - `~/.venv/venv/bin/python tools/gloss_translation/component_gloss.py google`

## Current pending sets

- Missing component glosses with `gloss_en` already present:
  - `倝`, `冄`, `冊`, `刅`, `叀`, `尌`, `昜`, `柰`, `矦`, `肰`, `舁`, `茻`, `龰`
- Missing component glosses that still need `gloss_en`:
  - `⺳`, `㳟`, `倠`, `厈`, `厽`, `圡`, `圤`, `圼`, `巸`, `弚`, `旲`, `汒`, `洰`, `犾`, `疌`, `茾`, `豙`, `迶`, `遀`, `龴`, `龵`, `龷`
