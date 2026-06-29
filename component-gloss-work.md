# Work Stream: component gloss coverage

## Files in scope

- `data/derived/components/components.json`
- `data/source/authored/gloss.json`
- `data/source/reference/dictionary_char.jsonl`
- `data/cache/component_gloss_translation/`
- `tools/gloss_translation/component_gloss.py`
- `AGENTS.md`

## Goal

Build the missing component-gloss queue from the final component set, prepare any needed cache-side translations, and merge the finished component glosses into authored gloss data.

## Confirmed decisions

- Use the final unique components from `data/derived/components/components.json` as the component set.
- Keep translation work files under `data/cache/component_gloss_translation/`.
- For components missing from `gloss.json`, fill `gloss_en` from `dictionary_char.jsonl` when available.
- Reuse the existing gloss-translation tooling style rather than creating a separate larger pipeline.
- Do not write a merged component gloss file under `data/source/authored/`; only cache-side missing lists are needed.
- Keep all missing component glosses in a single cache file rather than split `missing_fr` / `missing_en` files.
- Do not use a dedicated `workdir/`; keep the translation input and translated output directly in `data/cache/component_gloss_translation/`.
- Keep the queue fields minimal; do not add bookkeeping fields such as `needs_gloss_en` or `example_count`.

## Evaluation criteria

- Existing authored `gloss_en` and `gloss_fr` values in `gloss.json` remain untouched.
- All missing component glosses are represented once in a single cache file.
- Components with English gloss but missing French gloss remain identifiable for translation.
- Components with no usable English gloss remain identifiable for manual authoring.
- Translation can be run directly from the single cache file without a separate workdir.

## Current state

- Final component inventory currently has `1067` unique components after remapping `龷 -> 艹`.
- All `1067` components now have both `gloss_en` and `gloss_fr` in `data/source/authored/gloss.json`.
- `data/cache/component_gloss_translation/missing_gloss.json` is now empty after merging the component glosses into authored data.
- `data/cache/component_gloss_translation/missing_gloss_translated.json` is also now empty after the merge.

## Pending output groups

- Combined missing-gloss queue in `data/cache/component_gloss_translation/missing_gloss.json`
- Optional translation output in `data/cache/component_gloss_translation/missing_gloss_translated.json`

## Completed

- Added `tools/gloss_translation/component_gloss.py` with two commands:
  - `build`
  - `google`
- Generated `data/cache/component_gloss_translation/missing_gloss.json` with the current missing component gloss queue.
- Generated `data/cache/component_gloss_translation/missing_gloss_translated.json` with polished learner-facing French proposals for all `34` entries, stripped down to `gloss_en` and `gloss_fr`.
- Wrote `data/cache/component_gloss_translation/summary.json` with the current counts.
- Removed the previously generated authored aggregate, the split missing files, and the old `workdir/` cache layout after scope correction.
- Added a `hanzipy` fallback in `tools/gloss_translation/component_gloss.py`:
  - radical meanings from `hanzipy/data/radical_with_meanings.json`
  - character definitions from `HanziDictionary.definition_lookup`
- Verified new package-backed glosses:
  - `⺳ -> net`
  - `龵 -> hand`
  - `迶 -> walking`
- Added explicit package-backed fallback glosses for dictionary rows that expose a meaning only through `shuowen`, variants, or related package evidence:
  - `倠 -> bird`
  - `厈 -> cliff`
  - `厽 -> star`
  - `圡 -> earth`
  - `圤 -> clod`
  - `圼 -> mud`
  - `巸 -> broad`
  - `汒 -> vast`
  - `犾 -> dogs biting`
  - `疌 -> rapid`
  - `豙 -> enraged boar`
  - `遀 -> follow`
  - `龴 -> private, selfish`
- Added online-verified overrides for glosses that needed either confirmation or better wording:
  - `㳟 -> respectful`
  - `弚 -> younger brother`
  - `旲 -> sunlight`
  - `茾 -> herb`
  - `洰 -> ditch`
  - `迶 -> walking`
  - `⺳ -> net`
  - `龵 -> hand`
- Remapped `龷 -> 艹` in `data_components.py`, rebuilt `data/derived/components/components.json`, and removed `龷` from the missing-gloss queue entirely.
- Current missing-English count after the online-verified pass is now `0`.
- Merged the `34` translated component glosses from `data/cache/component_gloss_translation/missing_gloss_translated.json` into `data/source/authored/gloss.json`.
- Rebuilt the component-gloss cache after the merge, bringing `missing_gloss.json`, `missing_gloss_translated.json`, and `summary.json` to an empty-queue state.

## Translation workflow

- Build or refresh the missing-component-gloss queues:
  - `~/.venv/venv/bin/python tools/gloss_translation/component_gloss.py build`
- Translate the subset with non-empty `gloss_en` using the existing Google translation helper:
  - `~/.venv/venv/bin/python tools/gloss_translation/component_gloss.py google`

## Current pending sets

- Missing component glosses with `gloss_en` already present:
  - none
- Missing component glosses that still need `gloss_en`:
  - none
- Missing component glosses that still need `gloss_fr` merged into authored data:
  - none
