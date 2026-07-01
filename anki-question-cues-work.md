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
- The front-side component rows are now itemized with the same `━` cue used on the answer side, and the centered list container is narrower so the block sits less far left.
- The front-side component block is now widened again so gloss text can run farther before reflow, the gloss text itself is slightly smaller, and the whole cue block is nudged a bit to the right.
- The front-side character gloss is now pinned in a fixed lower footer position with reserved space, so it stays at the same height even when the number of components changes.
- The large study character on the question side and the answer side now uses one shared header wrapper with a smaller top offset, so they sit higher and line up from the same layout anchor.
- The standard-note back template now renders the answer content directly instead of prepending `{{FrontSide}}`, so the answer side no longer inherits the front-side scroll region.
- The question side and answer side now use the same outer top padding instead of relying on an inner header margin, so their large character aligns from the same side wrapper even though one side is flex-based and the other is normal flow.
- The answer-side character HTML is now wrapped in an explicit `.answer-character-block` container instead of relying on malformed trailing markup, so the browser no longer has to auto-repair the back-side DOM around the character block.
- The answer-side sound marker now comes after the visible character header instead of before it, so Anki's audio rendering cannot push the back-side character downward relative to the front.

## Requested change

- Change the question-side component source to `data/derived/components/components.json`.
- Apply that source only on the standard-note question side.
- Keep the answer side on its current data/render path.
- Keep a visible component block even when the final component list is just `[char]`.
- Keep the front-side style close to the current card style.
- Show stacked component rows with left-aligned content in a centered block, medium emphasis, and no extra front-side headings.
- Pull the front-side component list slightly inward from the left edge while keeping the same basic centered layout.
- Itemize the front-side component rows more like the answer side.
- Let the component gloss text run farther before wrapping, reduce its size slightly, and move the cue block a bit to the right.
- Move the character French gloss lower on the card as a weaker footer-style cue.
- Keep the front-side character gloss at a stable vertical position even when the component block changes height.
- Align the large character on the question side and answer side to the same vertical position.
- Reduce the top spacing further while keeping the question-side and answer-side character position matched.
- For the standard note type, remove `{{FrontSide}}` from the back template and render only the answer side.

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
