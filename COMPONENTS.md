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
  - `all`: BFS depth-order (shallowest component first, tiebreak by tree position); shallower = more visually prominent
  - `hanzi`: HanziDecomposer output order (preserve as returned)
  - `radical`: single entry; no ordering
  - `memodevice`: meaning-type first, then sound, then iconic/other
  - `meaning`: memodevice source order (preserves curation order within meaning-type)
  - `merged`: by vote count descending (most-confirmed component first); empty list when no component is confirmed by ≥2 approaches
- **Entity references**: components like `&CDP-89EB;` are valid and must be kept — they name CJK characters that lack a Unicode code point. Do not filter them out.
- **After adding any new approach**: compare its output against existing approaches and document what it contributes distinctly. Statistics alone are insufficient — show concrete divergence examples and explain *why* the approaches disagree (granularity difference? different structural tradition? different emphasis?). Questions to answer: what does this approach see that others miss? What characters does it uniquely cover? Where does it disagree most, and what does that tell us about the character?

## Data sources

| variable | file | contains |
|---|---|---|
| `ids_dict` | `ids_dictionary.json` | `ids` string, `components` (full recursive list), `decomposition` (depth-1 structured children) |
| `mma_dict` | `dictionary_makemeahanzi.txt` | `radical` (KangXi), etymology (`type`, `phonetic`, `semantic`, `hint`), `pinyin`, stroke count |
| `decomposer` | `HanziDecomposer()` | level-2 component decomposition (independent source, often disagrees with IDS) |
| `memo_dict` | `data_memodevice.json` | `components` (typed: `meaning`/`sound`/`iconic`/`simplified`/`remnant`), `hint`, pinyin, gloss |
| `char_dict` | `dictionary_char.jsonl` | `strokeCount`, HSK level, corpus frequency rank, `gloss` |

## Current output — `data_components/data_components_*.json`

One file per decomposition approach. Each maps every character to a list of bare component characters — the discriminating subset of its full decomposition. Empty list means no discriminating component could be found for this approach (e.g. character's radical is shared with all its confusables).

```json
{
  "字": ["comp_a", "comp_b"],
  "字": ["comp_a"],
  "字": []
}
```

Active files: `direct`, `all`, `hanzi`, `radical`, `memodevice`, `meaning`, `merged`.

## Implemented decomposition approaches

- **Direct** — the immediate structural parts of a character: depth-1 IDS children in positional reading order.
- **All** — the full recursive IDS ancestry (superset of direct), ordered by BFS depth so shallower (more visually prominent) components come first.
- **Hanzi** — decomposition from HanziDecomposer, an independent source. Disagreements with IDS surface components the IDS tree misses; decomposes at finer granularity than IDS (near-primitive elements).
- **Radical** — single KangXi radical from MMA (`mma_dict['radical']`). Always exactly one entry; the traditional dictionary-lookup component. Discriminating within phonetic families (each sibling has a different radical) but often shared within structural confusion sets.
- **Memodevice** — human-curated typed decomposition from `data_memodevice.json`. Meaning-type components first, then sound, then iconic/other. Genuinely disagrees with IDS: e.g. 明=囧+月 (memodevice) vs 日+月 (IDS). Coverage: 100% of characters have entries.
- **Meaning** — meaning-type components only from memodevice (semantic core). Strips phonetic and iconic parts; gives the component that carries the character's meaning. Coverage: ~77% of characters have at least one meaning component.
- **Merged** — components confirmed discriminating by ≥2 of the five structural sources (direct, all, hanzi, radical, memodevice), ordered by vote count. Empty when no component reaches the ≥2 threshold.
- **Family** — components shared by ≥50% of the character's confusables, ordered by share fraction descending. Intentionally NOT filtered by `_discriminating` — shows what BINDS the confusion group rather than what differs. Complementary to `direct`: together they tell the full story: "belongs to [family] group, distinguished by [direct]".
- **Consensus** — strict intersection of `direct_map ∩ memodevice_map`, then `_discriminating` applied. Only components that both IDS structure and human curation independently name at the named sub-character level. When smaller than both parents (e.g. 明=`['月']` vs direct's `['日','月']` and memo's `['囧','月']`), it identifies the single most agreed-upon component.
- **Hint** — CJK characters extracted from the free-text `hint` field in `data_memodevice.json`, in text-appearance order. Unlike all other approaches, this is **etymological**: the hint text systematically describes traditional forms and historical components (归: hint=`['歸','止','帚']` — broom+foot=return; 准: `['準','氵','隼']` — water+falcon). Answers "where did this character come from?" not "how is it structured today?".

### Approach comparison

Coverage (non-empty / 2998 characters):

| approach | non-empty | uniquely covers |
|---|---|---|
| memodevice | 2830 (94%) | 1 |
| merged | 2758 (92%) | 0 |
| hanzi | 2732 (91%) | 0 |
| family | 2672 (89%) | 1 |
| direct | 2675 (89%) | 0 |
| hint | 2639 (88%) | **38** |
| all | 2646 (88%) | 1 |
| consensus | 2438 (81%) | 0 |
| meaning | 1881 (63%) | 0 |
| radical | 1813 (60%) | 3 |

`hint` uniquely covers 38 characters no other approach reaches (simple chars like 八, 九, 十, 己 that have rich etymological hints but simple modern structure).

Pairwise Jaccard (average over chars where at least one approach is non-empty):

| pair | J | | pair | J |
|---|---|---|---|---|
| consensus vs memodevice | **0.794** | | meaning vs radical | 0.493 |
| consensus vs direct | 0.764 | | meaning vs family | 0.464 |
| direct vs memodevice | 0.694 | | radical vs family | 0.433 |
| direct vs consensus | 0.764 | | consensus vs hint | 0.538 |
| hint vs memodevice | 0.632 | | all vs memodevice | 0.473 |
| direct vs all | 0.633 | | all vs hanzi | 0.450 |
| direct vs hint | 0.469 | | family vs direct | 0.227 |
| direct vs hanzi | 0.314 | | family vs memodevice | 0.263 |
| hanzi vs family | **0.168** | | family vs all | **0.171** |

**Three structural dimensions** — approaches cluster into three distinct signals:

1. *Named structural level* (`direct`, `memodevice`, `consensus`): intermediate sub-characters with meaning (将, 壹, 阝). High mutual Jaccard (0.633–0.794). These are the components a human uses in a mnemonic.
2. *Primitive level* (`hanzi`, `all`-deep): near-stroke elements (丬, 亠, 冖). Low Jaccard with named-level sources (hanzi vs family = 0.168, all vs family = 0.171).
3. *Relational level* (`family`, `radical`, `meaning`): express a character's ROLE in its confusion group, not its internal structure. `family` = group-binding (J=0.227 with direct, 0.171 with all); `radical` = semantic type (J=0.493 with meaning).

**Complementary pair: `family` + `direct`**

`family` and `direct` answer opposite questions about the same confusion set:

| char | family | direct | reading |
|---|---|---|---|
| 清 | 青 | 氵 | 青-family member, distinguished by water radical |
| 情 | 青 | 忄 青 | 青-family member, distinguished by heart radical |
| 蒋 | 艹 | 将 | grass-family member, distinguished by 将 |
| 明 | 月 | 日 月 | moon-family member, also distinguished by 日 |
| 认 | 讠 | 讠 人 | speech-family member, distinguished by 人 |

Together: "belongs to [family] group, identified by [direct]" — a complete confusion-pair description.

**`consensus` as reliability filter**

When consensus is smaller than both parents, it identifies the single most agreed-upon component. When empty (育, 童, 祝), the two traditions completely disagree — a signal that this character's decomposition is genuinely ambiguous.

| char | direct | memodevice | consensus | interpretation |
|---|---|---|---|---|
| 明 | 日 月 | 囧 月 | 月 | only 月 agreed on; 日 vs 囧 is a genuine disagreement |
| 育 | 亠 厶 … | ⺼ 子 | ∅ | complete disagreement — both may be valid traditions |
| 除 | 阝 余 | 阝 余 | 阝 余 | full agreement |
| 膀 | 月 旁 | ⺼ 旁 | 旁 | 月/⺼ are same glyph, normalization missed; only 旁 agreed |

**`hint` as etymology, not structure**

`hint` is the only approach that captures **historical origin**: it systematically extracts traditional forms and historical components from the hint text.

| char | hint | memodevice | what hint adds |
|---|---|---|---|
| 归 | 歸 止 帚 | 刂 彐 | traditional 歸 = 帚 (broom) + 止 (foot) |
| 准 | 準 氵 隼 | 冫 隹 | traditional 準 = 氵 (water) + 隼 (falcon) |
| 庆 | 慶 廌 心 | 广 大 | traditional 慶 = 廌 (mythical animal) + 心 (heart) |
| 阳 | 陰 陽 阴 月 日 | 阝 日 | traditional pair 陰/陽 + their shared components |

This makes `hint` the most useful for etymology-based mnemonics. Its 38 uniquely-covered characters are mostly simple modern chars (八, 九, 十) whose modern structure is too simple to yield structural components but whose hint text names their etymological origins.

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

Each idea is a distinct angle; implement only after running the comparison analysis above.

- **Hint text mining** — the `hint` field in `data_memodevice.json` is free-text prose (e.g. "田 represents the meaning and 尚 represents the sound"). Mining CJK character mentions from this text would surface components the human author emphasized but did not include in the structured `components` field. Different from the `memodevice` approach which uses the structured field.

- **1v1 contrastive filter** — instead of removing components shared by *all* confusables, remove only what this character shares with its *single closest* confusable (highest Jaccard). Produces the minimal discriminating set for the one pair that matters most. A different filtering strategy, not a new source; applies on top of any existing component map.

- **Information gain** — for each character, rank components by information gain: which component, if known, most reduces uncertainty about which character this is within the confusable set? Decision-tree feature selection applied to character identity. Different from rarity-based salience — a common component shared by only 3 very confusable neighbours scores higher than a rare component shared with no confusable.

- **Positional stability** — a component that always appears in the same structural slot across all characters that contain it (木 is always left in ⿰木X) is more reliably memorable than one that drifts. Ordering by stability — most stable first — gives the learner the most consistent visual anchor first.

- **HSK anchor** — among a character's components, which are themselves HSK vocabulary? An HSK component is a "free" mnemonic anchor — the learner already has a word-level memory to attach it to. Ordering by HSK level of the component (lowest = most known) is pedagogically more useful than structural ordering.

- **Semantic indicator as primary component** — for pictophonetic chars, lead the decomposition with the semantic component (meaning-carrier, from MMA etymology). Within a phonetic family (all containing 青), the semantic indicator (氵/日/忄/讠/目) is always the discriminating one. Differs from `meaning` in that it uses MMA etymology rather than memodevice curation.

- **Position-invariant components** — build confusable detection on position-agnostic component membership: 削=⿰肖刂 and 梢=⿰木肖 both contain 肖. The current `build_char_index` uses slot-labelled features (L=肖 ≠ R=肖) so these two would not be detected as confusables. A position-invariant confusable set would surface more cross-slot confusion pairs.

- **Depth-2 ancestry components** — include components reachable at depth-2 through different intermediaries: 骑(马+奇) and 荷(艹+何) both reach 可 via different depth-1 children. Surfaces hidden structural kinship invisible to direct decomposition.

- **Visual-only components** — for characters like 己/已/巳 where IDS decomposition is identical, pixel-level rendering can identify the visual feature that varies (open vs. closed stroke end). Requires PIL + font file; uniquely covers single-stroke confusables that all other approaches miss.

- **Contrastive decomposition** — instead of a flat component list, express each component as an explicit contrast: `{vs: 睛, ours: 日, theirs: 目}`. Makes the decomposition directly actionable for card display and ties each component to a specific confusable. Requires changing the output format.

