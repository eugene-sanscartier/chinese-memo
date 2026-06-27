import json
import os
from collections import defaultdict
from itertools import combinations
from hanzipy.decomposer import HanziDecomposer

decomposer = HanziDecomposer()

NOISE = set('一丨丶丿乙亅㇆㇉㇠㇇㇒㇗㇈㇏㇖㇗𠂇𠂉⺁⺙⺮⺈⺌⻊⺊⺹⻎') | {'No glyph available'}
# Radical variant → canonical form.  Applied before NOISE check in _pos_leaves so that
# IDS trees using variant radicals (⻖=left-ear, ⻏=right-ear, ⺼=meat, ⻌=walk) produce
# the same positional features as trees written with the canonical form.
# Without this, 院(⿰⻖完) → {R=完} only (⻖ filtered), making it a "subset" of any
# char that also has R=完.  With it: 院 → {L=阝, R=完}, correctly discriminated.
_RADICAL_NORM = {'⻖': '阝', '⻏': '阝', '⺼': '月', '⻌': '辶'}

# IDS operator arity and positional slot names
_IDS_OPS = {'⿰':2,'⿱':2,'⿲':3,'⿳':3,'⿴':2,'⿵':2,'⿶':2,'⿷':2,'⿸':2,'⿹':2,'⿺':2,'⿻':2}
_SLOTS   = {'⿰':['L','R'],'⿱':['T','B'],'⿲':['L','M','R'],'⿳':['T','M','B'],
            '⿴':['O','I'],'⿵':['T','O'],'⿶':['B','O'],'⿷':['R','O'],
            '⿸':['TL','O'],'⿹':['TR','O'],'⿺':['BL','O'],'⿻':['A','B']}
# Approximate visual area fraction each slot occupies within its operator.
# Used to rank discriminating features by perceptual salience.
_SLOT_SALIENCE = {
    '⿰': {'L': 0.40, 'R': 0.60}, '⿱': {'T': 0.45, 'B': 0.55},
    '⿲': {'L': 0.30, 'M': 0.35, 'R': 0.35}, '⿳': {'T': 0.30, 'M': 0.35, 'B': 0.35},
    '⿴': {'O': 0.65, 'I': 0.35}, '⿵': {'T': 0.60, 'O': 0.40},
    '⿶': {'B': 0.60, 'O': 0.40}, '⿷': {'R': 0.60, 'O': 0.40},
    '⿸': {'TL': 0.55, 'O': 0.45}, '⿹': {'TR': 0.55, 'O': 0.45},
    '⿺': {'BL': 0.55, 'O': 0.45}, '⿻': {'A': 0.50, 'B': 0.50},
}


def _parse_ids(s):
    def go(pos):
        if pos >= len(s): return None, pos
        ch = s[pos]
        if ch == '&':
            end = s.find(';', pos)
            tok = s[pos:end + 1] if end != -1 else ch
            return tok, (end + 1 if end != -1 else pos + 1)
        if ch in _IDS_OPS:
            n = _IDS_OPS[ch]; children = []; p = pos + 1
            for _ in range(n):
                child, p = go(p)
                children.append(child)
            return (ch, children), p
        return ch, pos + 1
    if not s: return None
    tree, _ = go(0)
    return tree


def _valid_comp(c):
    if len(c) != 1: return True  # entity references like &CDP-8CCE; are valid
    o = ord(c)
    return (o >= 0x2E80 and not (0xE000 <= o <= 0xF8FF or 0xF0000 <= o <= 0x10FFFF))


def _pos_leaves(tree, path=''):
    """Recursively extract 'pos=component' strings from IDS tree leaves (no operators)."""
    if tree is None: return set()
    if isinstance(tree, str):
        comp = _RADICAL_NORM.get(tree, tree)
        if comp in NOISE or not _valid_comp(comp): return set()
        return {f'{path}={comp}' if path else comp}
    op, children = tree
    names = _SLOTS.get(op, [str(i) for i in range(len(children))])
    feats = set()
    for i, child in enumerate(children):
        slot = names[i] if i < len(names) else str(i)
        feats |= _pos_leaves(child, f'{path}.{slot}' if path else slot)
    return feats


def get_pos_feats(char, ids_dict):
    """Return set of positional feature strings like 'L=木', 'R=黄', 'BL=辶'."""
    tree = _parse_ids(ids_dict.get(char, {}).get('ids', ''))
    return _pos_leaves(tree) if tree else set()


def _jaccard(a, b):
    if not a and not b: return 0.0
    return len(a & b) / len(a | b)


# ── global fingerprint & joint identity (char-indexed, group-free) ───────────

def global_fingerprint(char, pos_map, all_chars, threshold=0.25):
    """Minimum pos-features separating char from every char with Jaccard >= threshold.
    Uses similarity-weighted greedy: covering a high-Jaccard neighbour is prioritised."""
    C = pos_map[char]
    if not C: return [], [], 'empty'

    threats = sorted(
        [(D, _jaccard(C, pos_map[D])) for D in all_chars
         if D != char and _jaccard(C, pos_map[D]) >= threshold],
        key=lambda x: -x[1]
    )
    if not threats:
        return [min(C, key=lambda f: sum(1 for D in all_chars if f in pos_map[D]))], [], 'unique'

    threat_chars = [D for D, _ in threats]
    jw = {D: j for D, j in threats}
    seps = [C - pos_map[D] for D in threat_chars]
    subset_of = [threat_chars[i] for i, s in enumerate(seps) if not s]
    nonempty = [(threat_chars[i], s) for i, s in enumerate(seps) if s]

    if not nonempty:
        return [], subset_of, 'subset'

    remaining = list(nonempty)
    chosen = []
    while remaining:
        candidates = set().union(*(s for _, s in remaining))
        best = max(candidates, key=lambda f: sum(jw[D] for D, s in remaining if f in s))
        chosen += [best]
        remaining = [(D, s) for D, s in remaining if best not in s]

    similar_top = [D for D, _ in threats[:8]]
    return chosen, similar_top, 'discriminating'


def joint_identity(char, pos_map, all_chars):
    """Smallest conjunction of pos-features that no other char in the dataset also has.
    Returns (features, identity_type) where identity_type is 'singleton', 'pair',
    'triple', or 'full' (entire pos-feature set needed)."""
    C = pos_map[char]
    feat_list = sorted(C)

    def no_other_has_all(feats):
        return not any(D != char and all(f in pos_map[D] for f in feats) for D in all_chars)

    feat_freq = {f: sum(1 for D in all_chars if f in pos_map[D]) for f in feat_list}

    for f in sorted(feat_list, key=lambda f: feat_freq[f]):
        if no_other_has_all([f]):
            return [f], 'singleton'

    best_pair = min(
        ((sum(1 for D in all_chars if fi in pos_map[D] and fj in pos_map[D]), [fi, fj])
         for fi, fj in combinations(feat_list, 2) if no_other_has_all([fi, fj])),
        default=(None, None)
    )
    if best_pair[1] is not None:
        return best_pair[1], 'pair'

    for triple in combinations(feat_list, 3):
        if no_other_has_all(list(triple)):
            return list(triple), 'triple'

    return feat_list, 'full'


def _slot_contrasts(char, similar_chars, pos_map, feat_freq):
    """For each of char's similar neighbors, find same-slot different-component contrasts.
    Returns list of {'vs': D, 'slot': s, 'ours': comp_C, 'theirs': comp_D},
    one best contrast per neighbor, up to 4 neighbors total.
    Prefers top-level slots (no dots) and rarer C-components."""
    C = pos_map[char]

    def slot_comp(feat):
        if '=' not in feat: return None, None
        slot, comp = feat.split('=', 1)
        return slot.split('.')[0], comp

    c_by_slot = defaultdict(set)
    for f in C:
        s, comp = slot_comp(f)
        if s: c_by_slot[s].add(comp)

    result = []
    for D in similar_chars:
        P = pos_map.get(D, set())
        if not P: continue
        d_by_slot = defaultdict(set)
        for f in P:
            s, comp = slot_comp(f)
            if s: d_by_slot[s].add(comp)
        slot_diffs = []
        for s in c_by_slot:
            if s not in d_by_slot: continue
            diff_c = c_by_slot[s] - d_by_slot[s]
            diff_d = d_by_slot[s] - c_by_slot[s]
            if diff_c and diff_d:
                best_c = min(diff_c, key=lambda comp: feat_freq.get(f'{s}={comp}', 0))
                best_d = min(diff_d, key=lambda comp: feat_freq.get(f'{s}={comp}', 0))
                slot_diffs.append((len(s), feat_freq.get(f'{s}={best_c}', 0), s, best_c, best_d))
        if slot_diffs:
            slot_diffs.sort()
            _, _, s, best_c, best_d = slot_diffs[0]
            result.append({'vs': D, 'slot': s, 'ours': best_c, 'theirs': best_d})
    return result[:4]


def _hd2_subcomps(comp):
    """Return sorted list of HD level-2 sub-components of comp (excluding comp itself and NOISE)."""
    try:
        r = decomposer.decompose(comp, 2)
        if r is None: return []
        return sorted(c for c in r.get('components', []) if c and c != comp and c not in NOISE and _valid_comp(c))
    except Exception:
        return []


def _feat_salience_score(feat, feat_freq, n_chars):
    """salience(slot) × rarity(feat) — used to sort fingerprint features for card display.
    Salience approximates visual area fraction; rarity = 1 - freq/n. Depth-nested slots
    are discounted by 0.7 per nesting level."""
    if '=' not in feat: return 0.5
    slot_path = feat.split('=')[0]
    top_slot = slot_path.split('.')[0]
    sal = 0.5
    for _, slot_map in _SLOT_SALIENCE.items():
        if top_slot in slot_map:
            sal = slot_map[top_slot]; break
    sal *= 0.7 ** slot_path.count('.')
    return sal * (1.0 - feat_freq.get(feat, 0) / n_chars)


def _build_phonetic_families_mma(characters, mma_dict):
    """Build phonetic families from MMA etymology annotation (covers ⿰, ⿱, ⿸, etc.).
    Returns dict: char → (phonetic, semantic, sem_hint, [{char, semantic, hint}...]) for all
    chars with ≥1 sibling sharing the same phonetic in the dataset."""
    ch_ph, ch_sem, ch_hint = {}, {}, {}
    for char in characters:
        e = (mma_dict.get(char, {}).get('etymology') or {})
        if e.get('type') != 'pictophonetic': continue
        ph = e.get('phonetic'); sem = e.get('semantic'); hint = e.get('hint')
        if ph: ph = _RADICAL_NORM.get(ph, ph)
        if sem: sem = _RADICAL_NORM.get(sem, sem)
        if ph: ch_ph[char] = ph
        if sem: ch_sem[char] = sem
        if hint: ch_hint[char] = hint
    ph_to_chars = defaultdict(list)
    for char, ph in ch_ph.items():
        ph_to_chars[ph] += [char]
    result = {}
    for char, ph in ch_ph.items():
        siblings = [d for d in ph_to_chars[ph] if d != char]
        if siblings:
            family = [{'char': d, 'semantic': ch_sem.get(d, '?'), 'hint': ch_hint.get(d, '?')} for d in siblings]
            result[char] = (ph, ch_sem.get(char), ch_hint.get(char), family)
    return result


def build_char_index(characters, ids_dict, mma_dict=None, char_dict=None, threshold=0.25):
    """Build global fingerprint, joint identity, and contrastive pairs for every character.
    Returns a dict keyed by character:
      components        — pos-features from global discriminating set, salience-reranked
      identity          — singleton / pair / triple / full / subset / stroke_count
      joint             — pos-features forming the minimal unique conjunction
      similar           — up to 8 most similar chars (Jaccard >= threshold)
      contrasts         — slot contrasts vs nearest lookalikes: [{vs, slot, ours, theirs}]
      component_hints   — HD L2 breakdown for each rare component: {'R=夌': ['八','土','夂']}
      stroke_count      — total stroke count (from char_dict)
      hsk_level         — HSK level 1-7 if in HSK (from char_dict statistics)
      frequency_rank    — corpus frequency rank (from char_dict statistics)
      definition        — short English gloss (from char_dict)
      etymology         — {type, phonetic, semantic, hint} for pictophonetic chars, or
                          {type, story} for ideographic/pictographic chars (from mma_dict)
      phonetic          — phonetic component from MMA etymology (broader than IDS-inferred)
      phonetic_family   — [{char, semantic, hint}] for all dataset chars sharing this phonetic
      ids_str           — IDS string for subset characters
    """
    pos_map = {c: get_pos_feats(c, ids_dict) for c in characters}
    feat_freq = defaultdict(int)
    for feats in pos_map.values():
        for f in feats:
            feat_freq[f] += 1
    n = len(characters)
    phonetic_families = _build_phonetic_families_mma(characters, mma_dict) if mma_dict else {}
    result = {}
    for char in characters:
        gf, similar, gf_type = global_fingerprint(char, pos_map, characters, threshold)
        ji, ji_type = joint_identity(char, pos_map, characters)
        contrasts = _slot_contrasts(char, similar, pos_map, feat_freq)
        gf_sorted = sorted(gf, key=lambda f: _feat_salience_score(f, feat_freq, n), reverse=True)
        hints = {}
        for feat in gf_sorted:
            if '=' not in feat: continue
            comp = feat.split('=', 1)[1]
            comp_count = sum(1 for f2 in feat_freq if f2.endswith(f'={comp}'))
            if comp_count <= 5:
                subs = _hd2_subcomps(comp)
                if subs:
                    hints[feat] = subs
        identity = ji_type if gf_type != 'subset' else 'subset'
        entry = {'components': gf_sorted, 'identity': identity, 'joint': ji, 'similar': similar, 'contrasts': contrasts}
        if hints:
            entry['component_hints'] = hints
        if mma_dict:
            mma_e = (mma_dict.get(char, {}).get('etymology') or {})
            etype = mma_e.get('type')
            if etype == 'pictophonetic':
                entry['etymology'] = {'type': 'pictophonetic', 'phonetic': mma_e.get('phonetic'), 'semantic': mma_e.get('semantic'), 'hint': mma_e.get('hint')}
            elif etype in ('ideographic', 'pictographic') and mma_e.get('hint'):
                entry['etymology'] = {'type': etype, 'story': mma_e['hint']}
        if char in phonetic_families:
            ph, _, _, family = phonetic_families[char]
            entry['phonetic'] = ph
            entry['phonetic_family'] = family
        if char_dict:
            cd = char_dict.get(char, {})
            sc = cd.get('strokeCount')
            if sc: entry['stroke_count'] = sc
            stats = cd.get('statistics') or {}
            hsk = stats.get('hskLevel')
            if hsk: entry['hsk_level'] = hsk
            rank = stats.get('bookCharRank')
            if rank: entry['frequency_rank'] = rank
            gloss = cd.get('gloss', '')
            if gloss: entry['definition'] = gloss
            # stroke_count rescue: subset chars whose stroke count differs from all similar chars
            if identity == 'subset' and sc:
                same_sc = [s for s in similar if (char_dict.get(s) or {}).get('strokeCount', sc) == sc]
                if not same_sc:
                    entry['identity'] = 'stroke_count'
        if gf_type == 'subset':
            entry['ids_str'] = ids_dict.get(char, {}).get('ids', char)
        result[char] = entry
    return result


# ── per-approach component files ─────────────────────────────────────────────

def write_component_files(characters, ids_dict, similar_idx=None, output_dir='.'):
    """Build a set of components for each character using multiple decomposition approaches.

    Each approach produces a {char: [comp, ...]} JSON file. Components are filtered to
    those that vary among the character's confusable neighbours (from similar_idx) —
    components shared by ALL neighbours are excluded.

    Output:
      data_components_direct.json   — depth-1 IDS children, positional reading order
      data_components_all.json      — full recursive IDS component set, BFS depth-order
      data_components_hanzi.json    — HanziDecomposer level-2 (independent source)
      data_components_merged.json   — confirmed by ≥2 approaches, vote-count order

    Approaches:
      direct  — immediate structural parts from the depth-1 IDS operator; ordering follows
                the IDS positional reading order (left→right, top→bottom)
      all     — full recursive ancestry from the IDS tree (superset of direct); ordered by
                BFS depth so shallower (more visually prominent) components come first
      hanzi   — HanziDecomposer level-2 decomposition; an independent source that often
                disagrees with IDS, surfacing components the IDS tree misses
      merged  — components confirmed discriminating by ≥2 of the above approaches, sorted
                by vote count; empty list when no component reaches the threshold
    """
    def _ok(x): return x not in NOISE and (len(x) != 1 or _valid_comp(x))

    def _direct_list(char):
        seen, result = set(), []
        for item in (ids_dict.get(char, {}).get('decomposition', []) or []):
            if isinstance(item, dict):
                for children in item.values():
                    for ch in children:
                        if isinstance(ch, str) and ch != char and ch not in seen:
                            seen.add(ch); result += [ch]
        return result

    def _discriminating(char, comps_map):
        """Return set of components of char not shared by ALL of its similar chars."""
        my = set(comps_map.get(char, []))
        if not my: return set()
        similar = [s for s in ((similar_idx or {}).get(char, {}).get('similar', [])) if s in comps_map]
        if not similar: return my
        common = my.copy()
        for s in similar: common &= set(comps_map[s])
        return my - common

    def _bfs_leaves(char):
        """All IDS leaf characters in BFS order: shallowest components first."""
        tree = _parse_ids(ids_dict.get(char, {}).get('ids', ''))
        if not tree: return []
        seen, result, queue, i = set(), [], [tree], 0
        while i < len(queue):
            node = queue[i]; i += 1
            if isinstance(node, str):
                comp = _RADICAL_NORM.get(node, node)
                if comp != char and comp not in seen and _ok(comp): seen.add(comp); result += [comp]
            elif isinstance(node, tuple):
                queue += node[1]
        return result

    # ── build structural component maps ───────────────────────────────────────

    # direct: IDS positional reading order (left→right, top→bottom)
    direct_ordered = {c: [ch for ch in _direct_list(c) if _ok(ch)] for c in characters}
    direct_map = {c: set(direct_ordered[c]) for c in characters}
    direct = {}
    for c in characters:
        disc = _discriminating(c, direct_map)
        direct[c] = [ch for ch in direct_ordered[c] if ch in disc]

    # all: BFS depth-order (shallowest component first, tiebreak by tree position)
    all_map = {c: set(x for x in (ids_dict.get(c, {}).get('components', []) or []) if x != c and _ok(x)) for c in characters}
    all_recursive = {}
    for c in characters:
        disc = _discriminating(c, all_map)
        ordered = [x for x in _bfs_leaves(c) if x in disc]
        ordered += sorted(disc - set(ordered))
        all_recursive[c] = ordered

    # hanzi: preserve HanziDecomposer output order
    hanzi_ordered = {}
    for c in characters:
        try: r = decomposer.decompose(c, 2); raw = [x for x in (r.get('components', []) if r else []) if x and x != c and x not in NOISE and _valid_comp(x)]
        except Exception: raw = []
        seen, ordered = set(), []
        for x in raw:
            if x not in seen: seen.add(x); ordered += [x]
        hanzi_ordered[c] = ordered
    hanzi_map = {c: set(hanzi_ordered[c]) for c in characters}
    hanzi = {}
    for c in characters:
        disc = _discriminating(c, hanzi_map)
        hanzi[c] = [ch for ch in hanzi_ordered[c] if ch in disc]

    files = [
        ('data_components_direct.json', direct),
        ('data_components_all.json',    all_recursive),
        ('data_components_hanzi.json',  hanzi),
    ]

    structural_maps = [direct_map, all_map, hanzi_map]

    # ── merged: by vote count descending (most-confirmed component first) ─────

    merged = {}
    for c in characters:
        counts = defaultdict(int)
        for m in structural_maps:
            for comp in _discriminating(c, m): counts[comp] += 1
        merged[c] = sorted((comp for comp, n in counts.items() if n >= 2), key=lambda x: -counts[x])
    files += [('data_components_merged.json', merged)]

    for filename, data in files:
        with open(os.path.join(output_dir, filename), 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        non_empty = sum(1 for v in data.values() if v)
        print(f"  {filename}: {non_empty}/{len(characters)} chars have components")


# ── main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    with open("data_memodevice.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    with open("ids_dictionary.json", "r", encoding="utf-8") as f:
        ids_dict = json.load(f)

    characters = [e['character'] for g in data.values() for e in g]
    print(f"Processing {len(characters)} characters...")

    OUT = 'data_components'
    os.makedirs(OUT, exist_ok=True)

    print("\nLoading MMA and char dictionaries...")
    mma_lines = open('dictionary_makemeahanzi.txt', encoding='utf-8').readlines()
    mma_dict = {d['character']: d for d in (json.loads(l) for l in mma_lines) if d.get('character')}
    char_dict = {}
    for line in open('dictionary_char.jsonl', encoding='utf-8'):
        d = json.loads(line)
        if d.get('char'): char_dict[d['char']] = d
    print(f"  MMA: {len(mma_dict)} entries, char_dict: {len(char_dict)} entries")

    print("\nBuilding global index (fingerprint + joint identity)...")
    idx = build_char_index(characters, ids_dict, mma_dict=mma_dict, char_dict=char_dict)

    print("\nWriting per-approach component files...")
    write_component_files(characters, ids_dict, similar_idx=idx, output_dir=OUT)
