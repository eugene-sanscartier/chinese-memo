# Work Stream: cdp render testing

## Files in scope

- `tools/test_cdp_render.py`
- `data/source/reference/ids_dictionary.json`
- `data/derived/entity_render/ids_dictionary_entity_render_map.json`
- `build/cdp_render_test.html`

## Goal

Create a test-only local HTML preview for IDS entity rendering without changing the Anki deck path.

## Confirmed decisions

- Keep this out of `anki_memodevice.py` and out of card rendering.
- Use a standalone HTML preview generated locally into `build/`.
- Generate a reusable JSON mapping file too.
- Cover every `CDP`/`A-CDP` entity that appears in `data/source/reference/ids_dictionary.json`.
- Map entities to Unicode PUA codepoints and render them with HanaMin instead of trying to replace them with ordinary Unicode characters.
- Use the published Big5/EUDC conversion formula referenced by `cjkvi-ids`.
- Also handle the small local `U-*` entity family by rendering the base Unicode codepoint directly.
- Best-effort extension: handle `A-U-*` and `o-UU+*` by their embedded Unicode codepoint, add a few locally defensible source-specific mappings, and leave unresolved entities explicit.

## Evaluation criteria

- Anki generation remains unchanged.
- Running the test script writes a preview HTML file under `build/`.
- Running the test script also writes a reusable JSON map under `data/derived/`.
- Every `CDP`/`A-CDP` entity from `ids_dictionary.json` is assigned a PUA codepoint.
- Every `U-*` entity from `ids_dictionary.json` is assigned its base Unicode codepoint.
- The preview shows entity, codepoint, mapping kind, status, and rendered glyph or raw unresolved entity text.

## Progress

- Identified that bundled HanaMin fonts already exist under `assets/anki/fonts/`.
- Confirmed `&CDP-...;` is not decoded by normal HTML entity handling.
- Confirmed the public `cjkvi-ids` path uses CDP entities plus a published Big5/EUDC-to-PUA conversion table rather than direct ordinary-Unicode replacement.
- Updated `tools/test_cdp_render.py` to generate a full `ids_dictionary` CDP/A-CDP → PUA map and a matching HTML preview.
- Extended the test mapping to cover the 8 local `U-*` entities by falling back to their base Unicode codepoints, e.g. `&U-i001+20541;` → `U+20541` (`𠕁`).
- Extended the preview to scan all IDS entities, including `A-U-*` and `o-UU+*`, and to surface unresolved source-specific entities instead of hiding them.
