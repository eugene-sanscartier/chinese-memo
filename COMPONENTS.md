# Character Decomposition — `data_components.py`

> **Maintenance rule:** after any change to `data_components.py` (new approach, removal, rename, behavioural change), update this file to reflect the current goal and output status before closing the task.

## Goal

Chinese characters that share structural components are easy to confuse during learning. The goal of this module is **character decomposition**: for each character, build a set of components using multiple approaches — structural, etymological, and cross-source — that together describe its composition in ways useful for learning and disambiguation.

A **component** is any structural, phonetic, or visual part of a character: a radical, a sub-character, a stroke group, or an etymological element. Different approaches capture different perspectives on the same character; each is useful in different contexts.

The output of each approach is filtered to the components that vary among the character's confusable neighbours, making the result specific to each character's confusion context rather than a generic structural listing.

---

## Output conventions

- **No slot labels**: component values must be bare characters (e.g. `木`, not `L=木` or `R=木`). Slot-labelled features are internal to `build_char_index` and must never appear in `data_components_*` output.
- **Systematic ordering** — each approach has a fixed ordering rule:
  - `direct`: IDS positional reading order (left → right, top → bottom as written in the IDS string)
  - `hanzi`: HanziDecomposer output order (preserve as returned)
  - `phonetic`: semantic component first (meaning-carrier), then phonetic
  - `all`: alphabetical (no structural order available)
  - `merged`: by vote count descending (most-confirmed component first)

## Data sources

| variable | file | contains |
|---|---|---|
| `ids_dict` | `ids_dictionary.json` | `ids` string, `components` (full recursive list), `decomposition` (depth-1 structured children) |
| `mma_dict` | `dictionary_makemeahanzi.txt` | etymology (`type`, `phonetic`, `semantic`, `hint`), `pinyin`, stroke count |
| `decomposer` | `HanziDecomposer()` | level-2 component decomposition (independent source, often disagrees with IDS) |
| `char_dict` | `dictionary_char.jsonl` | `strokeCount`, HSK level, corpus frequency rank, `gloss` |

## Current output — `data_similar/data_components_*.json`

One file per decomposition approach. Each maps every character to a list of bare component characters — the discriminating subset of its full decomposition. Empty list means no discriminating component could be found (character is a structural subset of a neighbour).

```json
{
  "字": ["comp_a", "comp_b"],
  "字": ["comp_a"],
  "字": []
}
```

## Implemented decomposition approaches

- **Direct** — the immediate structural parts of a character: depth-1 IDS children in positional reading order.
- **All** — the full recursive IDS ancestry (superset of direct). Captures components that only appear deeper in the structure.
- **Hanzi** — decomposition from HanziDecomposer, an independent source. Disagreements with IDS surface components the IDS tree misses.
- **Phonetic** — for 形声字: the semantic (meaning-carrier) and phonetic components from MMA etymology, semantic first.
- **Merged** — components confirmed discriminating by ≥2 of the above, ordered by vote count. The most cross-validated decomposition.

---

## `build_char_index` — how similar neighbours are found

Computes IDS positional leaf features for every character (`L=木`, `R=黄`, `BL=辶`). For each character, finds all others with Jaccard ≥ 0.25 — these are the confusable neighbours used by the discriminating filter.

Key design decisions:
- **Radical normalization** (`_RADICAL_NORM`): variant radicals (⻖/⻏/⺼/⻌) mapped to canonical forms before feature extraction.
- **Salience reranking**: features sorted by `salience(slot) × rarity` — ⿰ right component (60% visual area) leads.
- **Stroke count rescue**: subset chars with no IDS discriminator but unique stroke count get `identity=stroke_count`.
- **MMA phonetic families**: covers 1403 chars (vs 984 from IDS inference alone).

---

## Ideas for future decomposition approaches

Each idea is framed as a new source of discriminating components.

- **Mnemonic text mining** — parse mnemonic texts from `data_memodevice.json` and extract the components they name. Components a human mnemonist chose to emphasize are a pedagogically-validated decomposition signal independent of IDS structure.

- **Semantic indicator as primary component** — for pictophonetic chars, lead the decomposition with the semantic component (meaning-carrier, from MMA etymology) rather than the phonetic. Within a phonetic family (all containing 青), the semantic indicator (氵/日/忄/讠/目) is always the discriminating one.

- **Position-invariant components** — include a component even when it appears in a different structural slot than usual: 削=⿰肖刂 and 梢=⿰木肖 both contain 肖. Adding position-agnostic component membership to the decomposition set captures cross-position shared ancestry.

- **Depth-2 ancestry components** — include components reachable at depth-2 through different intermediaries: 骑(马+奇) and 荷(艹+何) both reach 可 via different depth-1 children. Surfaces hidden structural kinship invisible to direct decomposition.

- **Visual-only components** — for characters like 己/已/巳 where IDS decomposition is identical, pixel-level rendering can identify the visual feature that varies (open vs. closed stroke end). Requires PIL + font file, but the concept is sound and uniquely covers single-stroke confusables.

- **Contrastive decomposition** — instead of a flat component list, express each component as an explicit contrast: `{vs: 睛, ours: 日, theirs: 目}`. Makes the decomposition directly actionable for card display and ties each component to a specific confusable.

- **Depth-ranked components** — rank components by how deep in the IDS tree they appear: depth-1 (direct children) > depth-2 > deeper. Shallower components are visually more salient and should lead the decomposition set.
