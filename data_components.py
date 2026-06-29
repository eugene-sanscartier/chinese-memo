import json
from collections import defaultdict
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
DATA_DIR = ROOT_DIR / "data"
REFERENCE_DIR = DATA_DIR / "source" / "reference"
MEMODEVICE_DIR = DATA_DIR / "derived" / "memodevice"

NOISE = set('一丨丶丿乙亅㇆㇉㇠㇇㇒㇗㇈㇏㇖㇗𠂇𠂉⺁⺙⺮⺈⺌⻊⺊⺹⻎') | {'No glyph available'}
_RADICAL_NORM = {'⻖': '阝', '⻏': '阝', '⺼': '月', '⻌': '辶'}
_COMPONENT_REMAP = {'⺌': '小', '⺮': '竹', '𧾷': '足', '𤣩': '王', '礻': '示', '牜': '牛', '𠆢': '人', '𫩠': '尚', '龸': '尚', '&CDP-8958;': '月', '㔾': '卩', '⺶': '羊'}
_SELF_COMPONENT_OVERRIDES = {'众', '森', '晶', '六', '只'}
# Explicit host-character repairs for opaque/CDP families. Each entry records the
# learner-facing replacement chosen for that specific character, not a global
# entity->character rule.
_CHAR_COMPONENT_OVERRIDES = {
    '师': ['刂', '帀'], '归': ['刂', '彐'], '帅': ['刂', '巾'],
    '候': ['亻', '矦'], '侯': ['亻', '矦'],
    '留': ['卯', '田'], '贸': ['卯', '贝'],
    '即': ['皀', '卩'], '既': ['皀', '旡'],
    '辨': ['辡', '刂'], '班': ['玨', '刂'],
    '介': ['人', '八'], '养': ['羊', '介'], '乔': ['夭', '八'],
    '其': ['甘', '八'],
    '以': ['以'], '可': ['丁', '口'], '那': ['冄', '阝'],
    '发': ['发'], '原': ['厂', '泉'], '武': ['戈', '止'],
    '局': ['尸', '句'], '摇': ['扌', '䍃'], '典': ['冊', '廾'],
    '延': ['廴', '正'], '然': ['肰', '灬'], '或': ['戈', '口'],
    '制': ['制'], '丝': ['丝'], '象': ['象'],
    '与': ['与'], '度': ['广', '廿', '又'], '展': ['展'],
    '参': ['参'], '段': ['段'], '印': ['印'],
    '益': ['益'], '夜': ['夜'], '疑': ['疑'],
    '免': ['免'], '款': ['柰', '欠'], '旅': ['旅'],
    '奥': ['奥'], '舞': ['舞'],
    '曼': ['曼'], '乌': ['乌'], '梁': ['氵', '刅', '木'],
    '妻': ['十', '女'], '席': ['广', '巾', '廿'], '唐': ['广', '口', '廿'],
    '兼': ['兼'], '肃': ['肃'], '惠': ['叀', '心'],
    '曹': ['曹'], '饰': ['饣', '巾'], '寿': ['寿'],
    '匆': ['匆'], '衰': ['衰'], '燕': ['燕'],
    '祭': ['祭'], '函': ['函'], '疆': ['弓', '畺', '土'],
    '卑': ['卑'], '伞': ['人', '十', '丷'], '脊': ['脊'],
    '淫': ['氵', '爫', '士'], '舆': ['舁', '车'], '鼎': ['鼎'],
    '焉': ['正', '灬'], '詹': ['厃', '言'], '勿': ['勿'],
    '甩': ['甩'], '嗣': ['冊', '司'], '顷': ['匕', '页'],
    '隋': ['隋'], '兵': ['斤', '廾'], '有': ['又', '月'],
    '灰': ['又', '火'], '葬': ['茻', '死'], '敢': ['甘', '攵', '豕'],
    '赛': ['塞', '贝'], '塞': ['塞'], '寒': ['塞', '冫'], '寨': ['塞', '木'],
    '族': ['方', '矢'], '施': ['方', '也'], '旋': ['方', '疋'], '旗': ['方', '其'],
    '监': ['监'], '临': ['监', '品'], '觉': ['学', '见'], '总': ['兑', '心'],
    '兑': ['兑'], '盖': ['羊', '皿'],
    '径': ['彳', '又', '工'], '轻': ['车', '又', '工'], '经': ['纟', '又', '工'],
    '劲': ['又', '工', '力'], '颈': ['又', '工', '页'], '氢': ['气', '又', '工'],
    '茎': ['艹', '又', '工'],
    '畅': ['申', '昜'], '场': ['土', '昜'], '肠': ['月', '昜'],
    '杨': ['木', '昜'], '汤': ['氵', '昜'], '扬': ['扌', '昜'],
    '载': ['戈', '车'], '裁': ['十', '戈', '衣'], '戴': ['戴'],
    '截': ['十', '戈', '隹'], '栽': ['戈', '木'], '哉': ['戈', '口'],
    '春': ['春'], '泰': ['泰'], '奉': ['丰', '廾', '手'],
    '秦': ['秦'], '奏': ['奏'],
    '营': ['营'], '劳': ['劳'], '荣': ['荣'],
    '莹': ['莹'], '莺': ['莺'],
    '紧': ['刂', '又', '糸'], '坚': ['刂', '又', '土'], '贤': ['刂', '又', '贝'],
    '肾': ['刂', '又', '月'], '竖': ['刂', '又', '立'],
    '朝': ['朝'], '韩': ['倝', '韦'], '翰': ['倝', '羽'], '乾': ['倝', '乙'],
    '释': ['釆', '又', '二'], '译': ['讠', '又', '二'],
    '泽': ['氵', '又', '二'], '择': ['扌', '又', '二'],
    '美': ['羊', '大'], '姜': ['羊', '女'], '羡': ['羊', '次'],
    '具': ['目', '廾'], '兴': ['兴'], '共': ['共'],
    '学': ['学'], '追': ['追'], '薛': ['艹', '㠯', '辛'],
    '报': ['扌', '卩', '又'], '服': ['月', '卩', '又'],
    '满': ['氵', '艹', '两'], '瞒': ['目', '艹', '两'],
    '反': ['厂', '又'], '质': ['斤', '贝'], '盾': ['⺁', '十', '目'],
    '成': ['成'], '司': ['司'], '幻': ['幻'],
    '船': ['舟', '㕣'], '铅': ['钅', '㕣'], '朵': ['几', '木'],
    '炼': ['火', '柬'], '练': ['纟', '柬'], '拣': ['扌', '柬'],
    '爷': ['父', '卩'], '卫': ['卫'], '节': ['艹', '卩'],
    '眉': ['尸', '目'], '声': ['士', '尸'], '幽': ['幽'], '兹': ['兹'],
    '颐': ['臣', '页'], '姬': ['女', '臣'], '蔑': ['艹', '罒', '戍'],
    '萝': ['艹', '罗'], '琐': ['王', '小', '贝'], '锁': ['钅', '小', '贝'],
    '击': ['击'], '贵': ['贵'], '后': ['后'], '卵': ['卵'],
    '姊': ['姊'], '派': ['派'], '同': ['冂', '口'], '扁': ['扁'], '遣': ['遣'], '定': ['宀', '正'],
    '弱': ['弱'], '蜀': ['罒', '勹', '虫'], '解': ['角', '刀', '牛'],
    '厨': ['厂', '尌'], '害': ['害'], '应': ['应'], '兽': ['兽'], '举': ['举'],
    '继': ['纟', '米'], '断': ['米', '斤'],
    '兜': ['兜'], '黎': ['黎'], '抛': ['扌', '九', '力'], '卒': ['卒'],
    '拜': ['拜'], '至': ['至'], '廷': ['廴', '壬'], '爵': ['爵'],
    '隙': ['阝', '小', '日', '小'], '辟': ['尸', '口', '辛'], '刷': ['尸', '巾', '刂'],
    '殿': ['殿'], '微': ['微'], '赢': ['赢'], '餐': ['餐'], '渊': ['渊'],
    '陋': ['阝', '丙'], '能': ['能'],
    '寝': ['宀', '丬', '彐', '又'], '侵': ['亻', '彐', '又'], '浸': ['氵', '彐', '又'],
    '鉴': ['臣', '金'], '览': ['臣', '见'], '德': ['德'], '舍': ['舍'],
    '涩': ['涩'], '腾': ['月', '马', '关'], '索': ['十', '冖', '糸'],
    '卸': ['缶', '卩'], '塌': ['土', '日', '羽'], '莽': ['艹', '犬', '廾'],
    '表': ['龶', '衣'], '佩': ['亻', '凡', '巾'], '尉': ['尸', '示', '寸'],
    '愣': ['忄', '罒', '方'], '虐': ['虍', '二'], '撤': ['扌', '育', '攵'],
    '农': ['农'], '丧': ['丧'], '畏': ['畏'],
    '产': ['产'], '商': ['立', '冏'],
    '受': ['爫', '又'], '爱': ['冖', '友'],
    '帝': ['立', '巾'], '旁': ['立', '方'],
    '囊': ['口', '襄'], '襄': ['衣', '口'],
    '在': ['才', '土'], '存': ['才', '子'],
    '岛': ['鸟', '山'], '鸟': ['鸟'],
}
_SELF_COMPONENT_OVERRIDES |= {'直', '南', '北', '带', '争', '单', '曾', '尔', '化', '傻', '幸', '嵌', '步', '夏', '衡', '寡', '复', '向'}
_IDS_OPS = {'⿰': 2, '⿱': 2, '⿲': 3, '⿳': 3, '⿴': 2, '⿵': 2, '⿶': 2, '⿷': 2, '⿸': 2, '⿹': 2, '⿺': 2, '⿻': 2}
_SLOTS = {'⿰': ['L', 'R'], '⿱': ['T', 'B'], '⿲': ['L', 'M', 'R'], '⿳': ['T', 'M', 'B'], '⿴': ['O', 'I'], '⿵': ['T', 'O'], '⿶': ['B', 'O'], '⿷': ['R', 'O'], '⿸': ['TL', 'O'], '⿹': ['TR', 'O'], '⿺': ['BL', 'O'], '⿻': ['A', 'B']}


def _parse_ids(s):
    def go(pos):
        if pos >= len(s): return None, pos
        ch = s[pos]
        if ch == '&':
            end = s.find(';', pos)
            tok = s[pos:end + 1] if end != -1 else ch
            return tok, (end + 1 if end != -1 else pos + 1)
        if ch in _IDS_OPS:
            children, p = [], pos + 1
            for _ in range(_IDS_OPS[ch]):
                child, p = go(p)
                children += [child]
            return (ch, children), p
        return ch, pos + 1
    if not s: return None
    tree, _ = go(0)
    return tree


def _valid_comp(c):
    if len(c) != 1: return True
    o = ord(c)
    return o >= 0x2E80 and not (0xE000 <= o <= 0xF8FF or 0xF0000 <= o <= 0x10FFFF)


def _pos_leaves(tree, path=''):
    if tree is None: return set()
    if isinstance(tree, str):
        comp = _RADICAL_NORM.get(tree, tree)
        if comp in NOISE or not _valid_comp(comp): return set()
        return {f'{path}={comp}' if path else comp}
    op, children = tree
    feats = set()
    for i, child in enumerate(children):
        slot = _SLOTS.get(op, [str(j) for j in range(len(children))])[i]
        feats |= _pos_leaves(child, f'{path}.{slot}' if path else slot)
    return feats


def get_pos_feats(char, ids_dict):
    tree = _parse_ids(ids_dict.get(char, {}).get('ids', ''))
    return _pos_leaves(tree) if tree else set()


def _jaccard(a, b):
    if not a and not b: return 0.0
    return len(a & b) / len(a | b)


def build_similarity_index(characters, ids_dict, threshold=0.25):
    pos_map = {c: get_pos_feats(c, ids_dict) for c in characters}
    result = {}
    for char in characters:
        feats = pos_map[char]
        threats = sorted([(other, _jaccard(feats, pos_map[other])) for other in characters if other != char and _jaccard(feats, pos_map[other]) >= threshold], key=lambda item: -item[1])
        result[char] = {'similar': [other for other, _ in threats[:8]]}
    return result


def write_final_components(characters, ids_dict, similar_idx, output_path):
    def _ok(x): return x not in NOISE and (len(x) != 1 or _valid_comp(x))
    def _component_norm(x): return _COMPONENT_REMAP.get(_RADICAL_NORM.get(x, x), _RADICAL_NORM.get(x, x))
    def _component_ok(x): return _ok(_component_norm(x))
    def _direct_components(char):
        seen, result = set(), []
        for item in (ids_dict.get(char, {}).get('decomposition', []) or []):
            if not isinstance(item, dict): continue
            for children in item.values():
                for child in children:
                    parts = []
                    if isinstance(child, str): parts += [child]
                    elif isinstance(child, dict):
                        for nested in child.values():
                            for part in nested:
                                if isinstance(part, str): parts += [part]
                    for part in parts:
                        part = _component_norm(part)
                        if part != char and _component_ok(part) and part not in seen: seen.add(part); result += [part]
        return result
    def _discriminating(char, comps_map):
        my = set(comps_map.get(char, []))
        if not my: return set()
        similar = [other for other in similar_idx.get(char, {}).get('similar', []) if other in comps_map]
        if not similar: return my
        common = my.copy()
        for other in similar: common &= set(comps_map[other])
        return my - common
    def _family_shared(char, comps_map, threshold=0.5):
        my = set(comps_map.get(char, []))
        if not my: return []
        similar = [other for other in similar_idx.get(char, {}).get('similar', []) if other in comps_map]
        if not similar: return []
        counts = defaultdict(int)
        for other in similar:
            for comp in comps_map.get(other, []):
                if comp in my: counts[comp] += 1
        return sorted((comp for comp in my if counts[comp] / len(similar) >= threshold), key=lambda comp: -counts[comp])

    direct_components = {c: _direct_components(c) for c in characters}
    component_map = {c: set(direct_components[c]) for c in characters}
    core_components = {}
    for c in characters:
        disc = _discriminating(c, component_map)
        core_components[c] = [comp for comp in direct_components[c] if comp in disc]
        if direct_components[c] and not core_components[c]: core_components[c] = direct_components[c]

    family = {c: _family_shared(c, component_map) for c in characters}
    family_components = {}
    for c in characters:
        seen, ordered = set(), []
        for comp in family[c]:
            comp = _component_norm(comp)
            if comp != c and _component_ok(comp) and comp not in seen: seen.add(comp); ordered += [comp]
        family_components[c] = ordered

    components_out = {}
    for c in characters:
        target, seen, ordered = set(family_components[c]) | set(core_components[c]), set(), []
        for comp in direct_components[c]:
            if comp in target and comp not in seen: seen.add(comp); ordered += [comp]
        for comp in family_components[c] + core_components[c]:
            if comp not in seen: seen.add(comp); ordered += [comp]
        if c in _SELF_COMPONENT_OVERRIDES: ordered = [c]
        if c in _CHAR_COMPONENT_OVERRIDES: ordered = [comp for comp in _CHAR_COMPONENT_OVERRIDES[c] if _component_ok(comp)]
        if not ordered: ordered = [c]
        components_out[c] = ordered

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f: json.dump(components_out, f, ensure_ascii=False, indent=2)
    non_empty = sum(1 for comps in components_out.values() if comps)
    print(f"  {output_path.name}: {non_empty}/{len(characters)} chars have components")


if __name__ == "__main__":
    with open(MEMODEVICE_DIR / "data_memodevice.json", "r", encoding="utf-8") as f: data = json.load(f)
    with open(REFERENCE_DIR / "ids_dictionary.json", "r", encoding="utf-8") as f: ids_dict = json.load(f)
    characters = [entry['character'] for group in data.values() for entry in group]
    print(f"Processing {len(characters)} characters...")
    print("\nBuilding visual confusable index for final approach...")
    idx = build_similarity_index(characters, ids_dict)
    print("\nWriting final component file...")
    write_final_components(characters, ids_dict, idx, DATA_DIR / "derived" / "components" / "components.json")
