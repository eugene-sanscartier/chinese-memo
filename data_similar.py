import json
import math
from collections import defaultdict
from itertools import combinations
from hanzipy.decomposer import HanziDecomposer

decomposer = HanziDecomposer()

NOISE = set('一丨丶丿乙亅㇆㇉㇠㇇㇒㇗㇈㇏㇖㇗𠂇𠂉⺁⻖⻌⻏⺼⺙⺮⺈⺌⻊⺊⺹⻎') | {'No glyph available'}

MIN_GROUP = 3
MAX_COMP_FREQ = 25
USEFUL_THRESHOLD = 0.7  # if top-1 coverage >= this, return one component; else add top-2

# IDS operator arity and positional slot names
_IDS_OPS = {'⿰':2,'⿱':2,'⿲':3,'⿳':3,'⿴':2,'⿵':2,'⿶':2,'⿷':2,'⿸':2,'⿹':2,'⿺':2,'⿻':2}
_SLOTS   = {'⿰':['L','R'],'⿱':['T','B'],'⿲':['L','M','R'],'⿳':['T','M','B'],
            '⿴':['O','I'],'⿵':['T','O'],'⿶':['B','O'],'⿷':['R','O'],
            '⿸':['TL','O'],'⿹':['TR','O'],'⿺':['BL','O'],'⿻':['A','B']}


def _parse_ids(s):
    def go(pos):
        if pos >= len(s): return None, pos
        ch = s[pos]
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
    o = ord(c)
    return (o >= 0x2E80 and not (0xE000 <= o <= 0xF8FF or 0xF0000 <= o <= 0x10FFFF))


def _pos_leaves(tree, path=''):
    """Recursively extract 'pos=component' strings from IDS tree leaves (no operators)."""
    if tree is None: return set()
    if isinstance(tree, str):
        if tree in NOISE or not _valid_comp(tree): return set()
        return {f'{path}={tree}' if path else tree}
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


def build_char_index(characters, ids_dict, threshold=0.25):
    """Build global fingerprint, joint identity, and contrastive pairs for every character.
    Returns a dict keyed by character:
      components   — pos-features from global discriminating set
      identity     — joint identity type: singleton / pair / triple / full / subset
      joint        — pos-features forming the minimal unique conjunction
      similar      — up to 8 most similar chars (Jaccard >= threshold)
      contrasts    — slot contrasts vs nearest lookalikes: [{vs, slot, ours, theirs}]
      ids_str      — IDS string for subset characters
    """
    pos_map = {c: get_pos_feats(c, ids_dict) for c in characters}
    feat_freq = defaultdict(int)
    for feats in pos_map.values():
        for f in feats:
            feat_freq[f] += 1
    result = {}
    for char in characters:
        gf, similar, gf_type = global_fingerprint(char, pos_map, characters, threshold)
        ji, ji_type = joint_identity(char, pos_map, characters)
        contrasts = _slot_contrasts(char, similar, pos_map, feat_freq)
        entry = {'components': gf, 'identity': ji_type if gf_type != 'subset' else 'subset',
                 'joint': ji, 'similar': similar, 'contrasts': contrasts}
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

    filenames = {'disc': 'data_similar_disc.json', 'useful': 'data_similar_useful.json', 'pos': 'data_similar_pos.json'}

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

    print("\nBuilding global index (fingerprint + joint identity)...")
    idx = build_char_index(characters, ids_dict)

    # Stats
    from collections import Counter
    id_dist = Counter(e['identity'] for e in idx.values())
    print(f"  identity distribution: {dict(id_dist)}")

    # Sample output
    print("\n── global index (sample) ──")
    sample = ['横', '间', '问', '棒', '棱', '常', '党', '披', '波', '超']
    for char in sample:
        if char not in idx: continue
        e = idx[char]
        gf = ' '.join(e['components']) if e['components'] else '—'
        ji = ' & '.join(e['joint']) if e['joint'] else '—'
        sim = ''.join(e['similar'][:5])
        ct_str = '; '.join(f"{c['vs']}:{c['slot']}={c['theirs']}" for c in e.get('contrasts', [])[:3])
        print(f"  {char}  disc=[{gf}]  joint=[{ji}]  type={e['identity']}  similar={sim}")
        if ct_str: print(f"       contrasts: {ct_str}")

    with open('data_similar_global.json', 'w', encoding='utf-8') as f:
        json.dump(idx, f, ensure_ascii=False, indent=2)
    print("\nSaved to data_similar_global.json")

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

    with open('data_similar_hybrid.json', 'w', encoding='utf-8') as f:
        json.dump(hybrid_idx, f, ensure_ascii=False, indent=2)
    print("\nSaved to data_similar_hybrid.json")
