# Similar Characters — `data_similar.py`

## Purpose

Characters that share visual components are easy to confuse during recall. This module identifies those groups and, for each character, computes the positional component features that best identify it among all visually similar characters. Those features surface on the question side of an Anki card.

Running `data_similar.py` produces **eleven** output files:

| file | algorithm | format | use case |
|---|---|---|---|
| `data_similar_disc.json` | min hitting set, group-relative | grouped list | logically complete, all pairs covered |
| `data_similar_useful.json` | coverage × rarity IDF, group-relative | grouped list | single memorable anchor |
| `data_similar_pos.json` | min hitting set, IDS positional, group-relative | grouped list | tells WHERE (left/right/top/…) |
| `data_similar_global.json` | global fingerprint + joint identity, char-indexed | flat dict | **recommended for Anki** — group-free, globally consistent |
| `data_similar_hybrid.json` | global fingerprint using IDS positions + HanziDecomposer components | flat dict | experimental global index that can use both `R=皮` and `C=扌` style cues |
| `data_similar_pinyin.json` | IDS visual + MMA pinyin phonological cross-modal | flat dict | annotates visual confusions with phonological distance; surfaces "double danger" pairs |
| `data_similar_visual.json` | pixel-level HOG edge features, cosine similarity | flat dict | catches purely visual pairs IDS misses: 己/已, 乌/鸟, 干/千, 义/叉/又 |
| `data_similar_radical.json` | abstract radical clusters (氵/冫→DRIP, 扌/手→HAND, …) | flat dict | surfaces cross-radical confusions invisible to concrete IDS Jaccard |
| `data_similar_compound.json` | IDF-weighted Jaccard over rare compound word partners (HanziDictionary) | flat dict | contextual confusion pairs: chars interchangeable in the same compound slots |
| `data_similar_semantic.json` | shared English gloss grouping (memodevice `gloss` field) | flat dict | semantic synonym groups: different characters with the same meaning |
| `data_similar_subcomp.json` | position-agnostic IDF-Jaccard over direct IDS children | flat dict | cross-position component sharing: 削(肖刂) ↔ 梢(木肖), 案(安木) ↔ 按(扌安) |
| `data_similar_deepcomp.json` | IDF-Jaccard over depth-2+ complex components (complex = has IDS operator) | flat dict | hidden ancestry pairs: 骑(马+奇) ↔ 荷(艹+何) via shared 可; 喜/凳/禧 via shared 豆 |

---

## Approaches

### disc / useful — raw component sets, group-relative

For each character, the component set is the union of IDS dictionary components and HanziDecomposer level-2 decomposition. A shared component defines a group if it appears in 3–25 characters.

**disc** solves minimum hitting set within each group:
```
sep(C, C') = comps(C) − comps(C')
find smallest D ⊆ comps(C) such that D ∩ sep(C, C') ≠ ∅ for all C' in group
```

**useful** scores each component by `coverage × IDF-rarity`, returns top-1 (or top-2 if coverage < 0.7).

Both operate within one specific group — a character in multiple groups gets separate discriminators for each, and the smallest group is used for the Anki card.

### pos — IDS positional features, group-relative

Parse each character's IDS string into a tree and extract positional leaf features:
```
横  ⿰木黄  →  {L=木, R=黄}
府  ⿸广付  →  {TL=广, O=付}
间  ⿵门日  →  {T=门, O=日}
```

Groups form on shared `(slot=component)` features. Discrimination uses the same greedy hitting set, but now each feature says WHERE to look: `R=黄` means "look on the RIGHT side for 黄".

Limitation: only top-level IDS components — sub-stroke connections (艮 in both 朗 and 浪) are invisible to pos mode.

### global — global fingerprint + joint identity (recommended)

**Solves the two core weaknesses of the group-relative approaches:**

1. Group-relative approaches give different discriminators for the same character depending on which group is active. A character can be in five different groups and get five different hints. The global approach finds a single answer that works across all of them.

2. Group-relative pos mode gives the wrong answer for 间: it returns `T=门` (the shared feature that ALL 门-family chars have!) instead of `O=日`. The global approach correctly sees that `T=门` doesn't distinguish 间 from 问/闻/闲 and adds `O=日`.

**Algorithm (two layers):**

**Global fingerprint** (`components` field): find the minimum set of pos-features that separates `C` from every character `D` with Jaccard(`pos_feats(C)`, `pos_feats(D)`) ≥ 0.25. Uses similarity-weighted greedy hitting set — covering a high-Jaccard neighbour (most confusable) is prioritised over a low-Jaccard one.

**Joint identity** (`joint` / `identity` fields): find the smallest conjunction of pos-features that no other character in the dataset also has. If the conjunction `{f1, f2}` is unique to `C`, the statement "this character has BOTH `f1` AND `f2`" identifies it absolutely.

```
横  components=[R=黄]          identity=singleton  → R=黄 alone is globally unique
间  components=[O=日, T=门]    identity=pair       → neither O=日 nor T=门 alone; together they are
棒  components=[R=奉, L=木]   identity=pair
披  components=[R=皮, L=扌]   identity=pair       → needed because 波 also has R=皮
波  components=[R=皮, L=氵]   identity=pair       → same reason
```

**Dataset statistics (2998 characters):**
- singleton (44%): one pos-feature uniquely identifies the character
- pair (51%): exactly two features jointly needed
- stroke_count (2%): IDS features are a subset of another char's, but stroke count alone distinguishes
- subset (1%): no positive discriminator (IDS features AND stroke count ambiguous)
- full (2%): entire feature set needed (very complex characters)

**Output format** — flat dict keyed by character:
```json
{
  "横": {
    "components": ["R=黄"],
    "identity":   "singleton",
    "joint":      ["R=黄"],
    "similar":    ["林", "样", "机", "相", "权"],
    "contrasts":  [
      {"vs": "林", "slot": "R", "ours": "黄", "theirs": "木"},
      {"vs": "样", "slot": "R", "ours": "黄", "theirs": "羊"},
      {"vs": "机", "slot": "R", "ours": "黄", "theirs": "几"}
    ]
  },
  "清": {
    "components": ["R=青", "L=氵"],
    "identity":   "pair",
    "joint":      ["L=氵", "R=青"],
    "similar":    ["精", "靖", "睛", "猜", "晴", "情", "请", "倩"],
    "contrasts":  [
      {"vs": "精", "slot": "L", "ours": "氵", "theirs": "米"},
      {"vs": "靖", "slot": "L", "ours": "氵", "theirs": "立"},
      {"vs": "睛", "slot": "L", "ours": "氵", "theirs": "目"}
    ],
    "stroke_count": 11,
    "hsk_level": 6,
    "frequency_rank": 335,
    "definition": "clear",
    "etymology": {"type": "pictophonetic", "phonetic": "青", "semantic": "氵", "hint": "water"},
    "phonetic": "青",
    "phonetic_family": [
      {"char": "精", "semantic": "米", "hint": "grain"},
      {"char": "睛", "semantic": "目", "hint": "eye"},
      {"char": "晴", "semantic": "日", "hint": "sun"},
      {"char": "情", "semantic": "忄", "hint": "heart"},
      {"char": "请", "semantic": "讠", "hint": "speech"}
    ]
  },
  "常": {
    "components": ["B=巾", "T=𫩠"],
    "identity":   "pair",
    "joint":      ["B=巾", "T=𫩠"],
    "similar":    ["党", "掌", "堂", "赏", "棠"],
    "contrasts":  [
      {"vs": "党", "slot": "B", "ours": "巾", "theirs": "儿"},
      {"vs": "掌", "slot": "B", "ours": "巾", "theirs": "手"}
    ],
    "stroke_count": 11,
    "hsk_level": 1,
    "definition": "common",
    "etymology": {"type": "pictophonetic", "phonetic": "尚", "semantic": "巾", "hint": "cloth"},
    "phonetic": "尚",
    "phonetic_family": [
      {"char": "党", "semantic": "儿", "hint": "elder brother"},
      {"char": "掌", "semantic": "手", "hint": "hand"},
      {"char": "堂", "semantic": "土", "hint": "earth"}
    ]
  },
  "当": {
    "components": [],
    "identity":   "stroke_count",
    "joint":      [],
    "similar":    ["雪"],
    "contrasts":  [],
    "stroke_count": 6,
    "hsk_level": 2,
    "definition": "to match",
    "ids_str":    "⿱⺌彐"
  },
  "间": {
    "components": ["O=日", "T=门"],
    "identity":   "pair",
    "joint":      ["O=日", "T=门"],
    "similar":    ["问", "闷", "闭", "闪", "闻"],
    "contrasts":  [{"vs": "问", "slot": "O", "ours": "日", "theirs": "口"}],
    "stroke_count": 7,
    "hsk_level": 1,
    "definition": "space",
    "etymology": {"type": "ideographic", "story": "The sun 日 shining through a doorway 门"}
  },
  "度": {
    "components": [],
    "identity":   "subset",
    "joint":      [],
    "similar":    ["府", "底", "座", "序", "庭"],
    "contrasts":  [],
    "stroke_count": 9,
    "ids_str":    "⿸广&CDP-8C46;"
  }
}
```

| field | meaning |
|---|---|
| `components` | pos-features from global discriminating set, **salience-reranked** (most visually prominent first) |
| `identity` | `singleton` / `pair` / `triple` / `full` / `stroke_count` / `subset` |
| `joint` | the minimal unique conjunction — same features, different framing |
| `similar` | up to 8 most confusable chars (by Jaccard, sorted by similarity) |
| `contrasts` | contrastive slot pairs vs nearest neighbors: `[{vs, slot, ours, theirs}]` |
| `component_hints` | HD L2 breakdown of rare components in the discriminating set: `{"R=夌": ["八","土","夂"]}` |
| `stroke_count` | total stroke count (from `dictionary_char.jsonl`) — present for all 2998 chars |
| `hsk_level` | HSK level 1–7 if in HSK (from `dictionary_char.jsonl` statistics) |
| `frequency_rank` | corpus frequency rank (lower = more common; from `dictionary_char.jsonl`) |
| `definition` | short English gloss (from `dictionary_char.jsonl`) |
| `etymology` | for pictophonetic chars: `{type, phonetic, semantic, hint}` where `hint` is the English keyword for the semantic component ("water", "eye", …); for ideographic/pictographic chars: `{type, story}` where `story` is a visual composition description (from `dictionary_makemeahanzi.txt`) |
| `phonetic` | phonetic component from MMA etymology — covers ⿰, ⿱, ⿸, ⿺, etc. (broader than previous IDS-inferred) |
| `phonetic_family` | `[{char, semantic, hint}]` — all dataset chars sharing this phonetic, each annotated with their semantic component and English hint; the semantic hint is the discriminator within the family |
| `ids_str` | IDS string for subset/stroke_count chars |

**Salience reranking**: `components` are sorted by `salience(slot) × rarity(feature)`. For ⿰ chars, `R=` (60% visual area) always comes before `L=` (40%). For ⿱ chars, `B=` (55%) comes before `T=` (45%). 18.6% of two-feature chars are reordered vs. pure-rarity ordering — these are the chars where the rarest feature is not the most visually prominent one.

**Radical normalization** (`_RADICAL_NORM`): The IDS database uses variant radical forms (⻖, ⻏, ⺼, ⻌) that are distinct Unicode codepoints from their canonical equivalents (阝, 阝, 月, 辶). Previously these were silently filtered as noise, making any character using them a "subset" character with no discriminating feature. Now they are mapped to their canonical form before feature extraction. Result: 69 chars moved from `subset→pair` identity — characters like 院(⿰⻖完)→{L=阝, R=完}, 脸(⿰⺼佥)→{L=月, R=佥}, 这(⿺⻌文)→{BL=辶, O=文} now have proper discriminating features.

**Component hints** (`component_hints`): For rare components (appearing in ≤5 slot-positions globally), the HD level-2 sub-decomposition is stored as an annotation. 1703 chars have at least one hint. Intended for card display — when the discriminating component is obscure, show its sub-components as a visual memory aid: 棱 has `R=夌` with hint `["八","土","夂"]`; card shows "夌 (=土+八+夂) on the right".

**Phonetic family (MMA-sourced)**: ~80% of Chinese characters are 形声字 (semantic-phonetic compounds). 1403 chars have `phonetic` / `phonetic_family`, sourced from `dictionary_makemeahanzi.txt` etymology annotations. This covers all structure types (⿰, ⿱, ⿸, ⿺, …) rather than just ⿰. Previous IDS-inferred approach only covered 984 chars (⿰ only); MMA annotation covers 1403. The semantic hint within `phonetic_family` is the primary discriminator within a family: all 青-family chars look similar; the discriminating question is always "which semantic radical (水/日/心/言/目/米…) is present?". Card use: "phonetic 青: 清(water), 晴(sun), 情(heart), 请(speech), 睛(eye), 精(grain)".

`contrasts` frames identification by direct contrast: "清 has L=氵, where 精 has L=米, 靖 has L=立, 睛 has L=目."

**Etymology annotation**: 2787/2998 chars have `etymology` from MMA. For pictophonetic chars (1840), this gives `semantic` + `hint` (the English label for what the semantic radical represents) + `phonetic`. The `hint` enables a ready-made mnemonic: "water (氵) + 青 → 清 (clean)". For ideographic chars (812), `story` is a human-authored visual composition description: "The sun 日 shining through a doorway 门" (间). For pictographic chars (135), `story` describes the original pictogram. These are directly displayable as card scaffolds.

**Stroke count rescue**: 50 of the previous 82 "subset" chars (whose IDS feature set was a strict subset of some other char's) have a unique stroke count among their confusion neighbors — they are now classified as `stroke_count` identity. The remaining 32 true subset chars share both IDS features and stroke count with at least one neighbor. Card display for `stroke_count` chars: show stroke count as the distinguishing cue. All 2998 chars have `stroke_count` from `dictionary_char.jsonl`.

### pinyin cross-modal — visual + phonological overlap

`data_similar_pinyin.json` extends the global index with phonological data from `dictionary_makemeahanzi.txt`. For each character it parses the `pinyin` field into `(initial, final, tone)` triples and adds four new fields:

| field | meaning |
|---|---|
| `pinyin` | raw MMA pinyin list |
| `homophones` | other dataset chars with identical pronunciation (same initial + final + tone) |
| `near_homophones` | other dataset chars with same syllable (initial+final) but different tone |
| `double_danger` | chars that are BOTH visual (IDS Jaccard ≥ 0.25) AND phonologically similar (≥ 0.70) — the hardest learner pairs |

Phonological similarity scoring:

| condition | score |
|---|---|
| same initial + final + tone | 1.00 |
| same initial + final, different tone | 0.85 |
| same final (rhyme) only | 0.55 |
| same initial (onset) only | 0.25 |
| unrelated | 0.00 |

`double_danger` threshold: phonological score ≥ 0.70 (homophone or near-homophone) AND Jaccard ≥ 0.25 (visual similar).

**Dataset statistics (2998 chars):**
- 515 chars have at least one `double_danger` neighbor
- 2605 chars have at least one homophone in the dataset

**Notable double-danger pairs:**
```
清[qīng]  double_danger=晴情请   (homophone/near-homophone + visually similar)
胃[wèi]   double_danger=畏       (homophones: both wèi)
候[hòu]   double_danger=侯       (侯=hóu, near-homophone + visually similar)
```

### visual pixel — HOG edge features

`data_similar_visual.json` finds visually similar characters by rendering each character at 56×56 px using LXGWWenKai font and computing HOG-like edge density features:

1. Render character as 56×56 binary bitmap
2. Compute edge magnitude (Sobel-like: `√(|∂x|² + |∂y|²)`)
3. Divide into 7×7 grid cells (8px/cell) → 49-dimensional feature vector
4. L2-normalize the vector
5. Compute all-pairs cosine similarity via `feat_mat @ feat_mat.T`

New fields vs. the global index:

| field | meaning |
|---|---|
| `similar` | up to 8 most similar chars by edge-feature cosine similarity (threshold=0.97) |
| `visual_only` | subset of `similar` NOT found by IDS Jaccard ≥ 0.25 — genuinely novel pairs |
| `edge_sim` | `{char: cosine_similarity}` for each char in `similar` |

`visual_only` uses **uncapped** IDS Jaccard: a pair is excluded from `visual_only` only if IDS Jaccard ≥ 0.25 (regardless of whether it appears in the top-8 similar list). This prevents false positives from characters that share a common radical but happen to fall outside the top-8 display cap.

**Dataset statistics (2998 chars, threshold=0.97):**
- 611 chars have at least one `visual_only` neighbor (1277 total directed pairs)

**High-quality novel pairs found:**
```
己/已         (己 vs 已 — single middle stroke differs)
乌/鸟         (乌=鸟 missing a dot — classic single-stroke pair)
干/千         (一 vs 丿 at top — single stroke substitution)
义/叉/又      (classic tri-confusion set)
未/米/朱      (classic confusion cluster)
吏/史         (one stroke difference)
威/咸         (both contain 戊 structure with different enclosure)
胃/育/肾      (anatomical chars with similar proportions)
惠/恩         (similar structure, differ in bottom radical)
贸/贤         (both have 页 structure)
颖/颗         (near-identical phonetic-semantic compounds)
善/兽         (similar ink distribution at this resolution)
```

**Limitation:** HOG features capture spatial edge density, not specific stroke shapes. At 7×7 resolution, characters with the same structural template (⿰氵X) may still show moderate similarity even when their right components differ — but only those with IDS Jaccard < 0.25 reach `visual_only`.

### radical cluster — abstract radical similarity

`data_similar_radical.json` finds cross-radical confusion pairs invisible to concrete IDS Jaccard. It maps visually similar radical variants to shared abstract labels, then runs Jaccard over the abstract features.

**Cluster mappings:**
```
氵/冫  → DRIP    (3-dot water vs 2-dot ice)
扌/手  → HAND
忄/心  → HEART
讠/言  → SPEECH
纟/糸  → THREAD
钅/金  → METAL
艹/⺾  → GRASS
辶/彳  → WALK
刂/刀  → KNIFE
阝     → MOUND
```

Each concrete radical is replaced by its cluster label before computing Jaccard. A pair in `cluster_only` means: they are similar at the abstract level (share a cluster) but NOT at the concrete level (Jaccard < 0.25 with specific radicals), i.e., one has 氵 and the other has 冫 in the same slot with the same right component.

New field:

| field | meaning |
|---|---|
| `cluster_only` | chars found similar by cluster Jaccard but NOT by concrete IDS Jaccard |

**Dataset statistics (2998 chars):**
- 195 chars have at least one `cluster_only` neighbor

**Key cluster pairs found (DRIP: 氵 ↔ 冫):**
```
清[L=氵, R=青]  cluster_only=次决准况   (次/决/准/况 all have L=冫, different R)
冷[L=冫, R=令]  cluster_only=淫         (淫 has L=氵)
凉[L=冫, R=京]  cluster_only=淫
```

Note: 次/决/准/况 use **冫** (bīng, U+51AB, ice radical) while 清/浸/泳 use **氵** (sān shuǐ, U+6C35, water radical). They look nearly identical to learners but have IDS Jaccard = 0 (no shared features). The cluster index surfaces these as potential confusion pairs.

### position-agnostic direct-component — cross-position component sharing

`data_similar_subcomp.json` finds characters that share the same prominent component but in different structural positions. The IDS positional approach uses **(slot, component)** features, so it only finds similarity when the *same component* appears in the *same slot*:

```
削 = ⿰肖刂  {L=肖, R=刂}
梢 = ⿰木肖  {L=木, R=肖}
→ IDS positional Jaccard = 0  (L=肖 ≠ R=肖)

案 = ⿱安木  {T=安, B=木}
按 = ⿰扌安  {L=扌, R=安}
→ IDS positional Jaccard = 0  (T=安 ≠ R=安)
```

Both 削/梢 prominently contain 肖. Both 案/按 prominently contain 安. A learner who recognizes 肖 or 安 in one character will be confused by the other.

**Algorithm**: For each character, extract DIRECT IDS children as canonical strings (nested operator structures become their IDS string). Compute IDF over all characters' direct-child appearances — private-use components unique to one character get maximal IDF and naturally penalize sparse sets, preventing false positives. Compute position-agnostic IDF-Jaccard. Threshold = 0.35.

**Output fields per character:**

| field | meaning |
|---|---|
| `direct_components` | direct IDS children as canonical strings (first decomposition level only) |
| `subcomp_similar` | up to 8 chars with highest position-agnostic IDF-Jaccard (≥ 0.35) |
| `subcomp_only` | subcomp_similar chars NOT found by IDS positional Jaccard ≥ 0.25 |
| `subcomp_shared` | for top-4 subcomp_only pairs: the shared component(s) |

**Dataset statistics (2998 chars, threshold=0.35):**
- 2266 chars have at least one `subcomp_similar` neighbor
- 1738 chars have at least one `subcomp_only` neighbor

**Why IDF-weighted?** Common components like 口, 木, 氵 appear in 100–400 characters — sharing them provides little information. Rare components like 相(9 strokes, ~20 dataset chars), 朔(12 strokes, ~5 chars), 戌(6 strokes, ~12 chars) carry high signal. The IDF formula `log(n / (df+1))` naturally down-weights ubiquitous radicals.

**Why private-use chars in denominator?** Characters like 赛 = ⿱𡨄贝 have 𡨄 (private-use, df=1) as a direct child. If I filtered it out, 赛 and 赢 would both appear as `{贝}` only, giving IDF-Jaccard=1.0 even though they look nothing alike. Keeping 𡨄 in the denominator gives: `idf(贝) / (idf(𡨄) + idf(贝) + idf(𣎆)) = 3.9/18.5 = 0.21` — correctly below threshold.

**Notable new pairs found:**

```
削/梢/消/哨/俏/悄/销   all share 肖 — 削=⿰肖刂(肖 LEFT), others have 肖 RIGHT
案/按               both contain 安 — 案=⿱安木, 按=⿰扌安
含/吟/念/贪/琴        all share 今 — 含=⿱今口, 吟=⿰口今, 念=⿱今心, 贪=⿱今贝
想/湘/箱/厢/霜        all contain 相 — in ⿱T/B and ⿰L/R positions
哥/呵/河/柯/何/阿      哥=⿱可可(两个可), others are ⿰X可 — 可 is the shared element
辉/晃              辉=⿰光军, 晃=⿱日光 — both contain 光
辉/晕              辉=⿰光军, 晕=⿱日军 — both contain 军
威/咸              威=⿵戌女, 咸=⿴戌口 — both contain 戌 structure
塑/溯              塑=⿱朔土, 溯=⿰氵朔 — both contain 朔
```

**Relationship to phonetic families**: Many of these cross-position pairs represent the same PHONETIC component appearing as the non-standard (left or top) slot in atypical characters. In 削=⿰肖刂, 肖 is the phonetic on the LEFT and 刂 is the semantic knife radical on the right — reversed from the usual ⿰X肖 pattern. The position-agnostic index surfaces these "reversed phonetic" pairs that the MMA phonetic_family annotation also catches when present, but provides coverage for chars where the MMA has no etymology annotation.

### compound word context — IDF-weighted Jaccard over rare partners

`data_similar_compound.json` characterizes each character by which compound words it appears in. Two characters are contextually similar if they are interchangeable in the same compound slots — they appear before or after the same rare partner characters.

**Source**: `HanziDictionary().word_freq` from `hanzipy` (456K entries, ~242K two-character words).

**Algorithm**:

1. For each character `A` in 2-char words with freq ≥ 500: collect `left_partners[A]` (chars following A) and `right_partners[A]` (chars preceding A).
2. Compute document frequency (df): for each partner `p`, count how many dataset chars have `p` as a partner. High-df partners (e.g., 上, 理, 通) appear with hundreds of chars and are filtered out (df_max=20). Only RARE partners remain.
3. Rare-partner Jaccard with IDF weighting: `sum(idf(p) for p in shared) / sum(idf(p) for p in union)`, where `idf(p) = log(n / (df(p)+1))`. Threshold=0.15.
4. `compound_only` = compound-similar chars NOT found by IDS Jaccard ≥ 0.25 — genuinely novel contextual pairs.

**Output fields per character:**

| field | meaning |
|---|---|
| `left_compounds` | top 8 most frequent 2-char words where this char appears first (e.g., 早→早安/早餐/早上) |
| `right_compounds` | top 8 most frequent 2-char words where this char appears second (e.g., 晚→今晚/昨晚/明晚) |
| `compound_similar` | up to 8 chars with highest IDF-Jaccard over rare partners |
| `compound_only` | compound_similar chars NOT found by IDS Jaccard ≥ 0.25 |
| `shared_patterns` | for top-4 compound_similar chars: the shared rare left and right partners |

**Dataset statistics (2998 chars):**
- 1955 chars have at least one `compound_similar` neighbor
- 1934 chars have at least one `compound_only` neighbor (contextually confused but NOT visually similar)

**Notable compound pairs:**
```
早/晚       share left partners 安/餐 → 早安/晚安, 早餐/晚餐
他/她/它    share left partner 们 → 他们/她们/它们
做/作       share left partners 为/出/饭 → 做作/做出/做饭  vs  作为/作出
己/足/识    share right partner 知 (df=8) → 知己/知足/知识
清/漠       share right partner 冷 → 冷清/冷漠 (both describe emotional coldness)
已/曾       share right partner 经 → 已经/曾经
千/百/亿   share number-expression patterns
```

The compound index finds connections invisible to both visual and phonological methods. A learner who knows 知X exists may confuse 知己/知足/知识 — three different characters after 知.

### semantic synonyms — shared English gloss

`data_similar_semantic.json` groups characters by the single-word English gloss from `data_memodevice.json`. Characters sharing the same gloss are semantic synonyms — a learner who knows the meaning but not the form may write the wrong one.

**Algorithm**: group all 2998 characters by their `gloss` field. For each character, record all other chars in its group, then subtract the IDS-similar set (Jaccard ≥ 0.25) to get `semantic_only`.

**Output fields per character:**

| field | meaning |
|---|---|
| `gloss` | English meaning keyword (e.g., "clear", "already", "bright") |
| `gloss_group` | other dataset chars sharing this exact gloss |
| `semantic_only` | gloss_group chars NOT found by IDS Jaccard ≥ 0.25 — pure semantic confusion |

**Dataset statistics (2998 chars):**
- 2998 chars have a `gloss` entry (100% coverage)
- 956 chars have at least one `gloss_group` sibling
- 801 chars have at least one `semantic_only` neighbor (same meaning, not visually similar)
- 396 distinct glosses contain 2+ characters; largest groups:

```
bright (10): 慧 煌 炯 熙 亮 明 晃 昭 赫 耿
surname (14): 窦 冯 廖 黎 姜 赵 邓 谭 邵 邱 刘 蒋 蔡 潘
clear (5):   彰 晰 楚 清 浏
cover (5):   套 庇 盖 蒙 蔽
beautiful (5): 美 娟 丽 艳 倩
hide (5):    匿 隐 躲 藏 潜
```

**Notable semantic pairs:**
```
清/楚  both mean "clear" AND form the compound 清楚 — the two halves of one word share the same meaning
己/自  both mean "self" AND appear together in 自己 — the learner must know which character the meaning is mapped to
已/曾/既  all mean "already" — three distinct characters for the same adverb
晚/夜  both mean "night" — 晚上 vs 夜晚 are near-synonyms
冷/寒  both mean "cold"
净/洁  both mean "clean"
目/眼  both mean "eye" — 目 is classical/radical, 眼 is colloquial
```

The semantic index finds confusion that has nothing to do with visual or phonological similarity — pure conceptual confounds. Combined with `compound_only` (contextual pairs) and `visual_only` (pixel pairs), it provides a third orthogonal confusion dimension.

### deep component ancestry — depth-2+ complex subcomponents

`data_similar_deepcomp.json` extends the subcomp index one level deeper. Where subcomp finds chars sharing a **direct child**, deep component ancestry finds chars sharing a **grandchild** — a component that appears at depth-2 or deeper in both characters but through *different* depth-1 intermediaries.

```
subcomp finds:   骑(马+奇) and 寄(宀+奇) → share direct child 奇
deepcomp finds:  骑(马+奇) and 荷(艹+何) → share no direct child,
                   but 奇=⿱大可 and 何=⿰亻可 both contain 可 at depth-2

subcomp finds:   颤(亶+页) and 题(是+页) → share direct child 页
deepcomp finds:  颤(亶+页) and 堤(土+提?) → share no direct child,
                   but 亶 and 是/提 intermediaries both contain 旦 at depth-2
```

**Why "complex" filter?** Depth-2 recursively includes everything — but simple primitives like 一, 口, 日, 月 appear at depth-2 in hundreds of characters. Including them produces false positives (鸟/蒸 both contain 一 at depth-2 but look nothing alike). The **complex filter** keeps only depth-2+ components that are themselves composed (their IDS contains at least one IDS operator), which excludes atomic pictographs like 一/口/日/木 while retaining structured components like 可(⿵𠃍口), 旦(⿱日一), 豆(⿱⿱𠄠口一).

**Algorithm**:
1. For each character: compute `all_recursive_components` (from `ids['components']`) minus `direct_children` minus the character itself = depth-2+ components.
2. Filter to components that are (a) in the 2998-char dataset, (b) have an IDS string containing an IDS operator (are complex, not atomic).
3. Compute IDF over these filtered depth-2+ components across all characters.
4. Compute IDF-Jaccard. Threshold = 0.40.
5. `deep_only` = similar chars NOT already found by IDS positional Jaccard ≥ 0.25 AND not sharing any direct child (not in subcomp).

**Output fields per character:**

| field | meaning |
|---|---|
| `deep_components` | depth-2+ complex components in dataset (the "hidden ancestors") |
| `deep_similar` | up to 8 chars with highest deep IDF-Jaccard (≥ 0.40) |
| `deep_only` | deep_similar chars NOT found by IDS Jaccard ≥ 0.25 and not sharing a direct child |
| `deep_shared` | for top-4 deep_only pairs: which deep component is shared |

**Dataset statistics (2998 chars, threshold=0.40):**
- 194 chars have non-empty `deep_components` (depth-2+ complex components)
- 160 chars have at least one `deep_similar` neighbor
- 119 chars have at least one `deep_only` neighbor

**Notable groups found:**

```
可-family (df=8):  骑/荷/歌/啊/寄/崎/椅/倚 — all contain 可 at depth-2
  骑=马+奇(大+可),  荷=艹+何(亻+可),  歌=哥(可+可)+欠,
  啊=口+阿(阝+可),  寄=宀+奇,  崎=山+奇

旦-family (df=10): 颤/题/匙/恒/堤/垣/宣/桓/提/擅 — all contain 旦 at depth-2
  颤=亶+页(旦 in 亶),  堤=土+提(旦 via 是),  宣=宀+亘(旦 in 亘)

豆-family (df=10): 喜/凳/禧/嘉/彭/瞪/膨/鼓 — all contain 豆 at depth-2
  喜=壴+口(豆 in 壴),  凳=登+几(豆 in 登),  嘉=壴+加

品-family (df=7):  躁/癌/藻/燥/噪/澡/操 — all contain 品 at depth-2 via 喿(⿱品木)
```

**Relationship to subcomp**: Deep component pairs have no direct-child overlap, so they represent a strictly deeper structural connection. The 可-family example illustrates three separate depth-1 intermediaries (奇, 何, 哥, 阿) that all decompose to 可 — a structural "hidden ancestor" that subcomp cannot reach because subcomp only compares depth-1.

This dimension is useful for mnemonics: a learner who knows that 奇, 何, 哥, and 阿 all contain 可 can link the seemingly unrelated characters 骑/荷/歌/啊 through that shared building block.

### hybrid — IDS positions + HanziDecomposer components

`data_similar_hybrid.json` keeps the same flat, char-indexed shape as `data_similar_global.json`, but expands each character's feature set:

```
IDS positional leaves:        R=皮, L=扌, O=日
HanziDecomposer components:   C=皮, C=扌, C=门
```

Neighbor search uses the strongest of IDS-position Jaccard and HanziDecomposer-component Jaccard, so characters can become neighbors even when one representation misses the visual relationship. The discriminating set is then selected from the union of both feature views. Positional features are preferred when they cover the same threats, but `C=...` features are allowed when HanziDecomposer gives a better global cue.

The hybrid output adds `component_contrasts` beside the existing slot `contrasts`:

```json
{
  "披": {
    "components": ["R=皮", "L=扌"],
    "identity": "pair",
    "joint": ["C=扌", "C=皮"],
    "similar": ["摇", "疲", "彼", "被", "破"],
    "contrasts": [
      {"vs": "彼", "slot": "L", "ours": "扌", "theirs": "彳"},
      {"vs": "被", "slot": "L", "ours": "扌", "theirs": "衤"},
      {"vs": "破", "slot": "L", "ours": "扌", "theirs": "石"}
    ],
    "component_contrasts": [
      {"vs": "摇", "ours": "皮", "theirs": "缶"},
      {"vs": "疲", "ours": "扌", "theirs": "疒"},
      {"vs": "坡", "ours": "扌", "theirs": "土"}
    ]
  }
}
```

This method is experimental because component-only similarity can also over-connect broad families. It is most useful for checking whether the IDS-only global index missed a helpful decomposer cue.

Hybrid `identity` can also be `empty` when both IDS positional leaves and HanziDecomposer level-2 components are empty after noise filtering.

---

## Mode comparison

### 页-family (all have 页 on right)

```
  char   IDS       disc    useful  pos      global
  ────   ───────   ──────  ──────  ───────  ────────────────────────
  颤     ⿰亶页    亶       亶       L=亶     R=页  L=亶   (pair)
  颜     ⿰彦页    彦       彦       L=彦     R=页  L=彦   (pair)
  顽     ⿰元页    元       元       L=元     L=元          (singleton, R=页 not unique)
```

Global mode shows that for some chars `R=页` is needed (not unique in the dataset without it), while for others the left component alone is globally sufficient.

### 门-family (all have 门 as enclosure)

```
  char   disc    useful  pos     global
  ────   ──────  ──────  ──────  ────────────────────
  间     日       日      T=门    [O=日, T=门]  (pair — O=日 alone not unique globally)
  问     口       口      T=门    [O=口, T=门]  (pair)
  闲     木       木      T=门    [O=木, T=门]  (pair)
```

pos mode gives `T=门` (wrong — the shared feature!); global correctly gives `[O=日, T=门]`.

---

## Integration into `anki_memodevice.py`

The global index is the recommended source. It has no groups — just look up the character.

### Load at module level

```python
with open("data_similar_global.json", "r", encoding="utf-8") as f:
    similar_index = json.load(f)
```

### Render helper

```python
SLOT_NAMES = {"L": "left", "R": "right", "T": "top", "B": "bottom",
              "O": "inner", "I": "inner", "TL": "upper-left", "BL": "lower-left",
              "TR": "upper-right", "M": "middle", "A": "A", "B": "B"}

def _render_comp(comp, slot=None):
    label = SLOT_NAMES.get((slot or "").split(".")[-1], slot) if slot else None
    s = f'<strong>{comp}</strong>'
    if label: s += f'<span style="font-size:11px;color:#bbb;"> ({label})</span>'
    return s

def _render_feat(feat):
    if "=" in feat:
        slot, comp = feat.split("=", 1)
        return _render_comp(comp, slot)
    return f'<strong>{feat}</strong>'

def build_similar_html(char, similar_index):
    if char not in similar_index: return ""
    entry = similar_index[char]
    sim = entry.get("similar", [])
    if not sim: return ""

    chars_html = "  ".join(
        f'<strong style="color:#333;">{c}</strong>' if c == char
        else f'<span style="color:#aaa;">{c}</span>'
        for c in [char] + [c for c in sim if c != char][:7]
    )

    comps = entry.get("components", [])
    contrasts = entry.get("contrasts", [])
    ids_str = entry.get("ids_str", "")
    identity = entry.get("identity", "")

    if comps:
        rendered = "  ".join(_render_feat(f) for f in comps)
        if identity == "singleton":
            label = "Only this char has"
        elif identity == "pair":
            label = "Unique combination"
        else:
            label = "Look for"
        detail = rendered
        # Append contrastive hints: "not 口 (问), not 耳 (闻)"
        if contrasts:
            not_parts = [f'{ct["theirs"]} <span style="font-size:11px;color:#ccc;">({ct["vs"]})</span>'
                         for ct in contrasts[:3]]
            detail += f'<span style="color:#ccc;font-size:12px;">  — not {", ".join(not_parts)}</span>'
    elif ids_str:
        label = "Structure"
        detail = f'<span style="font-family:monospace;">{ids_str}</span>'
    else:
        return ""

    html  = '<div style="margin-top:8px;text-align:center;font-size:20px;line-height:1.6;">'
    html += f'<span style="color:#999;font-size:13px;">similar: </span>{chars_html}'
    html += '</div>'
    html += f'<div style="text-align:center;font-size:14px;color:#999;margin-bottom:4px;">{label}: {detail}</div>'
    return html
```

### Card question result

```
                    横
             (horizontal)

  similar:  横  林  样  机  相  权
            Only this char has: 黄 (right)  — not 木 (林), not 羊 (样), not 几 (机)

                    间
              (between)

  similar:  间  问  闻  闪  闭  闹
            Unique combination: 日 (inner)  门 (top)  — not 口 (问), not 耳 (闻), not 人 (闪)

                    颤
              (tremble)

  similar:  颤  颜  顽  顾  烦
            Only this char has: 亶 (left)  — not 彦 (颜), not 元 (顽), not 厄 (顾)
```

### Insert into `build_standard_note`

```python
question_html = char_display
question_html += build_similar_html(char, similar_index)
```

---

## Experimental findings (exp_novel.py)

Five novel approaches were tested on the full 2998-char dataset:

### Contrastive Slot Description — **implemented in global index**
For each similar neighbor D, find the slot where C and D differ: C has `slot=X`, D has `slot=Y`. Expressed as "not Y (D)". This is the most psychologically effective framing because memory encodes by contrast (von Restorff effect). Now stored as the `contrasts` field.

### Elimination Power Ordering
For each feature of C, count how many characters it globally eliminates (don't have it). `elimination_power(f) = total_chars − freq(f)`. Result: for 99%+ of characters, a single feature eliminates ≥99.9% of all other chars. Confirms that the greedy global fingerprint already picks features in the right order. No separate field needed.

### Decision Tree Path
Build a binary decision tree over each char's confusion cluster using information gain as splitting criterion. Each char's path from root to leaf is its identification sequence. Key finding: the DT optimizes average depth across the whole cluster, not per-char. For chars with a globally unique feature (L=亶 for 颤), the DT may still give an 8-step path because the tree processes other cluster members first. EP ordering is better for per-char identification; DT is a hardness diagnostic.

**Confusion hardness per char (DT path length at threshold=0.25):**
- 1 step: 超, 氛 (trivially unique within cluster)
- 2 steps: 泼, 营, 棒, 剑, 憾, 撕, 效, 拔
- 3 steps: 横, 棱
- 5–8 steps: 波, 颤, 遭, 懈, 掘, 椎, 披 (complex clusters)

### Confusion Network Analysis
The full Jaccard similarity graph (threshold=0.25) over 2998 chars has **62,421 edges**. The hardest characters (highest degree) are all ⿰扌X and ⿰氵X chars:
- 推: 162 neighbors, 折/投/抄/抱/拍: ~156 each
- 懿, 黄: degree 0 — completely unique, no confusion neighbors

Finding: the entire 扌-family (~150 chars) forms a near-complete confusion clique. The only discriminating feature within this clique is always the right component.

### Radical Family Abstraction
Normalize radical variants: 扌/手/𠂇→HAND, 氵/水→WATER, etc. Running Jaccard over abstract features finds **new confusion pairs** missed by concrete features (8 new pairs in 500 chars, ~50+ over the full dataset):
- 掌~弊: both HAND-radical but different specific forms
- 削~初: both KNIFE (刂 vs 刀) but not concrete-Jaccard neighbors
- 准~鹤: both BIRD (隹) in different positions

Not yet integrated into the global index — would require a second pass over the confusion set computation.

### Phonetic series (声旁) — **implemented in global index**
For simple ⿰(L)(R) characters, R is the phonetic component (声旁) that gives approximate pronunciation; L is the semantic radical. 186 phonetic families exist in the dataset, all with avg intra-family Jaccard = 0.333 (all family members are each other's confusion neighbors). 903 chars now have `phonetic` and `phonetic_siblings` fields. 535 phonetic-family pairs were NOT in each other's global similar list (despite Jaccard ≥ 0.25) because the cap of 8 is exceeded in large families like 扌 (148 chars) — the `phonetic_siblings` field gives the full family, bypassing the cap.

### Salience-reranked fingerprint — **implemented in global index**
Features are now sorted by `salience(slot) × rarity(feature)` instead of pure rarity. Visual salience approximates the fraction of the character's area occupied by each slot (R=60%, L=40%, B=55%, T=45% for ⿰/⿱). 272/1460 two-feature chars (18.6%) have their ordering changed. Effect: for ⿰ chars the phonetic/right component is listed first; for ⿱ chars the bottom component leads. Cards show the most visually prominent discriminator first.

### Radical normalization (⻖/⻏/⺼/⻌) — **implemented in _pos_leaves**
Root cause of 151 "subset" chars: the IDS database uses variant radical forms (⻖, ⻏, ⺼, ⻌) that don't match canonical forms (阝, 阝, 月, 辶). Previously treated as noise and silently dropped, causing any ⻖/⺼/⻌-radical character to appear as a subset. Now mapped to canonical form via `_RADICAL_NORM` before the noise check. 69 chars rescued from subset identity.

### MMA etymology annotation — **implemented in global index**
`dictionary_makemeahanzi.txt` provides expert-annotated etymology for 2787/2998 chars:
- **Pictophonetic** (1840 chars): explicit `phonetic` + `semantic` + English `hint`. More accurate than IDS inference (IDS-inferred ⿰ phonetic was wrong in 143/774 cases where the LEFT component is the phonetic). Covers all structure types, not just ⿰.
- **Ideographic** (812 chars): `story` gives a visual composition mnemonic (e.g., "A person 儿 carrying a torch 火" for 光).
- **Pictographic** (135 chars): `story` describes the original pictogram.

Phonetic family experiment: MMA-sourced families = 385 (vs 198 IDS-inferred), covering 1403 chars (vs 984). New families include ⿱-structure chars like 常/党/掌/堂/赏 (all phonetic=尚) and many ⿸/⿺ chars. For all confused pairs within a phonetic family, the semantic component (`semantic` + `hint`) is the correct discriminator.

MMA features (SEM=/PHO=) tested in Jaccard computation: adding role-typed features REDUCES Jaccard scores (more features dilute the overlap ratio). Not suitable for similarity computation. Best used as direct annotation fields.

### Stroke count rescue + metadata — **implemented in global index**
`dictionary_char.jsonl` provides per-character: `strokeCount`, `statistics.hskLevel`, `statistics.bookCharRank`, `gloss`.

Stroke count rescue: for the 82 subset chars (no IDS discriminating feature), 50 have unique stroke counts among their similar neighbors → identity upgraded from `subset` → `stroke_count`. Only 32 true subsets remain. Stroke count delta distribution for all confused pairs: 12.4% same count (delta=0), 22.5% delta=1, 19.0% delta=2 — most confused chars DO differ in stroke count, but delta=1 is barely noticeable; delta≥3 is a reliable visual cue.

HSK level and frequency rank enable confusion prioritization: HSK-1 chars with high-Jaccard neighbors are the most important to fix. Not yet integrated into the `similar` ordering.

### Positional HD-L2 (PHD2) — **component_hints implemented in global index**
For the top-level IDS slot of each char, run HD level-2 decomposition on that slot's component to get positioned sub-features (`R⊃土`, `R⊃八`). Key finding: only 11 new confusion pairs found at threshold 0.25 in a 9800-pair sample — PHD2 doesn't substantially expand the confusion set. But it IS useful as a component annotation: chars with obscure IDS components (appearing ≤5 times) now store the HD L2 breakdown in `component_hints`. 1703 chars have at least one hint. Card display use: `棱` shows "夌(=土+八+夂) on the right."

### Cross-level IDS/HD agreement
Mean Jaccard between IDS components and HD L2 components: 0.424. Low-agreement chars (j≈0): simple chars where IDS uses private-use sub-components but HD L2 sees canonical atoms (个, 介, 仓, 余). High-agreement chars (j=1.000): clean ⿰/⿱ structures where both methods agree exactly (饮, 鸡, 魄, 鲁). Agreement score is a proxy for structural clarity — unambiguous characters have high agreement.

### Structural template (IDS skeleton)
Replace IDS leaf components with abstract type labels. Characters sharing the same operator-sequence template share the same visual skeleton. 73 distinct templates; the enclosure operators (⿵, ⿷) have the highest intra-template Jaccard (0.21–0.24) and are already found by Jaccard similarity. For ⿰(X,X) (1534 chars), template is too coarse — most pairs share no components. Most useful as a human-readable shape descriptor, not as a new similarity detector.

---

## Approaches not yet implemented

### IDS tree edit distance

Distance = minimum component substitutions to transform one IDS tree into another. Characters at edit distance 1 (differ by exactly one component in one slot) are the most directly confusable. More principled than Jaccard for ranking similarity strength, but O(n²) to compute.

### Confusion network clustering

Build a pairwise Jaccard similarity graph over all characters. Run Louvain community detection to get non-overlapping clusters. Each character ends up in exactly one group. The current approach produces overlapping groups (a character can appear in many shared-component groups simultaneously); clustering forces a consistent single assignment.

### Integration of new fields into `anki_memodevice.py`

Six new indexes (`pinyin`, `visual`, `radical`, `subcomp`, `compound`, `semantic`) are not yet used in card generation. Planned additions:
- `double_danger` — flag on the card face when a char is both visually and phonologically similar to another
- `visual_only` — supplement `similar` display for chars like 己/已 that IDS misses
- `cluster_only` — annotation for 氵/冫 cross-radical pairs ("⚠ also confusable with 次/决 which use 冫 instead of 氵")
- `subcomp_only` — cross-position component sharing (削/梢 both have 肖, 案/按 both have 安)
- `compound_only` / `left_compounds` / `right_compounds` — contextual usage examples + cross-char usage warnings
- `semantic_only` — note when two chars share a meaning ("清 and 楚 both mean 'clear' — note the compound 清楚")

---

## Tuning

| constant | default | effect |
|---|---|---|
| `MAX_COMP_FREQ` | 25 | upper bound on group size for disc/useful/pos modes |
| `MIN_GROUP` | 3 | minimum group size |
| `USEFUL_THRESHOLD` | 0.7 | useful mode: coverage required before adding a second component |
| threshold in `build_char_index` | 0.25 | global mode: minimum Jaccard to count as "confusable" |
