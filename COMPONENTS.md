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
| `ids_dict` | `data/source/reference/ids_dictionary.json` | `ids` string, `components` (full recursive list), `decomposition` (depth-1 structured children) |
| `mma_dict` | `data/source/reference/dictionary_makemeahanzi.txt` | `radical` (KangXi), etymology (`type`, `phonetic`, `semantic`, `hint`), `pinyin`, stroke count |
| `decomposer` | `HanziDecomposer()` | level-2 component decomposition (independent source, often disagrees with IDS) |
| `memo_dict` | `data/derived/memodevice/data_memodevice.json` | `components` (typed: `meaning`/`sound`/`iconic`/`simplified`/`remnant`), `hint`, pinyin, gloss |
| `char_dict` | `data/source/reference/dictionary_char.jsonl` | `strokeCount`, HSK level, corpus frequency rank, `gloss` |

## Current output — `data_components/data_components_*.json`

One file per decomposition approach. Each maps every character to a list of bare component characters — the discriminating subset of its full decomposition. Empty list means no discriminating component could be found for this approach (e.g. character's radical is shared with all its confusables).

```json
{
  "字": ["comp_a", "comp_b"],
  "字": ["comp_a"],
  "字": []
}
```

Active files: `direct`, `all`, `hanzi`, `rare`, `contrastive`, `family`, `radical`, `memodevice`, `meaning`, `consensus`, `hint`, `pinyin`, `pos_inv`, `mma_semantic`, `memo_diff`, `absent`, `hsk_anchor`, `sem_sibling`, `sem_absent`, `homophone`, `phonetic_scope`, `merged`.

## Implemented decomposition approaches

- **Direct** — the immediate structural parts of a character: depth-1 IDS children in positional reading order.
- **All** — the full recursive IDS ancestry (superset of direct), ordered by BFS depth so shallower (more visually prominent) components come first.
- **Hanzi** — decomposition from HanziDecomposer, an independent source. Disagreements with IDS surface components the IDS tree misses; decomposes at finer granularity than IDS (near-primitive elements).
- **Radical** — single KangXi radical from MMA (`mma_dict['radical']`). Always exactly one entry; the traditional dictionary-lookup component. Discriminating within phonetic families (each sibling has a different radical) but often shared within structural confusion sets.
- **Memodevice** — human-curated typed decomposition from `data/derived/memodevice/data_memodevice.json`. Meaning-type components first, then sound, then iconic/other. Genuinely disagrees with IDS: e.g. 明=囧+月 (memodevice) vs 日+月 (IDS). Coverage: 100% of characters have entries.
- **Meaning** — meaning-type components only from memodevice (semantic core). Strips phonetic and iconic parts; gives the component that carries the character's meaning. Coverage: ~77% of characters have at least one meaning component.
- **Merged** — components confirmed discriminating by ≥2 of the five structural sources (direct, all, hanzi, radical, memodevice), ordered by vote count. Empty when no component reaches the ≥2 threshold.
- **Family** — components shared by ≥50% of the character's confusables, ordered by share fraction descending. Intentionally NOT filtered by `_discriminating` — shows what BINDS the confusion group rather than what differs. Complementary to `direct`: together they tell the full story: "belongs to [family] group, distinguished by [direct]".
- **Consensus** — strict intersection of `direct_map ∩ memodevice_map`, then `_discriminating` applied. Only components that both IDS structure and human curation independently name at the named sub-character level. When smaller than both parents (e.g. 明=`['月']` vs direct's `['日','月']` and memo's `['囧','月']`), it identifies the single most agreed-upon component.
- **Hint** — CJK characters extracted from the free-text `hint` field in `data/derived/memodevice/data_memodevice.json`, in text-appearance order. Unlike all other approaches, this is **etymological**: the hint text systematically describes traditional forms and historical components (归: hint=`['歸','止','帚']` — broom+foot=return; 准: `['準','氵','隼']` — water+falcon). Answers "where did this character come from?" not "how is it structured today?".
- **Rare** — components from `all_map` that appear in ≤2% of the dataset (~60/2998 chars), sorted by global frequency ascending. NOT filtered by `_discriminating` — the question is different: "what globally rare structural element is this character built from?" rather than "what distinguishes it from its specific confusables?". Covers 76 chars that `all` leaves empty — characters whose rare component is shared by all their confusables (so `_discriminating` returns nothing), but `rare` still surfaces it as the most unique structural element globally. Drops common components even when locally discriminating (e.g. 土, 口, 木 in `all` → absent from `rare`).
- **Contrastive** — components from `all_map` unique to this character vs its SINGLE closest confusable (highest Jaccard in `similar_idx`), BFS order. Different strategy from `_discriminating` (which removes what ALL confusables share): `contrastive` removes only what the closest one has. This produces a FOCUSED set for the hardest confusion pair. 82 chars get deeper BFS components that `direct` misses (e.g. 前: direct=`['刂']`, contrastive=`['刂','䒑']`); 1184 chars lose components that `direct` keeps but are shared with the closest confusable (e.g. 常: direct=`['𫩠','巾']`, contrastive=`['𫩠']` — 巾 shared with 常's closest lookalike).
- **Pinyin** — components from `all_map` that share the character's pinyin syllable (tone-stripped), BFS order. NOT filtered by `_discriminating` — the phonetic carrier is intentionally group-binding. Detects phonetic components for 形声字 from acoustic signal alone: no etymology annotations required. Coverage is intentionally low (876/29%) because only 43% of 形声字 in the dataset still have phonetic components whose pronunciation matches exactly (the rest diverged over time). When it fires, it is highly reliable: pinyin=`['各']` for 阁(gé) → MMA confirms phonetic=各; pinyin=`['良']` for 粮(liáng) → MMA confirms phonetic=良.
- **Pos_inv** — position-invariant confusable detection: computes Jaccard over bare `all_map` component sets (no slot labels) using an inverted index; finds a new confusable group at Jaccard ≥ 0.25; then applies `_discriminating` against that group. The current `build_char_index` uses positional features (L=肖 ≠ R=肖), so 削=⿰肖刂 and 梢=⿰木肖 have positional Jaccard=0 — they are not confusables positionally. Pos_inv sets their Jaccard to 1/3 and detects the full 肖-family (梢/峭/悄/销/消/哨/俏/屑/稍/削). Within that family, 削 is the only one with 刂 → pos_inv=`['肖','刂']` vs direct=`['肖']`. Gives MORE components than `direct` in 1575 chars (cross-slot families surface new discriminating requirements). J=0.703 with `all` (closest existing approach: both use full recursive components, different similarity metric).
- **Mma_semantic** — extracts the `semantic` field from MMA etymology for pictophonetic chars only (coverage 56%). Applies `_discriminating` with standard confusable set. Different from `meaning` (memodevice source, 113 chars disagree) and `family` (structural confusable grouping, J=0.512). J=0.003 with `pinyin` — essentially orthogonal. **Together, `mma_semantic` + `pinyin` give the complete 形声字 structure from two independent sources: `mma_semantic` gives the meaning-carrying component, `pinyin` gives the sound-carrying component.** 678/685 jointly-firing chars decode completely (only 7 agree on the same element). Example: 清 → semantic=`['氵']` (water meaning) + phonetic=`['青']` (qīng sound).
- **Hsk_anchor** — from the discriminating components in `all_map`, keeps only those that are themselves HSK vocabulary (have `hsk_level` in `similar_idx` — i.e., they're standalone study characters, not radical forms). Ordered by HSK level ascending. Coverage 76% (2266 chars). Avg 1.7 components — the most compact approach. The filter is pedagogically meaningful: 氵 (water radical) has no HSK level and is excluded; 青 (qīng, blue-green, HSK 3) is included. For 清: `hsk_anchor=[]` because 清's only discriminating component (氵) is a radical form without vocabulary status. For 情: `hsk_anchor=['青']` — among its discriminating components {忄, 青}, only 青 is vocabulary. For 骑: `hsk_anchor=['口','大','奇','可']` — the HSK vocabulary sub-components of 奇 (口 HSK1, 大 HSK1, 可 HSK2, 奇 HSK5) all show up as vocabulary anchors. J=0.597 with `all` (filtered subset); J=0.553 with `sem_sibling` (both tend to surface "named" non-radical characters as the discriminating element). Answers: "which discriminating component does the learner already know as a standalone vocabulary word?"
- **Sem_absent** — components present in the 8 closest radical siblings (by `all_map` Jaccard) that this character lacks. Uses the same sibling selection as `sem_sibling`. Coverage 97% (highest of all approaches). Avg 8.4 components. J=0.000 with `sem_sibling` (perfect complement by construction: sem_sibling = what C has that siblings lack; sem_absent = what siblings have that C lacks). J=0.000 with `direct`/`all`/`family` — completely orthogonal to all presence-based approaches. J=0.202 with `absent` (similar absent signal, different confusable grouping — radical family vs visual). Together `sem_sibling` + `sem_absent` give the complete **phonetic contrast map** within the radical family: "C uses X as its phonetic; its closest structural siblings use Y, Z, W instead." For 清: sem_sibling=`['青']`, sem_absent=`['舌','齐','㐬','肖','工']` → "청 uses 青 as phonetic; closest 氵-siblings use 舌(活/话)/齐/肖(消/潇)/工(江) instead." For 桥: sem_sibling=`['乔','大','夭']`, sem_absent=`['口','可','奇']` → "桥 uses 乔; closest 木-siblings use 口(杲?)/可(椁?)/奇(椅) instead."
- **Phonetic_scope** — confusable group = all chars sharing the same tone-stripped syllable (initial+final, any tone). Broader than `homophone` (exact tone): for 情(qíng2), phonetic_scope includes qīng1(清/靖/蜻)/qíng2(情/晴)/qǐng3(请)/qìng4(庆/磬...) while homophone includes only qíng2 chars. Coverage 90% (2708 chars). Avg 3.0 components. J=0.827 with `homophone` (high overlap — same logic, broader group). J=0.106 with `pinyin` (different operation: pinyin finds the phonetic CARRIER; phonetic_scope finds structural DISCRIMINATORS). Key divergences: for 情(qíng2), homophone=`['忄']` (all qíng2 homophones share 青 → removed) but phonetic_scope=`['忄','青']` (qīng1 chars like 靖 and qìng4 chars like 庆 don't have 青 → 青 survives). For 命(mìng4), homophone=`[]` (no same-tone homophones in dataset) but phonetic_scope=`['令','口','亽','龴','𠆢']` (cross-tone míng/mǐng/mìng chars exist). **374 chars fire in phonetic_scope but not homophone** — chars with cross-tone phonetic siblings but no exact-tone homophones.
- **Memo_diff** — components present in `memo_map` but ABSENT from `all_map` (IDS recursive ancestry). J=0.000 with `all` by construction (it's the set-difference). J=0.189 with `memodevice` (memo_diff ⊆ memodevice). 726 chars (24%) have non-empty memo_diff. Two categories: (1) **normalization variants**: memodevice uses 尚 while IDS uses its Unicode variant 𫩠 — affects 9 chars (常/党/掌/堂/赏 family); (2) **genuine structural reanalyses** (717 chars): memodevice decomposes at a named level that IDS doesn't — e.g. 当: memo_diff=`['田','尚']` while IDS gives only primitives `['彐','⺌']`; 光: memo_diff=`['火','卩']` while IDS gives `['一','儿','⺌']`; 肖: memo_diff=`['小','月']` while IDS gives only `['⺌']`. These are the characters where the memodevice structural tradition makes a meaningfully DIFFERENT choice from IDS — not just finer or coarser, but a different structural analysis entirely.
- **Absent** — components present in ≥1 visual confusable (from `similar_idx`) but absent from this character, ordered by count descending (how many confusables carry this component). J≈0.000 with ALL other approaches by construction: every other approach returns components IN the character; `absent` returns components NOT in it. Avg 11.8 components per non-empty char (large because it aggregates across all confusables). Covers 84 chars where `direct` is empty — even when there's nothing structurally discriminating IN this char, `absent` shows what the confusables have that this char lacks. Answers: "this character is NOT 间 (no 耳), NOT 问 (no 口), NOT 闯 (no 马)" — the learner can rule out confusables by what's missing.
- **Sem_sibling** — discrimination within KangXi radical family: confusable set = the 8 closest chars (by `all_map` Jaccard) that share the same MMA radical. Applies `_discriminating` against this semantic sibling group. J=0.025 with `mma_semantic` (nearly orthogonal — see below). Coverage: 2663 chars (89%). Avg 2.2 components per char. Key insight: within the radical family, the radical component is shared by all siblings → it falls out of `_discriminating` → what remains is the NON-RADICAL structural part, which for pictophonetic chars IS the phonetic component. For 清(氵+青): 氵-radical family → 青 is the discriminating phonetic. **`sem_sibling` fires for 1790 chars where `pinyin` is silent** — it recovers the phonetic component structurally even when modern pronunciation has diverged (e.g. 树: sem_sibling=`['对','又','寸']`, the phonetic 对(duì) has diverged from 树(shù) — but structurally it's still there). Unlike `pinyin` (acoustic signal, exact syllable match), `sem_sibling` uses structural grouping and is pronunciation-agnostic.
- **Homophone** — discrimination within homophone group: confusable set = all dataset chars sharing ≥1 exact pinyin reading (with tone) from MMA. Applies `_discriminating` against this phonetic group. Coverage: 2334 chars (78%). Avg 2.9 components per char. J=0.412 with `direct`, J=0.106 with `pinyin`. The confusable grouping is phonetically defined, not visually — so results frequently disagree with `direct`: for 情(qīng), homophone=`['忄']` (not `['忄','青']`) because 青 is shared by ALL qīng-homophones; for 清(qīng), homophone=`['氵','青']` because some qīng-homophones lack 氵. 664 chars with distinct homophone groups (>1 homophone), covering 2334 chars total. Answers: "given that this is pronounced qīng, which structural component makes it THIS character rather than 清/请/晴/...?"

### Approach comparison

Coverage (non-empty / 2998 characters):

| approach | non-empty | uniquely covers |
|---|---|---|
| sem_absent | 2912 (97%) | 0 |
| memodevice | 2830 (94%) | 1 |
| merged | 2758 (92%) | 0 |
| phonetic_scope | 2708 (90%) | 0 |
| hanzi | 2732 (91%) | 0 |
| rare | 2681 (89%) | **76** |
| absent | 2678 (89%) | 0 |
| direct | 2675 (89%) | 0 |
| family | 2672 (89%) | 1 |
| sem_sibling | 2663 (89%) | 0 |
| all | 2646 (88%) | 1 |
| hint | 2639 (88%) | **38** |
| pos_inv | 2608 (87%) | 0 |
| contrastive | 2576 (85%) | 0 |
| consensus | 2438 (81%) | 0 |
| homophone | 2334 (78%) | 0 |
| hsk_anchor | 2266 (76%) | 0 |
| meaning | 1881 (63%) | 0 |
| radical | 1813 (60%) | 3 |
| mma_semantic | 1685 (56%) | 0 |
| pinyin | 876 (29%) | 0 |
| memo_diff | 726 (24%) | 0 |

`hint` uniquely covers 38 chars (simple chars like 八, 九, 十 with rich etymological hints but simple modern structure). `rare` uniquely covers 76 chars where `all` returns empty — characters whose components are all shared by every confusable (not locally discriminating) but still contain a globally rare structural element (e.g. 当: all=`[]`, rare=`['彐']`). `absent` covers 84 chars where `direct` is empty — even with no discriminating component present IN the char, the approach still surfaces what confusables have that this char lacks.

Pairwise Jaccard (average over chars where at least one approach is non-empty):

| pair | J | | pair | J |
|---|---|---|---|---|
| consensus vs memodevice | **0.794** | | rare vs all | 0.654 |
| consensus vs direct | 0.764 | | pos_inv vs all | 0.703 |
| direct vs memodevice | 0.694 | | mma_semantic vs meaning | 0.565 |
| pos_inv vs direct | 0.543 | | mma_semantic vs family | 0.512 |
| contrastive vs direct | 0.737 | | mma_semantic vs direct | 0.162 |
| direct vs all | 0.633 | | contrastive vs family | 0.242 |
| direct vs hanzi | 0.314 | | rare vs family | 0.247 |
| family vs direct | 0.227 | | pinyin vs direct | 0.251 |
| hanzi vs family | **0.168** | | pinyin vs family | **0.030** |
| family vs all | **0.171** | | mma_semantic vs pinyin | **0.003** |
| memo_diff vs all | **0.000** | | memo_diff vs memodevice | 0.189 |
| sem_sibling vs all | 0.771 | | sem_sibling vs pos_inv | 0.601 |
| sem_sibling vs direct | 0.466 | | sem_sibling vs mma_semantic | **0.025** |
| sem_sibling vs family | 0.126 | | sem_sibling vs pinyin | 0.170 |
| sem_sibling vs radical | **0.023** | | homophone vs sem_sibling | 0.521 |
| homophone vs all | 0.627 | | homophone vs mma_semantic | 0.196 |
| homophone vs direct | 0.412 | | homophone vs family | 0.335 |
| homophone vs pinyin | 0.106 | | absent vs (all others) | **≈0.000** |
| hsk_anchor vs all | 0.597 | | hsk_anchor vs sem_sibling | 0.553 |
| hsk_anchor vs direct | 0.482 | | hsk_anchor vs mma_semantic | 0.085 |
| hsk_anchor vs family | 0.114 | | hsk_anchor vs pinyin | 0.187 |
| phonetic_scope vs homophone | **0.827** | | phonetic_scope vs all | 0.752 |
| phonetic_scope vs direct | 0.483 | | phonetic_scope vs pinyin | 0.106 |
| sem_absent vs sem_sibling | **0.000** | | sem_absent vs absent | 0.202 |
| sem_absent vs direct | **0.000** | | sem_absent vs all | **0.000** |
| sem_absent vs family | **0.000** | | sem_absent vs radical | 0.006 |

**Five structural dimensions** — approaches cluster into five distinct signals:

1. *Named structural level* (`direct`, `memodevice`, `consensus`, `contrastive`, `pos_inv`): intermediate sub-characters (将, 壹, 阝). High mutual Jaccard (0.543–0.794). `pos_inv` (J=0.543 with direct, J=0.703 with all) uses a position-invariant confusable set, surfacing cross-slot component-sharing confusables that positional detection misses.
2. *Primitive level* (`hanzi`, `all`, `rare`): near-stroke or globally rare elements (丬, 亠, 冖, 彐). Low Jaccard with named-level sources. `rare` (J=0.654 with all) filters `all_map` by global rarity.
3. *Relational level* (`family`, `radical`, `meaning`, `mma_semantic`): a character's ROLE in its confusion group or semantic class. `family` = structural group-binding; `mma_semantic` (J=0.512 with family, J=0.162 with direct) = MMA linguistic annotation of the semantic carrier.
4. *Acoustic/etymological level* (`pinyin`, `hint`, `memo_diff`): non-structural. `pinyin` detects phonetic carriers acoustically (J=0.003 with mma_semantic — nearly orthogonal); `hint` = etymological prose; `memo_diff` (J=0.000 with all!) = memodevice structural reanalyses absent from IDS.
5. *Alternative confusable groupings* (`sem_sibling`, `homophone`, `absent`, `hsk_anchor`, `sem_absent`, `phonetic_scope`): redefine the confusable set, the signal direction, or the component filter. `sem_sibling` uses semantic/radical grouping; `homophone` uses exact-tone phonetic grouping; `phonetic_scope` uses tone-agnostic syllable grouping (J=0.827 with homophone, broader); `absent` inverts the signal (components NOT in the character — J≈0.000 with all presence-based approaches); `sem_absent` inverts absent over the semantic family (J=0.000 with sem_sibling — perfect complement); `hsk_anchor` filters by learner knowledge state (vocabulary-word components only, avg 1.7 components).

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

**Complementary triple: `mma_semantic` + `pinyin` = complete 形声字 decode**

`mma_semantic` and `pinyin` are nearly orthogonal (J=0.003) because they give the two DIFFERENT elements of a 形声字 from two independent sources:

| char | mma_semantic | pinyin | reading |
|---|---|---|---|
| 清 | 氵 | 青 | water meaning + qīng sound → "clear water" |
| 情 | 忄 | 青 | heart meaning + qīng sound → "emotion" |
| 请 | 讠 | 青 | speech meaning + qīng sound → "to request" |
| 阁 | 门 | 各 | gate/building meaning + gé sound |
| 粮 | 米 | 良 | grain meaning + liáng sound |
| 树 | 木 | (silent) | wood meaning; phonetic 对 diverged |

678/685 jointly-firing chars decode completely (semantic + phonetic as two distinct elements). The 7 that agree on the same element are cases where semantic = phonetic (the component serves both roles). Together with `hint` (historical origin), these three acoustic/etymological approaches give the full linguistic picture of a character.

**`pos_inv` vs `direct` — cross-slot confusable discrimination**

`pos_inv` detects a broader confusable set (bare component Jaccard, no position) and applies `_discriminating` against it. 1575 chars get MORE components than `direct` because cross-slot families impose additional discriminating requirements:

| char | IDS | direct | pos_inv | why pos_inv adds more |
|---|---|---|---|---|
| 削 | ⿰肖刂 | 肖 | 肖 刂 | cross-slot 肖-family (梢/峭/悄/销/消...) makes 刂 required |
| 间 | ⿵门日 | 日 | 门 日 | cross-slot 门-family adds 门 as co-discriminator |
| 稽 | ⿰禾⿱尤旨 | *(empty)* | 禾 尤 旨 匕 | positional detection found nothing; cross-slot finds 4 |
| 第 | ⿱竹⿹丿弔 | *(empty)* | 竹 弔 | positional detection found nothing; cross-slot finds 2 |

削 has 9 cross-slot 肖-family members (梢/峭/悄/销/消/哨/俏/屑/稍). Positionally they look nothing like 削; component-wise they all share 肖. Within that group, only 削 has 刂 → the knife is the true distinguishing element.

**`memo_diff` — where the two structural traditions diverge**

`memo_diff` (J=0.000 with `all`) contains components that memodevice sees but IDS doesn't. Two types:

1. **Normalization variants** (9 chars): 尚 vs 𫩠 (same character, different Unicode code points) — affects the 常/党/掌/堂/赏 family.
2. **Genuine structural reanalyses** (717 chars): memodevice makes a fundamentally different structural choice:

| char | memo_diff | IDS components | what diverges |
|---|---|---|---|
| 当 | 田 尚 | 彐 ⺌ | memodevice sees named components; IDS gives only primitives |
| 光 | 火 卩 | 一 儿 ⺌ | completely different structural reading |
| 肖 | 小 月 | ⺌ | memodevice sees 肖=top+moon; IDS gives just a primitive |
| 爽 | 爻 | 大 㸚 | memodevice sees the X-pattern (爻) inside 爽 |
| 夺 | 隹 | 大 寸 | memodevice sees the bird (隹) in 夺; IDS gives big+inch |

When `memo_diff` fires, it is ALWAYS absent from `all` — these components literally do not appear in the IDS decomposition. They represent the memodevice tradition's interpretation of structure that IDS chose not to encode. `memo_diff` ∪ `all` gives the full memodevice view.

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

**`sem_sibling` + `mma_semantic` = complete 形声字 decode via structural analysis**

`sem_sibling` (J=0.025 with `mma_semantic`) gives the two halves of a 形声字 from purely structural analysis — no acoustic signal required. `mma_semantic` = the semantic component (the shared radical); `sem_sibling` = the discriminating component within the radical family (= the phonetic component). This means `sem_sibling` recovers the phonetic component even when pronunciation has diverged (unlike `pinyin`, which requires exact syllable match):

| char | mma_semantic | sem_sibling | pinyin | note |
|---|---|---|---|---|
| 清 | 氵 | 青 | 青 | all agree — modern pronunciation matches |
| 桥 | 木 | 乔 大 夭 | 乔 | sem_sibling gives full ancestry of phonetic |
| 树 | 木 | 对 又 寸 | *(empty)* | 对(duì) diverged from 树(shù) — pinyin silent, sem_sibling finds it |
| 江 | 氵 | 工 | *(empty)* | 工(gōng) diverged from 江(jiāng) — pinyin silent |
| 海 | 氵 | 每 母 | *(empty)* | 每(měi) diverged from 海(hǎi) — pinyin silent |
| 辉 | 光 | 光 军 儿 冖 车 | *(empty)* | complex ancestry; no modern acoustic match |

`sem_sibling` fires for 1790 chars where `pinyin` is silent — it recovers the phonetic component structurally even after pronunciation divergence. Together `sem_sibling` + `mma_semantic` always give different elements (J=0.025) and jointly decode the complete 形声字 structure via structural analysis alone: no pronunciation data needed.

**`sem_sibling` + `radical` — structural complements**

J(sem_sibling, radical) = 0.023 — nearly orthogonal and for a clean reason:
- `radical`: returns ONLY the radical (1 component, what ALL radical siblings share)
- `sem_sibling`: returns components the radical siblings do NOT all share (= everything EXCEPT the radical)

They're exact complements. Together they give the complete structural decomposition: `radical` = the shared root, `sem_sibling` = the unique differentiator. Example: 粮: radical=`['米']`, sem_sibling=`['良','艮']` → rice-root identified by good-grain ancestry.

**`direct` + `absent` = complete bidirectional discrimination**

`direct` answers "what does this character have that confusables don't?" `absent` answers "what do confusables have that this character lacks?" Together they give the full discrimination picture — what this character IS (positive) and what it IS NOT (negative):

| char | direct | absent (top 5) | reading |
|---|---|---|---|
| 间 | 日 | 口 耳 人 才 亠 | has 日; lacks 口(→not问), 耳(→not闻), 马(→not闯) |
| 闻 | 耳 | 日 口 人 才 亠 | has 耳; lacks 日(→not间), 口(→not问) |
| 问 | 门 口 | 日 耳 人 才 亠 | has 门+口; lacks 日(→not间), 耳(→not闻) |
| 清 | 氵 | 米 立 目 犭 日 | has 氵; lacks 米(→not精), 立(→not静), 目(→not睛) |
| 桥 | 乔 | 马 车 女 矢 羊 | has 乔; lacks 马(→not骑), 车(→not辕) |

`absent` covers 84 chars where `direct` is empty — even with nothing discriminating in the character itself, `absent` still tells the learner what the lookalikes have that this char doesn't.

**`homophone` — when structure follows sound**

`homophone` uses a phonetically-defined confusable set (exact pinyin match including tone). It disagrees with `direct` in informative ways:

| char | direct | homophone | why they differ |
|---|---|---|---|
| 情 | 忄 青 | 忄 | 青 is shared by ALL qīng homophones → homophone drops it |
| 清 | 氵 | 氵 青 | 氵 discriminates vs visual lookalikes; homophone also needs 青 to distinguish from 情/请/晴 |
| 请 | 讠 青 | 讠 青 | visual and phonetic confusable sets largely agree |
| 晴 | 日 青 | 日 | 青 shared by all qīng homophones → homophone drops it |
| 宫 | 吕 | 宀 吕 口 | some gōng homophones lack 宀 → homophone adds it |
| 名 | 夕 | 夕 口 | phonetic set (míng homophones) differs from visual set — 口 needed for phonetic disambiguation |

Pattern: when a component is shared by all homophones, homophone drops it (even if direct keeps it because visual lookalikes don't have it). When a component is absent from some homophones but present here, homophone adds it (even if visual lookalikes all share it). Homophone and direct together reveal which components are "phonetically salient" vs "visually salient."

**`sem_sibling` + `sem_absent` = complete phonetic contrast map within radical family**

J(sem_sibling, sem_absent) = 0.000 — perfect complements:
- `sem_sibling`: what C has that its closest radical siblings lack (= C's phonetic component)
- `sem_absent`: what C's closest radical siblings have that C lacks (= sibling phonetic components)

Together they give the full phonetic landscape of the radical family:

| char | sem_sibling | sem_absent (top 5) | reading |
|---|---|---|---|
| 清 | 青 | 舌 齐 肖 工 | 清 uses 青; closest 氵-siblings use 舌(活?)/肖(消/潇)/工(江) |
| 江 | 工 | 舌 青 齐 肖 | 江 uses 工; closest 氵-siblings use 青(清/情)/舌/肖 |
| 桥 | 乔 大 夭 | 口 可 奇 甘 | 桥 uses 乔; closest 木-siblings use 可(椁)/奇(椅)/口(杲) |
| 树 | 对 又 寸 | 叒 双 反 | 树 uses 对; closest 木-siblings use 叒/双/反 |
| 松 | 公 八 厶 | 勹 勾 儿 夋 | 松 uses 公; closest 木-siblings use 勹/勾/夋 |

sem_absent J=0.000 with ALL structural presence approaches — it lives entirely in a different set space (absent components). J=0.202 with `absent` (same signal type — absence — but semantic family vs visual confusable group).

**`hsk_anchor` — the vocabulary lens**

`hsk_anchor` filters discriminating components to those the learner already knows as standalone vocabulary. With avg 1.7 components, it's the most compact approach. Key behavior:

| char | hsk_anchor | direct | note |
|---|---|---|---|
| 情 | 青 | 忄 青 | 忄 dropped (radical form, no HSK level); 青 kept (HSK 3) |
| 清 | *(empty)* | 氵 | 氵 is radical form only — no vocabulary anchor available |
| 骑 | 口 大 奇 可 | 奇 | sub-components of 奇 that ARE vocabulary (口HSK1/大HSK1/可HSK2/奇HSK5) all surface |
| 树 | 对 又 寸 | 对 | 又(HSK5)/寸 appear in all_map as discriminating AND are vocabulary |
| 晴 | 日 青 | 日 青 | both are vocabulary; full agreement |
| 粮 | 良 | 良 | 良 is vocabulary (fine, good); clean single anchor |

Useful for card generation: "what word the learner already knows can anchor this character's form?" When empty (清, most radical-only chars), the learner has no vocabulary-level anchor and must learn the radical form as a new element.

**`phonetic_scope` vs `homophone` — tight vs broad phonetic confusables**

J=0.827: mostly agree. The 17% that differ are the most analytically interesting cases. phonetic_scope adds 374 chars where homophone fires but cross-tone groups provide additional discrimination:

| char | homophone | phonetic_scope | divergence |
|---|---|---|---|
| 情 | 忄 | 忄 青 | homophone drops 青 (all qíng2 homophones share 青); scope keeps 青 (qīng1/qìng4 chars don't all have 青) |
| 晴 | 日 | 日 青 | same pattern — cross-tone chars break the 青-sharing |
| 命 | *(empty)* | 令 口 亽 | no same-tone homophones; cross-tone míng chars exist in dataset |

phonetic_scope fires for 374 chars where homophone gives nothing — these are chars with cross-tone phonetic siblings but no exact-tone homophones in the 2998-char dataset. `phonetic_scope` is a strict superset in coverage; it's the better default for phonetic confusable detection when the dataset is small relative to the full vocabulary.

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

- **Position-invariant confusable detection** (`pos_inv`) — the current `build_char_index` uses slot-labelled positional features (L=肖 ≠ R=肖), so 削=⿰肖刂 and 梢=⿰木肖 have positional Jaccard=0 and are not detected as confusables. `pos_inv` computes Jaccard over BARE component membership (no slot labels) using an inverted index, finds a new confusable set (threshold ≥ 0.25), and applies `_discriminating` against it. This surfaces cross-slot component-sharing confusion pairs invisible to the positional approach.

- **MMA semantic component** (`mma_semantic`) — extracts the `semantic` field from MMA etymology for pictophonetic chars: the component that carries the character's meaning, according to the MMA annotation tradition. NOT filtered by `_discriminating` (the semantic component IS the discriminating element within the phonetic family). Different from `meaning` (which uses memodevice types) and `family` (which uses structural confusable grouping). For 阁(gé): mma_semantic=门 (same as family); for 清(qīng): mma_semantic=氵 (differs from family=青). Complements `pinyin`: for a 形声字, pinyin gives the phonetic component and mma_semantic gives the semantic component.

- **Memodevice vs IDS divergence** (`memo_diff`) — components present in `memo_map` but ABSENT from `all_map` (the IDS recursive ancestry). These are the points where the memodevice structural tradition diverges from the IDS standard: for 明, memo_map={囧,月} but all_map={日,月}, so memo_diff={囧} — memodevice reanalyzes 日 as 囧 (a variant). These divergent components are often the more memorable or creative decomposition precisely because they represent non-obvious structural interpretation. With `_discriminating` filter.

- **Information gain** — for each character, rank components by information gain: which component, if known, most reduces uncertainty about which character this is within the confusable set? Decision-tree feature selection applied to character identity. Different from rarity-based salience — a common component shared by only 3 very confusable neighbours scores higher than a rare component shared with no confusable.

- **Positional stability** — a component that always appears in the same structural slot across all characters that contain it (木 is always left in ⿰木X) is more reliably memorable than one that drifts. Ordering by stability — most stable first — gives the learner the most consistent visual anchor first.

- **HSK anchor** — among a character's components, which are themselves HSK vocabulary? An HSK component is a "free" mnemonic anchor — the learner already has a word-level memory to attach it to. Filtering to HSK-level components (not just reordering) produces a different SET: only components the learner already knows as vocabulary. Coverage is intentionally lower — covers only chars whose discriminating component happens to be common vocabulary.

- **Semantic family absent** (`sem_absent`) — complement to `sem_sibling`: what components do radical siblings HAVE that this character LACKS? While `sem_sibling` gives what makes C unique within the radical family, `sem_absent` gives the phonetic diversity of the family that C doesn't participate in. For a 氵-family char like 清, `sem_absent` gives the phonetic components of 海, 河, 江, 涌... — the whole landscape of what other 氵-chars use instead of 青. Together `sem_sibling` + `sem_absent` give the complete structural picture within a radical family.

- **Phonetic scope** (`phonetic_scope`) — confusable set = all chars sharing the same tone-stripped syllable (initial+final, ignoring tone). Broader than `homophone` (exact tone) and different from `pinyin` (which finds the phonetic carrier component). For 清(qīng): scope group = all qing-syllable chars regardless of tone — 清1, 请3, 情2, 晴2, 庆4, 穷2... Within this group, what structural component distinguishes 清? Expected: between `homophone` (exact tone, tighter group) and something more general. Bridges between the phonetic confusable groupings.

- **Depth-2 ancestry components** — include components reachable at depth-2 through different intermediaries: 骑(马+奇) and 荷(艹+何) both reach 可 via different depth-1 children. Surfaces hidden structural kinship invisible to direct decomposition.

- **Visual-only components** — for characters like 己/已/巳 where IDS decomposition is identical, pixel-level rendering can identify the visual feature that varies (open vs. closed stroke end). Requires PIL + font file; uniquely covers single-stroke confusables that all other approaches miss.

- **Contrastive decomposition** — instead of a flat component list, express each component as an explicit contrast: `{vs: 睛, ours: 日, theirs: 目}`. Makes the decomposition directly actionable for card display and ties each component to a specific confusable. Requires changing the output format.
