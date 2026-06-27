import json
import math
import os
from collections import defaultdict
from itertools import combinations
from hanzipy.decomposer import HanziDecomposer
import numpy

decomposer = HanziDecomposer()

NOISE = set('一丨丶丿乙亅㇆㇉㇠㇇㇒㇗㇈㇏㇖㇗𠂇𠂉⺁⺙⺮⺈⺌⻊⺊⺹⻎') | {'No glyph available'}
# Radical variant → canonical form.  Applied before NOISE check in _pos_leaves so that
# IDS trees using variant radicals (⻖=left-ear, ⻏=right-ear, ⺼=meat, ⻌=walk) produce
# the same positional features as trees written with the canonical form.
# Without this, 院(⿰⻖完) → {R=完} only (⻖ filtered), making it a "subset" of any
# char that also has R=完.  With it: 院 → {L=阝, R=完}, correctly discriminated.
_RADICAL_NORM = {'⻖': '阝', '⻏': '阝', '⺼': '月', '⻌': '辶'}

MIN_GROUP = 3
MAX_COMP_FREQ = 25
USEFUL_THRESHOLD = 0.7  # if top-1 coverage >= this, return one component; else add top-2

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


def get_comps(char, ids_dict):
    ids_comps = set(ids_dict.get(char, {}).get('components', [])) - {char} - NOISE
    try: dec_comps = set(decomposer.decompose(char, 2).get('components', [])) - {char} - NOISE
    except: dec_comps = set()
    return ids_comps, ids_comps | dec_comps


def get_hybrid_component_feats(char, ids_dict):
    """Return unpositioned IDS + HanziDecomposer components as 'C=component' features."""
    ids_comps = set(ids_dict.get(char, {}).get('components', [])) - {char} - NOISE
    try: dec_comps = set(decomposer.decompose(char, 2).get('components', [])) - {char} - NOISE
    except: dec_comps = set()
    return {f'C={comp}' for comp in ids_comps | dec_comps if len(comp) == 1 and _valid_comp(comp)}


# ── discriminating set ────────────────────────────────────────────────────────

def greedy_hitting_set(sep_sets, prefer):
    remaining = [s for s in sep_sets if s]
    chosen = []
    while remaining:
        candidates = set().union(*remaining)
        best = max(candidates, key=lambda x: (sum(1 for s in remaining if x in s), prefer(x)))
        chosen += [best]
        remaining = [s for s in remaining if best not in s]
    return chosen


def discriminating_set(char, group, all_comps, ids_comps, ids_dict):
    others = [c for c in group if c != char]
    seps = [all_comps[char] - all_comps[o] for o in others]
    subset_of = [others[i] for i, s in enumerate(seps) if not s]

    if subset_of:
        ids_str = ids_dict.get(char, {}).get('ids', char)
        return [], subset_of, ids_str

    def prefer(comp): return int(comp in ids_comps.get(char, set()))
    disc = greedy_hitting_set(seps, prefer)
    return disc, [], None


# ── usefulness set ────────────────────────────────────────────────────────────

def useful_set(char, group, all_comps, ids_comps, comp_freq, N):
    """Return ranked list of (component, score, coverage) for char within group.
    Score = coverage_in_group × global_rarity (IDF).
    Returns one component unless top-1 coverage < USEFUL_THRESHOLD, then adds top-2."""
    others = [c for c in group if c != char]
    n = len(others)
    subset_of = [o for o in others if all_comps[char] <= all_comps[o]]

    scores = []
    for comp in all_comps[char]:
        coverage = sum(1 for o in others if comp not in all_comps[o]) / n if n else 0.0
        rarity = math.log(N / comp_freq[comp]) / math.log(N) if comp_freq.get(comp, 0) > 0 else 0.0
        # prefer IDS-level components as tiebreaker
        in_ids = int(comp in ids_comps.get(char, set()))
        scores += [(comp, coverage * rarity, coverage, in_ids)]

    scores.sort(key=lambda x: (x[1], x[3]), reverse=True)

    if not scores:
        ids_str = ''
        return [], subset_of, ids_str

    # Decide how many components to return
    top = scores[0]
    if top[2] >= USEFUL_THRESHOLD or len(scores) == 1:
        chosen = [top[0]]
    else:
        # Add second component that covers what top-1 missed
        missed = {o for o in others if top[0] in all_comps[o]}  # top-1 didn't discriminate these
        second = next((comp for comp, _, _, _ in scores[1:] if any(comp not in all_comps[o] for o in missed)), None)
        chosen = [top[0], second] if second else [top[0]]

    ids_str = ''
    if subset_of:
        ids_str = ''  # caller handles this
    return chosen, subset_of, ids_str


# ── positional set (IDS position-aware) ──────────────────────────────────────

def positional_set(char, group, pos_feats, ids_dict):
    """Discriminate char from group using IDS positional features ('L=木', 'R=黄').
    The greedy hitting set operates on (position, component) pairs, so the result
    encodes WHERE to look, not just WHAT to look for."""
    others = [c for c in group if c != char]
    seps = [pos_feats[char] - pos_feats[o] for o in others]
    subset_of = [others[i] for i, s in enumerate(seps) if not s]
    if subset_of:
        ids_str = ids_dict.get(char, {}).get('ids', char)
        return [], subset_of, ids_str
    disc = greedy_hitting_set(seps, lambda _: 0)
    return disc, [], None


# ── global fingerprint & joint identity (char-indexed, group-free) ───────────

def _jaccard(a, b):
    if not a and not b: return 0.0
    return len(a & b) / len(a | b)

def _all_ids_similar(char, pos_map, all_chars, threshold=0.25):
    """Return ALL chars with IDS Jaccard >= threshold (uncapped — no top-8 limit)."""
    C = pos_map.get(char, set())
    if not C: return set()
    return {D for D in all_chars if D != char and _jaccard(C, pos_map.get(D, set())) >= threshold}


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


def _hybrid_similarity(pos_a, pos_b, comp_a, comp_b):
    pos_j = _jaccard(pos_a, pos_b)
    comp_j = _jaccard(comp_a, comp_b)
    return max(pos_j, comp_j, 0.65 * pos_j + 0.35 * comp_j)


def hybrid_fingerprint(char, pos_map, comp_map, feature_map, feat_freq, all_chars, threshold=0.25):
    """Minimum mixed IDS/HanziDecomposer feature set separating char from hybrid neighbors."""
    C = feature_map[char]
    if not C: return [], [], 'empty'

    threats = sorted(
        [(D, _hybrid_similarity(pos_map[char], pos_map[D], comp_map[char], comp_map[D])) for D in all_chars
         if D != char and _hybrid_similarity(pos_map[char], pos_map[D], comp_map[char], comp_map[D]) >= threshold],
        key=lambda x: -x[1]
    )
    if not threats:
        return [min(C, key=lambda f: feat_freq.get(f, 0))], [], 'unique'

    threat_chars = [D for D, _ in threats]
    jw = {D: j for D, j in threats}
    seps = [C - feature_map[D] for D in threat_chars]
    nonempty = [(threat_chars[i], s) for i, s in enumerate(seps) if s]

    if not nonempty:
        return [], [D for D, _ in threats[:8]], 'subset'

    remaining = list(nonempty)
    chosen = []
    while remaining:
        candidates = set().union(*(s for _, s in remaining))
        best = max(candidates, key=lambda f: (sum(jw[D] for D, s in remaining if f in s), -feat_freq.get(f, 0), int(not f.startswith('C='))))
        chosen += [best]
        remaining = [(D, s) for D, s in remaining if best not in s]

    similar_top = [D for D, _ in threats[:8]]
    return chosen, similar_top, 'discriminating'


def _component_contrasts(char, similar_chars, comp_map, feat_freq, skip_chars=None):
    skip_chars = skip_chars or set()
    C = {f.split('=', 1)[1] for f in comp_map[char] if f.startswith('C=')}
    result = []
    for D in similar_chars:
        if D in skip_chars: continue
        P = {f.split('=', 1)[1] for f in comp_map.get(D, set()) if f.startswith('C=')}
        diff_c = C - P
        diff_d = P - C
        if diff_c and diff_d:
            best_c = min(diff_c, key=lambda comp: feat_freq.get(f'C={comp}', 0))
            best_d = min(diff_d, key=lambda comp: feat_freq.get(f'C={comp}', 0))
            result += [{'vs': D, 'ours': best_c, 'theirs': best_d}]
    return result[:4]


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
        # MMA etymology: type + semantic/phonetic roles + English hint
        if mma_dict:
            mma_e = (mma_dict.get(char, {}).get('etymology') or {})
            etype = mma_e.get('type')
            if etype == 'pictophonetic':
                entry['etymology'] = {'type': 'pictophonetic', 'phonetic': mma_e.get('phonetic'), 'semantic': mma_e.get('semantic'), 'hint': mma_e.get('hint')}
            elif etype in ('ideographic', 'pictographic') and mma_e.get('hint'):
                entry['etymology'] = {'type': etype, 'story': mma_e['hint']}
        # MMA-sourced phonetic family (replaces IDS-inferred, covers ⿱/⿸/⿺ too)
        if char in phonetic_families:
            ph, _, _, family = phonetic_families[char]
            entry['phonetic'] = ph
            entry['phonetic_family'] = family
        # char_dict metadata: stroke count, HSK level, frequency rank, short gloss
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


def build_hybrid_char_index(characters, ids_dict, threshold=0.25):
    """Build a global character index from IDS positional features plus HanziDecomposer components.
    Returns a dict keyed by character:
      components            — mixed positional/component features from the hybrid discriminating set
      identity              — joint identity type: singleton / pair / triple / full / subset / empty
      joint                 — mixed features forming the minimal unique conjunction
      similar               — up to 8 most similar chars by hybrid IDS/component similarity
      contrasts             — positional slot contrasts where IDS structure gives a same-slot difference
      component_contrasts   — HanziDecomposer component contrasts for neighbors without a clean slot contrast
      ids_str               — IDS string for subset characters
    """
    pos_map = {c: get_pos_feats(c, ids_dict) for c in characters}
    comp_map = {c: get_hybrid_component_feats(c, ids_dict) for c in characters}
    feature_map = {c: pos_map[c] | comp_map[c] for c in characters}
    feat_freq = defaultdict(int)
    for feats in feature_map.values():
        for f in feats:
            feat_freq[f] += 1
    result = {}
    for char in characters:
        gf, similar, gf_type = hybrid_fingerprint(char, pos_map, comp_map, feature_map, feat_freq, characters, threshold)
        ji, ji_type = joint_identity(char, feature_map, characters)
        contrasts = _slot_contrasts(char, similar, pos_map, feat_freq)
        component_contrasts = _component_contrasts(char, similar, comp_map, feat_freq, {ct['vs'] for ct in contrasts})
        entry = {'components': gf, 'identity': gf_type if gf_type in {'empty', 'subset'} else ji_type,
                 'joint': ji, 'similar': similar, 'contrasts': contrasts, 'component_contrasts': component_contrasts}
        if gf_type == 'subset':
            entry['ids_str'] = ids_dict.get(char, {}).get('ids', char)
        result[char] = entry
    return result


# ── pinyin (cross-modal: visual + phonological) ───────────────────────────────

_PINYIN_TONE = {'ā':'a1','á':'a2','ǎ':'a3','à':'a4','ē':'e1','é':'e2','ě':'e3','è':'e4',
                'ī':'i1','í':'i2','ǐ':'i3','ì':'i4','ō':'o1','ó':'o2','ǒ':'o3','ò':'o4',
                'ū':'u1','ú':'u2','ǔ':'u3','ù':'u4','ǖ':'v1','ǘ':'v2','ǚ':'v3','ǜ':'v4'}
_PINYIN_INIT  = ['zh','ch','sh','b','p','m','f','d','t','n','l','g','k','h','j','q','x','r','z','c','s','y','w']

def _parse_pinyin(py_raw):
    """Return (initial, final, tone) for a toned pinyin string."""
    tone = '5'; base = []
    for ch in py_raw:
        if ch in _PINYIN_TONE: base.append(_PINYIN_TONE[ch][0]); tone = _PINYIN_TONE[ch][1]
        else: base.append(ch)
    base = ''.join(base)
    init = next((i for i in _PINYIN_INIT if base.startswith(i)), '')
    return init, base[len(init):], tone

def _pinyin_sim(pys1, pys2):
    """Max phonological similarity across all pinyin variants: 1.0=same, 0.85=same syllable diff tone,
    0.55=same final (rhyme), 0.25=same initial only, 0.0=unrelated."""
    best = 0.0
    for i1,f1,t1 in pys1:
        for i2,f2,t2 in pys2:
            if i1==i2 and f1==f2 and t1==t2: s=1.0
            elif i1==i2 and f1==f2: s=0.85
            elif f1==f2 and f1: s=0.55
            elif i1==i2 and i1: s=0.25
            else: s=0.0
            best=max(best,s)
    return best


def build_pinyin_index(characters, ids_dict, mma_dict, threshold=0.25, ph_threshold=0.7):
    """Build a character index that annotates visual confusions with phonological similarity.
    Additional pinyin-specific fields per entry:
      pinyin          — raw MMA pinyin list
      homophones      — other dataset chars with identical pronunciation (same syllable + tone)
      near_homophones — other dataset chars with same syllable, different tone
      double_danger   — chars that are BOTH visual (Jaccard>=threshold) AND phonological (>=ph_threshold)
                        confusers — the hardest pairs for learners
    """
    pos_map = {c: get_pos_feats(c, ids_dict) for c in characters}
    feat_freq = defaultdict(int)
    for feats in pos_map.values():
        for f in feats: feat_freq[f] += 1
    n = len(characters)

    # Parse pinyin for all chars
    char_py = {}
    for c in characters:
        raw = (mma_dict.get(c) or {}).get('pinyin', [])
        if raw: char_py[c] = [_parse_pinyin(py) for py in raw if py]

    # Build (initial, final) → chars lookup for fast homophone search
    syllable_map = defaultdict(list)  # (init, final, tone) → chars
    rhyme_map    = defaultdict(list)  # (init, final) → chars
    for c, pys in char_py.items():
        for tup in pys:
            syllable_map[tup] += [c]
            rhyme_map[(tup[0], tup[1])] += [c]

    result = {}
    for char in characters:
        gf, similar, gf_type = global_fingerprint(char, pos_map, characters, threshold)
        ji, ji_type = joint_identity(char, pos_map, characters)
        contrasts = _slot_contrasts(char, similar, pos_map, feat_freq)
        gf_sorted = sorted(gf, key=lambda f: _feat_salience_score(f, feat_freq, n), reverse=True)

        entry = {'components': gf_sorted, 'identity': ji_type if gf_type != 'subset' else 'subset',
                 'joint': ji, 'similar': similar, 'contrasts': contrasts}
        if gf_type == 'subset': entry['ids_str'] = ids_dict.get(char, {}).get('ids', char)

        pys = char_py.get(char, [])
        if pys:
            entry['pinyin'] = (mma_dict.get(char) or {}).get('pinyin', [])

            # Homophones: same (init, final, tone) in dataset
            homos = sorted({d for py in pys for d in syllable_map.get(py,[]) if d != char})
            if homos: entry['homophones'] = homos

            # Near-homophones: same (init, final) but different tone
            near = sorted({d for py in pys for d in rhyme_map.get((py[0],py[1]),[])
                           if d != char and not any(py2 == py for py2 in char_py.get(d,[]))})
            if near: entry['near_homophones'] = near

            # Double danger: visual similar AND phonologically similar
            dd = sorted([d for d in similar if d in char_py and
                         _pinyin_sim(pys, char_py[d]) >= ph_threshold],
                        key=lambda d: -_pinyin_sim(pys, char_py[d]))
            if dd: entry['double_danger'] = dd

        result[char] = entry
    return result


# ── visual pixel similarity (HOG-like edge features) ─────────────────────────

_VISUAL_FONT_PATH  = None  # set by build_visual_index before use
_VISUAL_FONT_CACHE = {}
_VISUAL_FEAT_CACHE = {}
_VISUAL_SIZE       = 56
_VISUAL_GRID       = 7    # grid cells per side (7×7 = 49 features per char)

def _edge_feats(char):
    """Return normalised edge-density feature vector for char (49-d float32)."""
    if char in _VISUAL_FEAT_CACHE: return _VISUAL_FEAT_CACHE[char]
    from PIL import Image, ImageDraw, ImageFont
    if _VISUAL_FONT_PATH not in _VISUAL_FONT_CACHE:
        _VISUAL_FONT_CACHE[_VISUAL_FONT_PATH] = ImageFont.truetype(_VISUAL_FONT_PATH, _VISUAL_SIZE - 8)
    font = _VISUAL_FONT_CACHE[_VISUAL_FONT_PATH]
    img  = Image.new('L', (_VISUAL_SIZE, _VISUAL_SIZE), 255)
    ImageDraw.Draw(img).text((3, 2), char, font=font, fill=0)
    arr  = (numpy.array(img) < 128).astype(numpy.float32)
    gx   = numpy.diff(arr, axis=1, prepend=arr[:, :1])
    gy   = numpy.diff(arr, axis=0, prepend=arr[:1, :])
    mag  = numpy.sqrt(gx**2 + gy**2)
    step = _VISUAL_SIZE // _VISUAL_GRID
    v    = numpy.array([mag[i*step:(i+1)*step, j*step:(j+1)*step].sum()
                        for i in range(_VISUAL_GRID) for j in range(_VISUAL_GRID)], dtype=numpy.float32)
    n    = numpy.linalg.norm(v)
    v    = v / (n + 1e-8)
    _VISUAL_FEAT_CACHE[char] = v
    return v


def build_visual_index(characters, ids_dict, font_path, threshold=0.97, ids_threshold=0.25):
    """Build a character index using pixel-level visual similarity (HOG-like edge features).
    Finds confusions that IDS decomposition misses — e.g. 己/已/巳, 候/侯, 胃/肾/臂.
    Returns a dict keyed by character:
      similar       — up to 8 most similar chars by edge feature cosine similarity
      visual_only   — similar chars NOT found by IDS Jaccard (novel pairs)
      identity      — same computation as global index (IDS-based)
      components    — IDS-based discriminating features (for card display)
      contrasts     — IDS slot contrasts vs visual neighbors
      edge_sim      — {char: similarity_score} for visual_similar
    """
    global _VISUAL_FONT_PATH
    _VISUAL_FONT_PATH = font_path
    _VISUAL_FEAT_CACHE.clear()

    print("  Rendering characters and computing edge features...")
    feat_mat = numpy.stack([_edge_feats(c) for c in characters])  # (N, 49)
    sim_mat  = feat_mat @ feat_mat.T                               # (N, N) cosine similarities

    pos_map  = {c: get_pos_feats(c, ids_dict) for c in characters}
    feat_freq = defaultdict(int)
    for feats in pos_map.values():
        for f in feats: feat_freq[f] += 1
    n = len(characters)
    char_idx = {c: i for i, c in enumerate(characters)}

    result = {}
    for char in characters:
        gf, ids_similar, gf_type = global_fingerprint(char, pos_map, characters, ids_threshold)
        ji, ji_type = joint_identity(char, pos_map, characters)
        ids_similar_set = _all_ids_similar(char, pos_map, characters, ids_threshold)

        # Visual similar: top-k by edge sim, excluding self
        ci   = char_idx[char]
        sims = sim_mat[ci]
        order = numpy.argsort(sims)[::-1]
        visual_sim = [(characters[j], float(sims[j])) for j in order
                      if characters[j] != char and sims[j] >= threshold][:8]
        vis_chars  = [c for c, _ in visual_sim]
        vis_only   = [c for c in vis_chars if c not in ids_similar_set]
        edge_scores = {c: round(s, 4) for c, s in visual_sim}

        # Contrasts vs visual neighbors (IDS-based where possible)
        gf_sorted  = sorted(gf, key=lambda f: _feat_salience_score(f, feat_freq, n), reverse=True)
        contrasts  = _slot_contrasts(char, vis_chars, pos_map, feat_freq)

        entry = {'components': gf_sorted, 'identity': ji_type if gf_type != 'subset' else 'subset',
                 'joint': ji, 'similar': vis_chars, 'contrasts': contrasts}
        if vis_only:   entry['visual_only'] = vis_only
        if edge_scores: entry['edge_sim'] = edge_scores
        if gf_type == 'subset': entry['ids_str'] = ids_dict.get(char, {}).get('ids', char)
        result[char] = entry
    return result


# ── radical cluster index (abstract visual groups) ────────────────────────────

# Radicals that look visually similar mapped to a shared cluster label.
# Only truly confusable pairs: 氵 (3-drip water left) ≈ 冫 (2-drip ice left),
# 扌/手 (hand), 忄/心 (heart), 讠/言 (speech), 纟/糸 (thread), 钅/金 (metal).
_RADICAL_CLUSTER = {
    '氵': 'DRIP', '冫': 'DRIP',
    '扌': 'HAND', '手': 'HAND',
    '忄': 'HEART', '心': 'HEART',
    '讠': 'SPEECH', '言': 'SPEECH',
    '纟': 'THREAD', '糸': 'THREAD',
    '钅': 'METAL', '金': 'METAL',
    '艹': 'GRASS', '⺾': 'GRASS',
    '辶': 'WALK', '彳': 'WALK',
    '刂': 'KNIFE', '刀': 'KNIFE',
    '阝': 'MOUND',  # already normalized from ⻖/⻏ via _RADICAL_NORM
}

def _get_cluster_feats(char, ids_dict):
    """Positional features with clustered radicals collapsed to shared labels.
    Returns a set containing ONLY the abstract cluster features (not the concrete form)
    so that cross-radical pairs can be found without double-counting."""
    pos = get_pos_feats(char, ids_dict)
    result = set()
    for feat in pos:
        if '=' not in feat: result.add(feat); continue
        slot, comp = feat.split('=', 1)
        cluster = _RADICAL_CLUSTER.get(comp)
        result.add(f'{slot}={cluster}' if cluster else feat)
    return result


def build_radical_cluster_index(characters, ids_dict, threshold=0.25):
    """Build a character index using abstract radical clusters.
    Visually similar radicals (氵≈冫, 扌≈手, 忄≈心, etc.) are collapsed to the same
    cluster label before Jaccard computation, finding cross-radical confusions that the
    concrete IDS index misses.
    Returns a dict keyed by character:
      components      — cluster-feature discriminating set (salience-sorted)
      identity        — singleton / pair / triple / full / subset
      joint           — minimal unique cluster-feature conjunction
      similar         — up to 8 most similar chars by cluster Jaccard
      cluster_only    — similar chars not found by concrete IDS Jaccard
      contrasts       — slot contrasts (using cluster labels where applicable)
    """
    cluster_map = {c: _get_cluster_feats(c, ids_dict) for c in characters}
    pos_map     = {c: get_pos_feats(c, ids_dict) for c in characters}

    feat_freq = defaultdict(int)
    for feats in cluster_map.values():
        for f in feats: feat_freq[f] += 1
    n = len(characters)

    result = {}
    for char in characters:
        gf, similar, gf_type = global_fingerprint(char, cluster_map, characters, threshold)
        ji, ji_type = joint_identity(char, cluster_map, characters)

        # Which of these are NEW (not in concrete IDS similar)?
        ids_similar = _all_ids_similar(char, pos_map, characters, threshold)
        cluster_only = [d for d in similar if d not in ids_similar]

        gf_sorted  = sorted(gf, key=lambda f: _feat_salience_score(f, feat_freq, n), reverse=True)
        contrasts  = _slot_contrasts(char, similar, cluster_map, feat_freq)

        entry = {'components': gf_sorted, 'identity': ji_type if gf_type != 'subset' else 'subset',
                 'joint': ji, 'similar': similar, 'contrasts': contrasts}
        if cluster_only: entry['cluster_only'] = cluster_only
        if gf_type == 'subset': entry['ids_str'] = ids_dict.get(char, {}).get('ids', char)
        result[char] = entry
    return result


# ── position-agnostic direct-component index ──────────────────────────────────

def build_subcomp_index(characters, ids_dict, threshold=0.35):
    """Build a similarity index using position-agnostic IDF-Jaccard over direct IDS children.

    The IDS positional approach uses (slot, component) pairs like {L=氵, R=青} —
    two chars are similar only if the SAME component appears in the SAME slot.
    This misses cases where the same component appears in different structural positions:
      削 = ⿰肖刂  {L=肖, R=刂}
      梢 = ⿰木肖  {L=木, R=肖}  →  IDS positional Jaccard = 0, but both contain 肖!
      案 = ⿱安木  {T=安, B=木}
      按 = ⿰扌安  {L=扌, R=安}  →  IDS positional Jaccard = 0, but both contain 安!

    This index uses DIRECT IDS children (top-level decomposition) without position
    labels, weighted by IDF so rare/complex components dominate over common radicals.
    Private-use components unique to one character appear in the denominator with
    maximal IDF, penalizing sparse component sets and preventing false positives.

    Per-character output fields:
      direct_components   — canonical direct IDS children (as strings)
      subcomp_similar     — up to 8 chars with highest position-agnostic IDF-Jaccard
      subcomp_only        — subcomp_similar chars NOT found by IDS Jaccard >= 0.25
      subcomp_shared      — for top-4 subcomp_only pairs: which component is shared
    """
    def _item_to_str(item):
        if isinstance(item, str): return item
        if isinstance(item, dict):
            for op, children in item.items():
                return op + ''.join(_item_to_str(c) for c in children)
        return '?'

    def _direct_children(char):
        decomp = ids_dict.get(char, {}).get('decomposition', [])
        result = []
        for item in decomp:
            if isinstance(item, dict):
                for children in item.values():
                    for child in children:
                        s = _item_to_str(child)
                        if s and s != char: result += [s]
        return result

    n = len(characters)
    child_to_chars = defaultdict(set)
    char_to_children = {}
    for c in characters:
        children = _direct_children(c)
        char_to_children[c] = children
        for ch in children:
            child_to_chars[ch].add(c)
    idf = {comp: math.log(n / (len(chars) + 1)) for comp, chars in child_to_chars.items()}

    def _idf_jac(ca, cb):
        sa = set(char_to_children.get(ca, []))
        sb = set(char_to_children.get(cb, []))
        if not sa and not sb: return 0.0
        shared = sa & sb; union = sa | sb
        sw = sum(idf.get(c, 0) for c in shared)
        uw = sum(idf.get(c, 0) for c in union)
        return sw / uw if uw > 0 else 0.0

    pos_map = {c: get_pos_feats(c, ids_dict) for c in characters}
    char_neighbors = defaultdict(list)
    for i, a in enumerate(characters):
        for b in characters[i+1:]:
            s = _idf_jac(a, b)
            if s >= threshold:
                char_neighbors[a] += [(b, s)]
                char_neighbors[b] += [(a, s)]

    result = {}
    for char in characters:
        children = char_to_children.get(char, [])
        neighbors = sorted(char_neighbors.get(char, []), key=lambda x: -x[1])
        ids_sim = _all_ids_similar(char, pos_map, characters)
        subcomp_sim = [b for b, _ in neighbors[:8]]
        subcomp_only = [b for b in subcomp_sim if b not in ids_sim]
        shared_info = {}
        for b, s in neighbors[:4]:
            if b in ids_sim: continue
            shared = set(char_to_children.get(char, [])) & set(char_to_children.get(b, []))
            # Only include shared components that are recognizable (in dataset or short)
            shared_clean = [c for c in sorted(shared) if len(c) == 1]
            if shared_clean: shared_info[b] = shared_clean
        entry = {}
        if children: entry['direct_components'] = children
        if subcomp_sim: entry['subcomp_similar'] = subcomp_sim
        if subcomp_only: entry['subcomp_only'] = subcomp_only
        if shared_info: entry['subcomp_shared'] = shared_info
        result[char] = entry
    return result


# ── compound word context index ───────────────────────────────────────────────

def build_compound_index(characters, ids_dict, word_freq, min_freq=500, df_max=20):
    """Build a character index based on compound word co-occurrence patterns.

    For each character, finds the 2-char compounds it appears in (left and right
    position), then identifies other characters that appear in similar compound
    patterns.  Two characters sharing a RARE compound partner (one that appears
    with ≤ df_max dataset chars) are "compound-confused": a learner might write
    the wrong character because both fit the same word-slot.

    Uses IDF-weighted Jaccard over rare partners to avoid domination by extremely
    common characters (的/了/在 appear in thousands of compounds).

    Per-character output fields:
      left_compounds   — top 8 most frequent words where char appears first
      right_compounds  — top 8 most frequent words where char appears second
      compound_similar — other dataset chars sharing rare compound partners
      compound_only    — compound_similar chars NOT found by IDS Jaccard >= 0.25
    """
    char_set = set(characters)
    left_partners  = defaultdict(dict)   # char → {partner: freq}
    right_partners = defaultdict(dict)   # char → {partner: freq}

    for word, freq in word_freq.items():
        if len(word) != 2: continue
        f = int(freq)
        if f < min_freq: continue
        a, b = word[0], word[1]
        if a in char_set:
            if f > left_partners[a].get(b, 0): left_partners[a][b] = f
        if b in char_set:
            if f > right_partners[b].get(a, 0): right_partners[b][a] = f

    # Partner document frequency: how many dataset chars use partner X
    ldf = defaultdict(int)
    rdf = defaultdict(int)
    for c in characters:
        for p in left_partners[c]:  ldf[p] += 1
        for p in right_partners[c]: rdf[p] += 1

    n = len(characters)

    def _rare_set(partner_dict, df_map):
        """Return set of partners with df <= df_max (rare = distinctive)."""
        return frozenset(p for p in partner_dict if df_map[p] <= df_max)

    def _idf_jac(sa, sb, df_map):
        if not sa and not sb: return 0.0
        shared = sa & sb; union = sa | sb
        sw = sum(math.log(n / (df_map[p] + 1)) for p in shared)
        uw = sum(math.log(n / (df_map[p] + 1)) for p in union)
        return sw / (uw + 1e-9) if uw > 0 else 0.0

    # Precompute rare partner sets
    rare_left  = {c: _rare_set(left_partners[c],  ldf) for c in characters}
    rare_right = {c: _rare_set(right_partners[c], rdf) for c in characters}

    # Build per-char compound_similar: IDF-Jaccard >= 0.15 (either direction)
    COMP_THRESH = 0.15
    pos_map = {c: get_pos_feats(c, ids_dict) for c in characters}

    compound_neighbors = defaultdict(list)
    active = [c for c in characters if rare_left[c] or rare_right[c]]
    for i, a in enumerate(active):
        for b in active[i+1:]:
            lj = _idf_jac(rare_left[a],  rare_left[b],  ldf)
            rj = _idf_jac(rare_right[a], rare_right[b], rdf)
            best = max(lj, rj)
            if best >= COMP_THRESH:
                compound_neighbors[a] += [(b, lj, rj)]
                compound_neighbors[b] += [(a, lj, rj)]

    result = {}
    for char in characters:
        ids_sim = _all_ids_similar(char, pos_map, characters)

        # Top compounds (sorted by freq)
        lc = sorted(left_partners[char].items(), key=lambda x: -x[1])[:8]
        rc = sorted(right_partners[char].items(), key=lambda x: -x[1])[:8]
        left_words  = [char + p for p, _ in lc]
        right_words = [p + char for p, _ in rc]

        # compound_similar: sorted by best IDF-Jaccard
        neighbors = sorted(compound_neighbors.get(char, []), key=lambda x: -max(x[1], x[2]))
        comp_sim = [b for b, _, _ in neighbors[:8]]
        comp_only = [b for b in comp_sim if b not in ids_sim]

        # Shared rare partners for the top neighbors
        shared_patterns = {}
        for b, lj, rj in neighbors[:4]:
            sl = sorted(rare_left[char] & rare_left[b])[:4]
            sr = sorted(rare_right[char] & rare_right[b])[:4]
            if sl or sr: shared_patterns[b] = {'left': sl, 'right': sr}

        entry = {}
        if left_words:   entry['left_compounds']   = left_words
        if right_words:  entry['right_compounds']  = right_words
        if comp_sim:     entry['compound_similar']  = comp_sim
        if comp_only:    entry['compound_only']     = comp_only
        if shared_patterns: entry['shared_patterns'] = shared_patterns
        result[char] = entry
    return result


def build_semantic_index(characters, ids_dict, char_to_entry):
    """Build a semantic synonym index based on MMA English gloss words.

    Characters sharing the same single-word gloss form a semantic confusion group —
    a learner who knows the MEANING but not the FORM may write the wrong one.

    Per-character output fields:
      gloss           — English meaning keyword (memodevice 'gloss' field)
      gloss_group     — other chars sharing this exact gloss
      semantic_only   — gloss_group chars NOT found by IDS Jaccard >= 0.25
    """
    pos_map = {c: get_pos_feats(c, ids_dict) for c in characters}
    gloss_to_chars = defaultdict(list)
    char_gloss = {}
    for c in characters:
        g = char_to_entry.get(c, {}).get('gloss', '').strip().lower()
        if g:
            char_gloss[c] = g
            gloss_to_chars[g] += [c]
    result = {}
    for char in characters:
        gloss = char_gloss.get(char)
        if not gloss:
            result[char] = {}
            continue
        group = [c for c in gloss_to_chars[gloss] if c != char]
        if not group:
            result[char] = {'gloss': gloss}
            continue
        ids_sim = _all_ids_similar(char, pos_map, characters)
        sem_only = [c for c in group if c not in ids_sim]
        entry = {'gloss': gloss, 'gloss_group': group}
        if sem_only: entry['semantic_only'] = sem_only
        result[char] = entry
    return result


# ── deep component ancestry index ─────────────────────────────────────────────

def build_deepcomp_index(characters, ids_dict, threshold=0.4):
    """Build a similarity index using IDF-Jaccard over DEEP (depth-2+) complex components.

    The subcomp index uses DIRECT IDS children (depth-1). This extends one level
    deeper: depth-2+ components that are themselves COMPLEX (have their own IDS
    with decomposition operators). Simple primitives (一, 口, 日 with atomic IDS)
    are excluded to prevent false positives from trivially common strokes.

    Example: 骑(马+奇) and 荷(艹+何) share no direct child, so subcomp misses them.
    But 奇=⿱大可 and 何=⿰亻可 both contain 可 (itself complex: ⿵𠃍口).
    Both 骑 and 荷 therefore have 可 at depth-2, revealing hidden structural kinship.
    Similarly: 颤/堤/宣/恒/垣 all share 旦 at depth-2 through different intermediaries.

    Per-character output fields:
      deep_components   — deep complex components (depth-2+, in dataset, complex IDS)
      deep_similar      — up to 8 chars with highest deep IDF-Jaccard
      deep_only         — deep_similar chars NOT found by IDS Jaccard >= 0.25 and
                          not already sharing a direct child (not in subcomp)
      deep_shared       — for top-4 deep_only pairs: which deep component is shared
    """
    IDS_OPS = set('⿰⿱⿲⿳⿴⿵⿶⿷⿸⿹⿺⿻')
    char_set = set(characters)
    n = len(characters)

    def _is_complex(c):
        ids_str = ids_dict.get(c, {}).get('ids', '') or ''
        return any(op in ids_str for op in IDS_OPS)

    def _direct_set(char):
        direct = set()
        for item in (ids_dict.get(char, {}).get('decomposition', []) or []):
            if isinstance(item, dict):
                for children in item.values():
                    for ch in children:
                        if isinstance(ch, str) and ch != char: direct.add(ch)
        return direct

    char_direct = {c: _direct_set(c) for c in characters}
    char_deep = {}
    for c in characters:
        all_comps = set(ids_dict.get(c, {}).get('components', []) or [])
        deep = all_comps - char_direct[c] - {c}
        char_deep[c] = {x for x in deep if x in char_set and _is_complex(x)}

    comp_to_chars = defaultdict(set)
    for c, comps in char_deep.items():
        for comp in comps: comp_to_chars[comp].add(c)
    idf = {comp: math.log(n / (len(cs) + 1)) for comp, cs in comp_to_chars.items()}

    def _idf_jac(a, b):
        sa, sb = char_deep[a], char_deep[b]
        if not sa and not sb: return 0.0
        shared = sa & sb; union = sa | sb
        sw = sum(idf.get(c, 0) for c in shared)
        uw = sum(idf.get(c, 0) for c in union)
        return sw / uw if uw > 0 else 0.0

    pos_map = {c: get_pos_feats(c, ids_dict) for c in characters}
    char_neighbors = defaultdict(list)
    active = [c for c in characters if char_deep[c]]
    for i, a in enumerate(active):
        for b in active[i+1:]:
            s = _idf_jac(a, b)
            if s >= threshold:
                char_neighbors[a] += [(b, s)]
                char_neighbors[b] += [(a, s)]

    result = {}
    for char in characters:
        deep = sorted(char_deep.get(char, set()))
        neighbors = sorted(char_neighbors.get(char, []), key=lambda x: -x[1])
        ids_sim = _all_ids_similar(char, pos_map, characters)
        deep_sim = [b for b, _ in neighbors[:8]]
        deep_only = [b for b in deep_sim
                     if b not in ids_sim
                     and not (char_direct.get(char, set()) & char_direct.get(b, set()))]
        shared_info = {}
        for b, _ in neighbors[:4]:
            if b in ids_sim or (char_direct.get(char, set()) & char_direct.get(b, set())): continue
            shared = sorted(char_deep.get(char, set()) & char_deep.get(b, set()))
            shared_clean = [c for c in shared if len(c) == 1]
            if shared_clean: shared_info[b] = shared_clean
        entry = {}
        if deep: entry['deep_components'] = deep
        if deep_sim: entry['deep_similar'] = deep_sim
        if deep_only: entry['deep_only'] = deep_only
        if shared_info: entry['deep_shared'] = shared_info
        result[char] = entry
    return result


# ── per-approach component files ─────────────────────────────────────────────

def write_component_files(characters, ids_dict, mma_dict=None, compound_idx=None, semantic_idx=None, output_dir='.'):
    """Write a {char: [comp, ...]} JSON file for each similarity approach.

    'Components' is interpreted broadly — whatever features characterise a char
    according to that approach (structural sub-chars, positional strings, cluster
    labels, compound partners, or semantic synonyms).

    Files always written (require only ids_dict):
      data_components_direct.json      — direct IDS children (depth-1); subcomp basis
      data_components_deep.json        — depth-2+ complex components; deepcomp basis
      data_components_all.json         — all recursive IDS components present in dataset
      data_components_positional.json  — positional feature strings ('L=木', 'R=黄')
      data_components_radical.json     — cluster feature strings ('L=DRIP', 'R=HAND')
      data_components_hanzi.json       — HanziDecomposer level-2 components; hybrid basis

    Files written only when optional sources are supplied:
      data_components_phonetic.json    — MMA phonetic + semantic components   (mma_dict)
      data_components_compound.json    — top compound word partners            (compound_idx)
      data_components_semantic.json    — semantic synonym group chars          (semantic_idx)
    """
    # IDS_OPS = set('⿰⿱⿲⿳⿴⿵⿶⿷⿸⿹⿺⿻')
    # char_set = set(characters)

    # def _is_complex(c):
    #     return any(op in (ids_dict.get(c, {}).get('ids', '') or '') for op in IDS_OPS)

    def _direct_set(char):
        s = set()
        for item in (ids_dict.get(char, {}).get('decomposition', []) or []):
            if isinstance(item, dict):
                for children in item.values():
                    for ch in children:
                        if isinstance(ch, str) and ch != char: s.add(ch)
        return s

    char_direct_set = {c: _direct_set(c) for c in characters}

    def _ok(x): return x not in NOISE and (len(x) != 1 or _valid_comp(x))

    direct = {c: sorted(ch for ch in char_direct_set[c] if _ok(ch)) for c in characters}

    # deep = {}
    # for c in characters:
    #     raw = set(ids_dict.get(c, {}).get('components', []) or []) - char_direct_set[c] - {c}
    #     deep[c] = sorted(x for x in raw if _ok(x) and _is_complex(x))

    all_recursive = {c: sorted(x for x in (ids_dict.get(c, {}).get('components', []) or [])
                                if x != c and _ok(x)) for c in characters}

    # Slot ordering for positional features: canonical L-to-R / T-to-B reading order.
    _SLOT_ORDER = {'T': 0, 'TL': 1, 'TR': 2, 'L': 3, 'M': 4, 'R': 5, 'BL': 6, 'B': 7, 'O': 8, 'I': 9, 'A': 10}
    def _slot_rank(feat):
        slot = feat.split('=')[0].split('.')[0] if '=' in feat else ''
        return _SLOT_ORDER.get(slot, 99)

    def _pos_components(char):
        """Positional features stripped of slot labels, deduped, sorted by canonical slot order."""
        feats = sorted(get_pos_feats(char, ids_dict), key=_slot_rank)
        seen = set(); result = []
        for f in feats:
            comp = f.split('=', 1)[1] if '=' in f else f
            if comp not in seen: seen.add(comp); result += [comp]
        return result

    positional = {c: _pos_components(c) for c in characters}

    # radical = {c: sorted(_get_cluster_feats(c, ids_dict)) for c in characters}

    hanzi = {}
    for c in characters:
        try:
            r = decomposer.decompose(c, 2)
            comps = sorted(x for x in (r.get('components', []) if r else [])
                           if x and x != c and x not in NOISE and _valid_comp(x))
        except Exception:
            comps = []
        hanzi[c] = comps

    files = [
        ('data_components_direct.json',     direct),
        # ('data_components_deep.json',      deep),
        ('data_components_all.json',         all_recursive),
        ('data_components_positional.json',  positional),
        # ('data_components_radical.json',   radical),
        ('data_components_hanzi.json',       hanzi),
    ]

    # if mma_dict:
    #     phonetic = {}
    #     for c in characters:
    #         e = (mma_dict.get(c, {}).get('etymology') or {})
    #         comps = []
    #         if e.get('phonetic'): comps += [_RADICAL_NORM.get(e['phonetic'], e['phonetic'])]
    #         if e.get('semantic'): comps += [_RADICAL_NORM.get(e['semantic'], e['semantic'])]
    #         phonetic[c] = comps
    #     files += [('data_components_phonetic.json', phonetic)]

    # if compound_idx:
    #     compound = {}
    #     for c in characters:
    #         e = compound_idx.get(c, {})
    #         partners = [w[-1] for w in e.get('left_compounds', [])] + [w[0] for w in e.get('right_compounds', [])]
    #         compound[c] = sorted(set(partners))
    #     files += [('data_components_compound.json', compound)]

    # if semantic_idx:
    #     semantic = {c: sorted(semantic_idx.get(c, {}).get('gloss_group', [])) for c in characters}
    #     files += [('data_components_semantic.json', semantic)]

    for filename, data in files:
        with open(os.path.join(output_dir, filename), 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        non_empty = sum(1 for v in data.values() if v)
        print(f"  {filename}: {non_empty}/{len(characters)} chars have components")


# ── group finding ─────────────────────────────────────────────────────────────

def find_similar_chars(characters, ids_dict, mode='disc'):
    if mode == 'pos':
        pos_map = {c: get_pos_feats(c, ids_dict) for c in characters}
        feat_to_chars = defaultdict(list)
        for char, feats in pos_map.items():
            for feat in feats:
                feat_to_chars[feat] += [char]
        valid_feats = {f for f, chars in feat_to_chars.items() if MIN_GROUP <= len(chars) <= MAX_COMP_FREQ}

        raw_groups = {}
        for feat in valid_feats:
            chars = feat_to_chars[feat]
            key = frozenset(chars)
            if key not in raw_groups: raw_groups[key] = {'chars': list(chars), 'shared': []}
            raw_groups[key]['shared'] += [feat]

        groups = []
        for g in raw_groups.values():
            chars = g['chars']
            members = []
            for char in chars:
                comps, subset_of, ids_str = positional_set(char, chars, pos_map, ids_dict)
                entry = {'char': char, 'components': comps}
                if subset_of: entry['subset_of'] = subset_of
                if ids_str: entry['ids_str'] = ids_str
                members += [entry]
            groups += [{'shared': g['shared'], 'members': members}]
        return sorted(groups, key=lambda g: -len(g['members']))

    ids_comps_map, all_comps_map = {}, {}
    for c in characters:
        ic, ac = get_comps(c, ids_dict)
        ids_comps_map[c] = ic
        all_comps_map[c] = ac

    comp_to_chars = defaultdict(list)
    for char, comps in all_comps_map.items():
        for comp in comps:
            comp_to_chars[comp] += [char]
    valid_comps = {c for c, chars in comp_to_chars.items() if MIN_GROUP <= len(chars) <= MAX_COMP_FREQ}

    # global frequency for IDF (over all components seen, not just valid ones)
    comp_freq = {c: len(chars) for c, chars in comp_to_chars.items()}
    N = len(characters)

    raw_groups = {}
    for comp in valid_comps:
        chars = comp_to_chars[comp]
        key = frozenset(chars)
        if key not in raw_groups: raw_groups[key] = {'chars': list(chars), 'shared': []}
        raw_groups[key]['shared'] += [comp]

    groups = []
    for g in raw_groups.values():
        chars = g['chars']
        members = []
        for char in chars:
            if mode == 'disc':
                comps, subset_of, ids_str = discriminating_set(char, chars, all_comps_map, ids_comps_map, ids_dict)
            else:
                comps, subset_of, ids_str = useful_set(char, chars, all_comps_map, ids_comps_map, comp_freq, N)
                if not ids_str and subset_of:
                    ids_str = ids_dict.get(char, {}).get('ids', char)

            entry = {'char': char, 'components': comps}
            if subset_of: entry['subset_of'] = subset_of
            if ids_str: entry['ids_str'] = ids_str
            members += [entry]
        groups += [{'shared': g['shared'], 'members': members}]

    return sorted(groups, key=lambda g: -len(g['members']))


# ── main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    with open("data_memodevice.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    with open("ids_dictionary.json", "r", encoding="utf-8") as f:
        ids_dict = json.load(f)

    characters = [e['character'] for g in data.values() for e in g]
    print(f"Processing {len(characters)} characters...")

    OUT = 'data_similar'
    os.makedirs(OUT, exist_ok=True)

    filenames = {'disc': f'{OUT}/data_similar_disc.json', 'useful': f'{OUT}/data_similar_useful.json', 'pos': f'{OUT}/data_similar_pos.json'}

    for mode in ('disc', 'useful', 'pos'):
        groups = find_similar_chars(characters, ids_dict, mode=mode)
        print(f"\n── {mode} mode  ({len(groups)} groups) ──")
        for g in groups[:8]:
            print(f"  shared [{' '.join(g['shared'])}]")
            for m in g['members']:
                comp_str = ' '.join(m['components']) if m['components'] else '—'
                note = f"  ← subset of {''.join(m.get('subset_of', []))}  IDS={m.get('ids_str','')}" if 'subset_of' in m else ''
                print(f"    {m['char']}  {comp_str}{note}")
            print()
        with open(filenames[mode], "w", encoding="utf-8") as f:
            json.dump(groups, f, ensure_ascii=False, indent=2)
        print(f"Saved to {filenames[mode]}")

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

    # Stats
    from collections import Counter
    id_dist = Counter(e['identity'] for e in idx.values())
    print(f"  identity distribution: {dict(id_dist)}")

    # Sample output
    print("\n── global index (sample) ──")
    sample = ['横', '间', '问', '棒', '棱', '常', '党', '披', '波', '超', '清', '情', '请']
    for char in sample:
        if char not in idx: continue
        e = idx[char]
        gf = ' '.join(e['components']) if e['components'] else '—'
        ji = ' & '.join(e['joint']) if e['joint'] else '—'
        sim = ''.join(e['similar'][:5])
        ct_str = '; '.join(f"{c['vs']}:{c['slot']}={c['theirs']}" for c in e.get('contrasts', [])[:3])
        ph_fam = e.get('phonetic_family', [])
        ph_str = f"  phonetic={e['phonetic']} family={''.join(m['char'] for m in ph_fam[:6])}" if 'phonetic' in e else ''
        etym = e.get('etymology', {})
        etym_str = f"  [{etym.get('type','?')}] {etym.get('hint','')}({etym.get('semantic','')})→{etym.get('phonetic','')}" if etym else ''
        sc_str = f"  sc={e.get('stroke_count','')} hsk={e.get('hsk_level','')}"
        print(f"  {char}  disc=[{gf}]  joint=[{ji}]  type={e['identity']}  similar={sim}{ph_str}{etym_str}{sc_str}")
        if ct_str: print(f"       contrasts: {ct_str}")

    with open(f'{OUT}/data_similar_global.json', 'w', encoding='utf-8') as f:
        json.dump(idx, f, ensure_ascii=False, indent=2)
    print(f"\nSaved to {OUT}/data_similar_global.json")

    print("\nBuilding hybrid index (IDS positions + HanziDecomposer components)...")
    hybrid_idx = build_hybrid_char_index(characters, ids_dict)
    hybrid_id_dist = Counter(e['identity'] for e in hybrid_idx.values())
    print(f"  identity distribution: {dict(hybrid_id_dist)}")

    print("\n── hybrid index (sample) ──")
    for char in sample:
        if char not in hybrid_idx: continue
        e = hybrid_idx[char]
        gf = ' '.join(e['components']) if e['components'] else '—'
        ji = ' & '.join(e['joint']) if e['joint'] else '—'
        sim = ''.join(e['similar'][:5])
        ct_str = '; '.join(f"{c['vs']}:{c['slot']}={c['theirs']}" for c in e.get('contrasts', [])[:3])
        hct_str = '; '.join(f"{c['vs']}:C={c['theirs']}" for c in e.get('component_contrasts', [])[:3])
        print(f"  {char}  disc=[{gf}]  joint=[{ji}]  type={e['identity']}  similar={sim}")
        if ct_str: print(f"       slot contrasts: {ct_str}")
        if hct_str: print(f"       component contrasts: {hct_str}")

    with open(f'{OUT}/data_similar_hybrid.json', 'w', encoding='utf-8') as f:
        json.dump(hybrid_idx, f, ensure_ascii=False, indent=2)
    print(f"\nSaved to {OUT}/data_similar_hybrid.json")

    print("\nBuilding pinyin cross-modal index...")
    pinyin_idx = build_pinyin_index(characters, ids_dict, mma_dict)
    dd_count = sum(1 for e in pinyin_idx.values() if e.get('double_danger'))
    homo_count = sum(1 for e in pinyin_idx.values() if e.get('homophones'))
    print(f"  double_danger chars: {dd_count}, chars with homophones: {homo_count}")
    print("\n── pinyin index (sample) ──")
    for char in ['清','情','晴','胃','畏','候','侯','己','已','常']:
        if char not in pinyin_idx: continue
        e = pinyin_idx[char]
        py_str = ','.join((mma_dict.get(char) or {}).get('pinyin', []))
        dd_str = ''.join(e.get('double_danger', []))
        homo_str = ''.join(e.get('homophones', []))
        near_str = ''.join(e.get('near_homophones', [])[:4])
        print(f"  {char}[{py_str}]  double_danger={dd_str}  homophones={homo_str}  near={near_str}")
    with open(f'{OUT}/data_similar_pinyin.json', 'w', encoding='utf-8') as f:
        json.dump(pinyin_idx, f, ensure_ascii=False, indent=2)
    print(f"\nSaved to {OUT}/data_similar_pinyin.json")

    print("\nBuilding visual pixel index (edge features)...")
    font_path = '_LXGWWenKaiGBLite-Regular.ttf'
    visual_idx = build_visual_index(characters, ids_dict, font_path)
    vis_only_count = sum(1 for e in visual_idx.values() if e.get('visual_only'))
    print(f"  chars with visual-only (non-IDS) similar chars: {vis_only_count}")
    print("\n── visual index (sample) ──")
    for char in ['清','情','胃','畏','候','侯','己','已','巳']:
        if char not in visual_idx: continue
        e = visual_idx[char]
        sim_str = ''.join(e.get('similar', [])[:6])
        vo_str = ''.join(e.get('visual_only', []))
        es_str = ' '.join(f"{c}:{s}" for c,s in list(e.get('edge_sim', {}).items())[:4])
        print(f"  {char}  similar={sim_str}  visual_only={vo_str}")
        if es_str: print(f"       edge_sims: {es_str}")
    with open(f'{OUT}/data_similar_visual.json', 'w', encoding='utf-8') as f:
        json.dump(visual_idx, f, ensure_ascii=False, indent=2)
    print(f"\nSaved to {OUT}/data_similar_visual.json")

    # print("\nBuilding radical cluster index...")
    # radical_idx = build_radical_cluster_index(characters, ids_dict)
    # cluster_only_count = sum(1 for e in radical_idx.values() if e.get('cluster_only'))
    # print(f"  chars with cluster-only (cross-radical) new similar chars: {cluster_only_count}")
    # id_dist_r = Counter(e['identity'] for e in radical_idx.values())
    # print(f"  identity distribution: {dict(id_dist_r)}")
    # print("\n── radical cluster index (sample) ──")
    # for char in ['清','冷','情','快','忆','说','话','银','铜']:
    #     if char not in radical_idx: continue
    #     e = radical_idx[char]
    #     sim_str = ''.join(e.get('similar', [])[:6])
    #     co_str = ''.join(e.get('cluster_only', []))
    #     gf = ' '.join(e['components']) if e['components'] else '—'
    #     print(f"  {char}  disc=[{gf}]  similar={sim_str}  cluster_only={co_str}")
    # with open(f'{OUT}/data_similar_radical.json', 'w', encoding='utf-8') as f:
    #     json.dump(radical_idx, f, ensure_ascii=False, indent=2)
    # print(f"\nSaved to {OUT}/data_similar_radical.json")

    print("\nBuilding position-agnostic subcomponent index...")
    subcomp_idx = build_subcomp_index(characters, ids_dict)
    sc_sim_count = sum(1 for e in subcomp_idx.values() if e.get('subcomp_similar'))
    sc_only_count = sum(1 for e in subcomp_idx.values() if e.get('subcomp_only'))
    print(f"  chars with subcomp_similar: {sc_sim_count}")
    print(f"  chars with subcomp_only (not IDS): {sc_only_count}")
    print("\n── subcomp index (sample) ──")
    for char in ['削', '梢', '案', '按', '含', '吟', '想', '湘', '箱', '哥', '呵', '塑', '溯', '威', '咸']:
        if char not in subcomp_idx: continue
        e = subcomp_idx[char]
        sim = ''.join(e.get('subcomp_similar', [])[:6])
        only = ''.join(e.get('subcomp_only', [])[:4])
        shared = {k: v for k, v in e.get('subcomp_shared', {}).items()}
        print(f"  {char}: sim={sim}  only={only}  shared={shared}")
    with open(f'{OUT}/data_similar_subcomp.json', 'w', encoding='utf-8') as f:
        json.dump(subcomp_idx, f, ensure_ascii=False, indent=2)
    print(f"\nSaved to {OUT}/data_similar_subcomp.json")

    # print("\nBuilding compound word context index...")
    # import warnings; warnings.filterwarnings('ignore')
    # import logging; logging.disable(logging.CRITICAL)
    # from hanzipy.dictionary import HanziDictionary
    # word_freq = HanziDictionary().word_freq
    # compound_idx = build_compound_index(characters, ids_dict, word_freq)
    # comp_sim_count = sum(1 for e in compound_idx.values() if e.get('compound_similar'))
    # comp_only_count = sum(1 for e in compound_idx.values() if e.get('compound_only'))
    # print(f"  chars with compound_similar: {comp_sim_count}")
    # print(f"  chars with compound_only (not IDS): {comp_only_count}")
    # print("\n── compound index (sample) ──")
    # for char in ['早','晚','他','她','做','作','清','情','已','己','大','太','干','千']:
    #     if char not in compound_idx: continue
    #     e = compound_idx[char]
    #     lc = ','.join(e.get('left_compounds', [])[:4])
    #     rc = ','.join(e.get('right_compounds', [])[:4])
    #     cs = ''.join(e.get('compound_similar', [])[:6])
    #     co = ''.join(e.get('compound_only', [])[:4])
    #     print(f"  {char}: L=[{lc}] R=[{rc}] sim={cs} only={co}")
    #     for b, pats in list(e.get('shared_patterns', {}).items())[:2]:
    #         sl = ''.join(pats.get('left', []))
    #         sr = ''.join(pats.get('right', []))
    #         if sl: print(f"       shared_L with {b}: {sl}")
    #         if sr: print(f"       shared_R with {b}: {sr}")
    # with open(f'{OUT}/data_similar_compound.json', 'w', encoding='utf-8') as f:
    #     json.dump(compound_idx, f, ensure_ascii=False, indent=2)
    # print(f"\nSaved to {OUT}/data_similar_compound.json")

    # print("\nBuilding semantic synonym index...")
    # char_to_entry = {e['character']: e for g in data.values() for e in g}
    # semantic_idx = build_semantic_index(characters, ids_dict, char_to_entry)
    # sem_group_count = sum(1 for e in semantic_idx.values() if e.get('gloss_group'))
    # sem_only_count = sum(1 for e in semantic_idx.values() if e.get('semantic_only'))
    # print(f"  chars with gloss_group: {sem_group_count}")
    # print(f"  chars with semantic_only (not IDS): {sem_only_count}")
    # print("\n── semantic index (sample) ──")
    # for char in ['清', '晰', '楚', '己', '自', '已', '曾', '既', '明', '亮', '早', '晚', '夜']:
    #     if char not in semantic_idx: continue
    #     e = semantic_idx[char]
    #     g = e.get('gloss', '—')
    #     grp = ''.join(e.get('gloss_group', []))
    #     so = ''.join(e.get('semantic_only', []))
    #     print(f"  {char} [{g}]  group={grp}  semantic_only={so}")
    # with open(f'{OUT}/data_similar_semantic.json', 'w', encoding='utf-8') as f:
    #     json.dump(semantic_idx, f, ensure_ascii=False, indent=2)
    # print(f"\nSaved to {OUT}/data_similar_semantic.json")

    # print("\nBuilding deep component ancestry index...")
    # deepcomp_idx = build_deepcomp_index(characters, ids_dict)
    # deep_sim_count = sum(1 for e in deepcomp_idx.values() if e.get('deep_similar'))
    # deep_only_count = sum(1 for e in deepcomp_idx.values() if e.get('deep_only'))
    # print(f"  chars with deep_similar: {deep_sim_count}")
    # print(f"  chars with deep_only (not IDS or subcomp): {deep_only_count}")
    # print("\n── deep component index (sample) ──")
    # for char in ['骑', '荷', '歌', '啊', '寄', '崎', '颤', '堤', '宣', '恒', '喜', '凳', '禧', '躁', '藻']:
    #     if char not in deepcomp_idx: continue
    #     e = deepcomp_idx[char]
    #     dc = ''.join(e.get('deep_components', []))
    #     ds = ''.join(e.get('deep_similar', [])[:6])
    #     do = ''.join(e.get('deep_only', [])[:4])
    #     print(f"  {char}: deep={dc}  sim={ds}  only={do}")
    # with open(f'{OUT}/data_similar_deepcomp.json', 'w', encoding='utf-8') as f:
    #     json.dump(deepcomp_idx, f, ensure_ascii=False, indent=2)
    # print(f"\nSaved to {OUT}/data_similar_deepcomp.json")

    print("\nWriting per-approach component files...")
    write_component_files(characters, ids_dict,
        mma_dict=mma_dict,
        # compound_idx=compound_idx,
        # semantic_idx=semantic_idx,
        output_dir=OUT)
