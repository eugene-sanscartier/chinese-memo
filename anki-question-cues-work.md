# Work Stream: anki question-side component cues

## File list

- `anki_memodevice.py`
- `assets/anki/css.css`
- `data/derived/components/components.json`
- `data/source/authored/gloss.json`
- `AGENTS.md`

## Goal

Make the standard Anki card question side use the final curated component list as the primary cue, while keeping the answer side unchanged.

## Current state

- The standard-note question side now loads its component cue from `data/derived/components/components.json` inside `anki_memodevice.py`.
- The answer side still uses the existing `entry["components"]` path from `data_memodevice.json` and was not modified.
- The front side keeps a component block even when the final component list is self-only.
- The front-side layout now uses a centered container with a left-aligned stacked component block and a low-emphasis footer gloss.
- The front-side component block now uses a fixed centered width with a mobile cap so its left edge stays aligned from card to card.
- The front-side component block is widened so component rows can still reflow when needed, but much less often than before.
- The front-side component glyph now prefers `LXGW WenKai GB Lite Light` before HanaMin fallback and is slightly larger than the surrounding gloss text so it does not read too thin.
- The front-side component row now styles the glyph and gloss separately: the glyph stays larger as the cue, while the gloss is slightly smaller and lower-contrast.

## Requested change

- Change the question-side component source to `data/derived/components/components.json`.
- Apply that source only on the standard-note question side.
- Keep the answer side on its current data/render path.
- Keep a visible component block even when the final component list is just `[char]`.
- Keep the front-side style close to the current card style.
- Show stacked component rows with left-aligned content in a centered block, medium emphasis, and no extra front-side headings.
- Move the character French gloss lower on the card as a weaker footer-style cue.

## Decisions

- Do not replace the global component source in `data_memodevice.py`.
- Do not touch the answer side.
- Use French component glosses on the question side.
- Preserve style consistency by still rendering a component block for self-only final decompositions.

## Evaluation criteria

- Standard-card question-side components come from `components.json`, not the current raw answer-side component data.
- Each front-side component renders with its French gloss when available.
- The answer side remains unchanged.
- The front-side layout stays visually close to the existing card, with only the cue hierarchy changed.

## Verification

- `~/.venv/venv/bin/python -m py_compile anki_memodevice.py` succeeds.
- Sample render check on `常` shows front-side components `尚`, `巾` from the final component map and still shows the answer-side decomposition block separately.
