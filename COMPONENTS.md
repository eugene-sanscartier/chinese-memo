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

Active files: `direct`, `all`, `hanzi`, `rare`, `contrastive`, `family`, `radical`, `memodevice`, `meaning`, `consensus`, `hint`, `pinyin`, `merged`.

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
- **Rare** — components from `all_map` that appear in ≤2% of the dataset (~60/2998 chars), sorted by global frequency ascending. NOT filtered by `_discriminating` — the question is different: "what globally rare structural element is this character built from?" rather than "what distinguishes it from its specific confusables?". Covers 76 chars that `all` leaves empty — characters whose rare component is shared by all their confusables (so `_discriminating` returns nothing), but `rare` still surfaces it as the most unique structural element globally. Drops common components even when locally discriminating (e.g. 土, 口, 木 in `all` → absent from `rare`).
- **Contrastive** — components from `all_map` unique to this character vs its SINGLE closest confusable (highest Jaccard in `similar_idx`), BFS order. Different strategy from `_discriminating` (which removes what ALL confusables share): `contrastive` removes only what the closest one has. This produces a FOCUSED set for the hardest confusion pair. 82 chars get deeper BFS components that `direct` misses (e.g. 前: direct=`['刂']`, contrastive=`['刂','䒑']`); 1184 chars lose components that `direct` keeps but are shared with the closest confusable (e.g. 常: direct=`['𫩠','巾']`, contrastive=`['𫩠']` — 巾 shared with 常's closest lookalike).
- **Pinyin** — components from `all_map` that share the character's pinyin syllable (tone-stripped), BFS order. NOT filtered by `_discriminating` — the phonetic carrier is intentionally group-binding. Detects phonetic components for 形声字 from acoustic signal alone: no etymology annotations required. Coverage is intentionally low (876/29%) because only 43% of 形声字 in the dataset still have phonetic components whose pronunciation matches exactly (the rest diverged over time). When it fires, it is highly reliable: pinyin=`['各']` for 阁(gé) → MMA confirms phonetic=各; pinyin=`['良']` for 粮(liáng) → MMA confirms phonetic=良.

### Approach comparison

Coverage (non-empty / 2998 characters):

| approach | non-empty | uniquely covers |
|---|---|---|
| memodevice | 2830 (94%) | 1 |
| merged | 2758 (92%) | 0 |
| hanzi | 2732 (91%) | 0 |
| rare | 2681 (89%) | **76** |
| direct | 2675 (89%) | 0 |
| family | 2672 (89%) | 1 |
| all | 2646 (88%) | 1 |
| hint | 2639 (88%) | **38** |
| contrastive | 2576 (85%) | 0 |
| consensus | 2438 (81%) | 0 |
| meaning | 1881 (63%) | 0 |
| radical | 1813 (60%) | 3 |
| pinyin | 876 (29%) | 0 |

`hint` uniquely covers 38 chars (simple chars like 八, 九, 十 with rich etymological hints but simple modern structure). `rare` uniquely covers 76 chars where `all` returns empty — characters whose components are all shared by every confusable (not locally discriminating) but still contain a globally rare structural element (e.g. 当: all=`[]`, rare=`['彐']`).

Pairwise Jaccard (average over chars where at least one approach is non-empty):

| pair | J | | pair | J |
|---|---|---|---|---|
| consensus vs memodevice | **0.794** | | meaning vs radical | 0.493 |
| consensus vs direct | 0.764 | | meaning vs family | 0.464 |
| direct vs memodevice | 0.694 | | radical vs family | 0.433 |
| hint vs memodevice | 0.632 | | consensus vs hint | 0.538 |
| contrastive vs direct | 0.737 | | contrastive vs all | 0.513 |
| direct vs all | 0.633 | | rare vs all | 0.654 |
| direct vs hint | 0.469 | | rare vs direct | 0.483 |
| direct vs hanzi | 0.314 | | contrastive vs family | 0.242 |
| hanzi vs family | **0.168** | | rare vs family | 0.247 |
| family vs direct | 0.227 | | pinyin vs direct | 0.251 |
| family vs all | **0.171** | | pinyin vs family | **0.030** |

**Four structural dimensions** — approaches cluster into four distinct signals:

1. *Named structural level* (`direct`, `memodevice`, `consensus`, `contrastive`): intermediate sub-characters (将, 壹, 阝). High mutual Jaccard (0.633–0.794). These are the components a human uses in a mnemonic. `contrastive` (J=0.737 with direct) is a stricter variant focused on the closest confusion pair.
2. *Primitive level* (`hanzi`, `all`, `rare`): near-stroke or globally rare elements (丬, 亠, 冖, 彐). Low Jaccard with named-level sources. `rare` (J=0.654 with all) filters `all_map` by global rarity — keeps the most unique building blocks.
3. *Relational level* (`family`, `radical`, `meaning`): a character's ROLE in its confusion group. `family` = structural group-binding (J=0.227 with direct); `radical` = semantic type; `meaning` = semantic core.
4. *Acoustic level* (`pinyin`, `hint`): sound-based or historical. `pinyin` (J=0.030 with family!) detects phonetic carriers purely from pronunciation data; `hint` is etymological prose.

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

**Complementary pair: `pinyin` + `family`**

`pinyin` and `family` both find group-binding components, but for completely different groupings — they almost always disagree (J=0.030). `family` finds what visually confusable characters SHARE (semantic component); `pinyin` finds the PHONETIC component from acoustic signal. Together they give the full 形声字 analysis:

| char | family | pinyin | reading |
|---|---|---|---|
| 阁 | 门 | 各 | 门-group member (structural), pronounced via 各 (phonetic) |
| 粮 | 米 | 良 | 米-group member (structural), pronounced via 良 (phonetic) |
| 粉 | 米 | 分 | 米-group member (structural), pronounced via 分 (phonetic) |
| 糊 | 米 | 胡 | 米-group member (structural), pronounced via 胡 (phonetic) |
| 清 | 青 | 青 | both agree — 青 is both the structural binder AND the phonetic carrier |

`family` is consistently the semantic component (阝, 米, 木, 口, 田); `pinyin` is consistently the phonetic component (各, 良, 分, 胡). The rare agreement (98/870 = 11%) occurs when a character like 清 has the same element serving both roles.

`pinyin` detects only 43% of 形声字 — the ones where modern pronunciation still exactly matches the phonetic component. The 57% where it's silent are characters whose phonetic has diverged over time (e.g., 语(yù) has phonetic 吾(wú), 说(shuō) has phonetic 兑(duì)).

**`rare` vs `all` — global vs local scoping**

`rare` and `all` use the same source (`all_map`) but different filters:
- `all`: locally scoped — removes components shared by this character's confusables
- `rare`: globally scoped — removes components shared by >2% of the dataset

| char | all | rare | what differs |
|---|---|---|---|
| 尚 | 冋 冂 口 | 冋 冂 | 口 is common (>2% of chars) → rare drops it |
| 堂 | 𫩠 土 | 𫩠 | 土 is common → rare drops it; 𫩠 is rare |
| 间 | 日 | 门 | 日 is common (dropped by rare); 门 is rare enough to keep |
| 当 | *(empty)* | 彐 | all finds nothing discriminating; rare surfaces 彐 as the globally rare identifier |

`rare` uniquely covers 76 chars where `all` returns empty — characters whose components are all shared by every confusable, but still have a globally rare element. For these chars, `rare` provides the only structural anchor.

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

- **1v1 contrastive filter** (`contrastive`) — instead of removing components shared by *all* confusables, remove only what this character shares with its *single closest* confusable (highest Jaccard). Produces the minimal discriminating set for the most dangerous confusion pair. More aggressive than `_discriminating` for components shared with the closest neighbor; answers "what makes me different from my hardest-to-distinguish lookalike?" Applies to `all_map`.

- **Globally rare components** (`rare`) — apply a global rarity filter instead of the confusable-scoped discriminating filter: keep only `all_map` components that appear in ≤2% of the dataset characters (~60 for 2998 chars). Sort rarest-first. Does NOT use `_discriminating` — the question is "what rare structural element is this character built from globally?" Characters made entirely of common primitives (木, 口, 日) yield empty; those containing rare elements (禹, 黄, 黹) yield them first. Different signal from `_discriminating` which is locally scoped.

- **Pinyin-based phonetic component** (`pinyin`) — for each character, find which `all_map` components share the same pinyin syllable (tone-stripped). No `_discriminating` filter — the phonetic carrier is intentionally the group-binding element. Detects phonetic components for 形声字 from acoustic signal alone, without MMA etymology annotations. For ideographic/pictographic characters, output is empty. Complements `family` (detects group binding structurally); `pinyin` detects it acoustically.

- **Information gain** — for each character, rank components by information gain: which component, if known, most reduces uncertainty about which character this is within the confusable set? Decision-tree feature selection applied to character identity. Different from rarity-based salience — a common component shared by only 3 very confusable neighbours scores higher than a rare component shared with no confusable.

- **Positional stability** — a component that always appears in the same structural slot across all characters that contain it (木 is always left in ⿰木X) is more reliably memorable than one that drifts. Ordering by stability — most stable first — gives the learner the most consistent visual anchor first.

- **HSK anchor** — among a character's components, which are themselves HSK vocabulary? An HSK component is a "free" mnemonic anchor — the learner already has a word-level memory to attach it to. Ordering by HSK level of the component (lowest = most known) is pedagogically more useful than structural ordering.

- **Semantic indicator as primary component** — for pictophonetic chars, lead the decomposition with the semantic component (meaning-carrier, from MMA etymology). Within a phonetic family (all containing 青), the semantic indicator (氵/日/忄/讠/目) is always the discriminating one. Differs from `meaning` in that it uses MMA etymology rather than memodevice curation.

- **Position-invariant components** — build confusable detection on position-agnostic component membership: 削=⿰肖刂 and 梢=⿰木肖 both contain 肖. The current `build_char_index` uses slot-labelled features (L=肖 ≠ R=肖) so these two would not be detected as confusables. A position-invariant confusable set would surface more cross-slot confusion pairs.

- **Depth-2 ancestry components** — include components reachable at depth-2 through different intermediaries: 骑(马+奇) and 荷(艹+何) both reach 可 via different depth-1 children. Surfaces hidden structural kinship invisible to direct decomposition.

- **Visual-only components** — for characters like 己/已/巳 where IDS decomposition is identical, pixel-level rendering can identify the visual feature that varies (open vs. closed stroke end). Requires PIL + font file; uniquely covers single-stroke confusables that all other approaches miss.

- **Contrastive decomposition** — instead of a flat component list, express each component as an explicit contrast: `{vs: 睛, ours: 日, theirs: 目}`. Makes the decomposition directly actionable for card display and ties each component to a specific confusable. Requires changing the output format.

