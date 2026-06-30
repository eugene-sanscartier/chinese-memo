# Work Stream: component gloss coverage and gloss audit

## Files in scope

- `data/derived/components/components.json`
- `data/source/authored/gloss.json`
- `data/source/reference/dictionary_char.jsonl`
- `data/source/reference/ids_dictionary.json`
- `data/cache/component_gloss_translation/`
- `data/cache/gloss_translation/suspicious_gloss_audit/`
- `tools/gloss_translation/component_gloss.py`
- `tools/gloss_translation/suspicious_glosses.py`
- `qwen_api.py`
- `AGENTS.md`

## Goal

Build the missing component-gloss queue from the final component set, prepare any needed cache-side translations, merge the finished component glosses into authored gloss data, and now audit existing authored glosses for clear English/French sense mismatches.

## Confirmed decisions

- Use the final unique components from `data/derived/components/components.json` as the component set.
- Keep translation work files under `data/cache/component_gloss_translation/`.
- For components missing from `gloss.json`, fill `gloss_en` from `dictionary_char.jsonl` when available.
- Reuse the existing gloss-translation tooling style rather than creating a separate larger pipeline.
- Do not write a merged component gloss file under `data/source/authored/`; only cache-side missing lists are needed.
- Keep all missing component glosses in a single cache file rather than split `missing_fr` / `missing_en` files.
- Do not use a dedicated `workdir/`; keep the translation input and translated output directly in `data/cache/component_gloss_translation/`.
- Keep the queue fields minimal; do not add bookkeeping fields such as `needs_gloss_en` or `example_count`.
- For authored gloss cleanup, fix incorrect or misleading `gloss_en` first, then align `gloss_fr` to the same sense.
- Keep authored-gloss edits narrow: patch only entries that are clearly wrong or crossed, not all stylistic duplicates.
- For the current full-gloss audit, use Qwen to flag suspicious rows and propose replacements, but keep `gloss.json` untouched until the flagged set is reviewed.
- Cover all of `data/source/authored/gloss.json`, not just the component subset.
- Keep the Qwen audit outputs under `data/cache/gloss_translation/suspicious_gloss_audit/`.
- Use `qwen-plus` as the default suspicious-gloss audit model, with thinking enabled.
- The suspicious-gloss JSON output should contain flagged rows only as a direct character-to-review mapping, not a parallel list of okay rows and not a top-level `suspicious` wrapper.
- Each flagged row should carry a primary audit category such as `wrong_sense`, `en_fr_mismatch`, `overpacked`, `meta_variant_encyclopedic`, `awkward_french`, `non_core_meaning`, or `other`.
- The prompt should require the exact empty result `{}` when a batch has no findings.
- The prompt should force a single primary category using an explicit precedence order.
- The prompt should keep the replacement `gloss_en` unchanged when only the French needs correction.
- The prompt should describe the target as short learner-facing character-study glosses, not refer vaguely to a `deck`.
- The prompt should require short, one-main-sense, non-encyclopedic replacement glosses.
- The prompt should explicitly prefer modern common learner-facing meanings over archaic, literary, rare, or highly technical senses.
- The prompt should explicitly avoid flagging rows just because a different gloss would be merely better or more elegant.
- The prompt should be conservative about switching polyphonic characters to another reading.
- For smoke tests, the suspicious-gloss audit should support a reproducible random sample of characters instead of forcing the first rows in file order.
- The suspicious-gloss cache rows should store current values as `current_gloss_en/current_gloss_fr` and the model replacement as `gloss_en/gloss_fr`.
- When `--sample-size` is used without `--sample-seed`, the script should generate a random seed, print it, and record it in the cached selection.
- `qwen_api.py` should make `thinking=True` safe for JSON workflows by retrying once without thinking if the stream ends with no final JSON answer.
- The audit should support small in-process batch parallelism without shards by keeping Qwen requests concurrent but leaving cache/state writes in the main thread.
- Terminal output should show batch-level progress only; suppress token-by-token reasoning/response streaming while the audit runs.
- Progress should use `tqdm` over characters, while cumulative input/output/total token counts stay visible during the run.

## Evaluation criteria

- Existing authored `gloss_en` and `gloss_fr` values in `gloss.json` remain untouched.
- All missing component glosses are represented once in a single cache file.
- Components with English gloss but missing French gloss remain identifiable for translation.
- Components with no usable English gloss remain identifiable for manual authoring.
- Translation can be run directly from the single cache file without a separate workdir.
- For authored-gloss audit fixes, each patched row has English and French pointing at the same sense and is supported by external verification when the current gloss is suspicious and local dictionary-derived data is not an independent oracle.
- The Qwen pass should categorize all deck-relevant gloss problems, not just strict semantic errors.
- The cache-side audit report should be resumable and should not modify authored gloss data.
- The audit summary should expose category counts so the flagged set can be reviewed by failure type.
- Sampled test runs should keep their own cached state via recorded sample selection settings.
- `non_core_meaning` should be used sparingly and not simply because a polyphonic character has another common reading.
- Polyphonic-character judgments should favor conservative modern learner-facing glosses rather than reading swaps based on marginal alternatives.
- Parallel mode should not introduce shared-write races; only the main thread should merge results and write cache artifacts.
- Token usage should be collected per completed batch and reported cumulatively during the audit.

## Current state

- Final component inventory currently has `1067` unique components after remapping `龷 -> 艹`.
- All `1067` components now have both `gloss_en` and `gloss_fr` in `data/source/authored/gloss.json`.
- `data/cache/component_gloss_translation/missing_gloss.json` is now empty after merging the component glosses into authored data.
- `data/cache/component_gloss_translation/missing_gloss_translated.json` is also now empty after the merge.
- Current gloss-audit focus is the small set of authored rows with obvious English/French crossings or wrong modern senses, starting with `凌 / 沃 / 夃 / 讽 / 诧 / 嚼 / 医 / 喀 / 礻 / 氢`.
- The second audit pass now extends that set to the remaining high-confidence sense/granularity mismatches in `慧 / 宏 / 葛 / 棋 / 迄 / 喧 / 俭 / 念`.
- The consistency-normalization pass now also targets repeated English glosses that still mapped to multiple French glosses, preferring sense-splitting on the English side over forcing unrelated French rows into one label.
- The next audit pass is no longer based on comparing `gloss.json` back to `dictionary_char.jsonl`, because `gloss.json` was derived from that source; instead it uses `qwen_api.py` to flag suspicious rows across the full file and write a cache-side review report.
- The suspicious-gloss audit now defaults to `qwen-plus` and calls Qwen with thinking enabled.
- The suspicious-gloss audit now returns only flagged rows and classifies them by failure type instead of echoing okay rows.

## Pending output groups

- Combined missing-gloss queue in `data/cache/component_gloss_translation/missing_gloss.json`
- Optional translation output in `data/cache/component_gloss_translation/missing_gloss_translated.json`
- Suspicious-gloss audit cache in `data/cache/gloss_translation/suspicious_gloss_audit/`

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
- Audited the first batch of obviously crossed authored gloss rows and confirmed that several are true semantic mismatches rather than harmless wording differences.
- Confirmed with `dictionary_char.jsonl` and spot online checks that this batch should be corrected by fixing `gloss_en` first and then re-aligning `gloss_fr`.
- Applied a second narrow authored-gloss cleanup pass:
  - `慧`: `bright` -> `intelligent`
  - `宏`: `wide / grand` -> `vast / vaste`
  - `葛`: `edible bean / kudzu, légumineuse` -> `kudzu / kudzu`
  - `棋`: kept `chess`, tightened French `jeu` -> `échecs`
  - `迄`: `extend` -> `until`
  - `喧`: `lively` -> `noisy`
  - `俭`: `temperate` -> `frugal`
  - `念`: `think of, ready / penser à, lire` -> `think of / penser à`
- Applied a broader consistency-normalization pass across the remaining repeated-English groups.
  - Main rule: when one English gloss covered multiple senses, split the English gloss by row instead of flattening distinct senses into one French label.
  - Representative examples:
    - `副 assist -> deputy`
    - `晋 advance -> progress`
    - `妃 wife -> consort`
    - `叫 cry -> shout`
    - `脂 fat -> grease`
    - `纪 record -> chronicle`
    - `源 spring -> source`
    - `副 / 域 / 籍 / 迁 / 署 / 署 / 络 / 讯` tightened to match their existing French sense
    - radical-style rows such as `彳 / 廴 / 辶` were made explicit as `walk radical / radical de marche`
    - remaining broad lexical rows were split into more specific learner-facing glosses like `redeem`, `character`, `flower classifier`, `string together`, `rescue`, `right side`, `short in height`, `seize by force`, `large ship`, `walk radical`, `climb`, and `consort`
- Current audit metric after the normalization pass:
  - repeated English glosses with multiple French mappings: `0`
- Added `tools/gloss_translation/suspicious_glosses.py` to run a resumable Qwen audit over all of `gloss.json` and write:
  - `audit_state.json`
  - `suspicious_glosses.json`
  - `summary.json`
- Tightened the suspicious-gloss `system_prompt` to:
  - require `{}` for clean batches
  - choose one primary category by precedence
  - preserve English replacements for French-only issues
  - target short learner-facing character-study glosses
  - require concise, one-main-sense, non-encyclopedic replacements
- Strengthened the prompt further to:
  - prefer modern common learner-facing senses
  - avoid flagging merely-better alternatives
  - be conservative about switching polyphonic characters to another reading
- Added a runtime fallback in `qwen_api.py`: if `thinking=True` yields no final JSON, retry the same request once with thinking disabled so callers do not crash.
- Removed the top-level `suspicious` wrapper from the Qwen output contract; the model now returns a direct mapping of flagged characters.
- Added random-sample test support to `tools/gloss_translation/suspicious_glosses.py`:
  - `--sample-size`
  - `--sample-seed`
- Made `--sample-seed` optional for sampled test runs; the script now generates and records a random seed when none is provided.
- Adjusted the suspicious-gloss artifact field names after the sample test:
  - keep source values as `current_gloss_en/current_gloss_fr`
  - store the replacement from Qwen as `gloss_en/gloss_fr`
- Tightened the prompt again after the sample test to reduce false positives from `non_core_meaning` and polyphonic characters.
- Added `--max-parallel` to `tools/gloss_translation/suspicious_glosses.py` and switched the audit loop to small in-process batch parallelism with main-thread-only cache writes.
- Added `print_stream=False` support in `qwen_api.py` so Qwen reasoning/output can be suppressed while keeping batch-level progress visible.
- Added `tqdm` character-level progress plus cumulative prompt/completion/total token reporting for the suspicious-gloss audit.

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
