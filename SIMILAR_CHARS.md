# Similar Characters — `data_similar.py`

## Purpose

Characters that share visual components are easy to confuse during recall. This module identifies those groups and, for each character, computes the positional component features that best identify it among all visually similar characters. Those features surface on the question side of an Anki card.

Running `data_similar.py` produces **five** output files:

| file | algorithm | format | use case |
|---|---|---|---|
| `data_similar_disc.json` | min hitting set, group-relative | grouped list | logically complete, all pairs covered |
| `data_similar_useful.json` | coverage × rarity IDF, group-relative | grouped list | single memorable anchor |
| `data_similar_pos.json` | min hitting set, IDS positional, group-relative | grouped list | tells WHERE (left/right/top/…) |
| `data_similar_global.json` | global fingerprint + joint identity, char-indexed | flat dict | **recommended for Anki** — group-free, globally consistent |
| `data_similar_hybrid.json` | global fingerprint using IDS positions + HanziDecomposer components | flat dict | experimental global index that can use both `R=皮` and `C=扌` style cues |

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
- pair (49%): exactly two features jointly needed
- subset (5%): character's features are a strict subset of some other character's — no positive discriminator
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
  "间": {
    "components": ["O=日", "T=门"],
    "identity":   "pair",
    "joint":      ["O=日", "T=门"],
    "similar":    ["问", "闻", "闪", "闭", "闹"],
    "contrasts":  [
      {"vs": "问", "slot": "O", "ours": "日", "theirs": "口"},
      {"vs": "闻", "slot": "O", "ours": "日", "theirs": "耳"},
      {"vs": "闪", "slot": "O", "ours": "日", "theirs": "人"}
    ]
  },
  "度": {
    "components": [],
    "identity":   "subset",
    "joint":      [],
    "similar":    ["府", "底", "座", "序", "庭"],
    "contrasts":  [],
    "ids_str":    "⿸广&CDP-8C46;"
  }
}
```

| field | meaning |
|---|---|
| `components` | pos-features from global discriminating set (use these for "look for…") |
| `identity` | `singleton` / `pair` / `triple` / `full` / `subset` |
| `joint` | the minimal unique conjunction — same features, different framing |
| `similar` | up to 8 most confusable chars (by Jaccard, sorted by similarity) |
| `contrasts` | contrastive slot pairs vs nearest neighbors: `[{vs, slot, ours, theirs}]` |
| `ids_str` | IDS string for subset chars |

`components` and `joint` contain the same features. `contrasts` is the qualitatively new field: for each near-neighbor, it names the **specific slot where they differ** — "间 has O=日, where 问 has O=口, 闻 has O=耳." This frames identification by direct contrast rather than as an abstract feature list.

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

---

## Approaches not yet implemented

### IDS tree edit distance

Distance = minimum component substitutions to transform one IDS tree into another. Characters at edit distance 1 (differ by exactly one component in one slot) are the most directly confusable. More principled than Jaccard for ranking similarity strength, but O(n²) to compute.

### Cross-radical abstraction in global index

The experiment (exp_novel.py) confirmed this finds ~50+ new confusion pairs. Integrating into `build_char_index` would require: normalize radical variants before computing pos-features, re-run the Jaccard similarity with abstract features, merge the new neighbors into `similar`. More complete confusion sets, better `contrasts`.

### Image-based pixel similarity

Render each character at 32×32 from a CJK font and compare pixel vectors. The only approach that catches purely visual similarity with no component overlap — characters like 己/已/巳 that are structurally nearly identical but have completely different IDS trees. Requires `Pillow` + a CJK font.

### Confusion network clustering

Build a pairwise Jaccard similarity graph over all characters. Run Louvain community detection to get non-overlapping clusters. Each character ends up in exactly one group. The current approach produces overlapping groups (a character can appear in many shared-component groups simultaneously); clustering forces a consistent single assignment.

---

## Tuning

| constant | default | effect |
|---|---|---|
| `MAX_COMP_FREQ` | 25 | upper bound on group size for disc/useful/pos modes |
| `MIN_GROUP` | 3 | minimum group size |
| `USEFUL_THRESHOLD` | 0.7 | useful mode: coverage required before adding a second component |
| threshold in `build_char_index` | 0.25 | global mode: minimum Jaccard to count as "confusable" |
