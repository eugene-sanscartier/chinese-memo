import json
import re
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
REFERENCE_DIR = DATA_DIR / "source" / "reference"
DERIVED_DIR = DATA_DIR / "derived" / "cdp"
BUILD_DIR = ROOT_DIR / "build"
IDS_PATH = REFERENCE_DIR / "ids_dictionary.json"
MAP_PATH = DERIVED_DIR / "ids_dictionary_entity_render_map.json"
OUTPUT_PATH = BUILD_DIR / "cdp_render_test.html"

ENTITY_RE = re.compile(r'&[^;]+;')
CDP_RE = re.compile(r'&(A-)?CDP-([0-9A-F]{4});')
U_RE = re.compile(r'&U-([iv])([0-9]{3})\+([0-9A-F]+);')
A_U_RE = re.compile(r'&A-U-([iv])([0-9]{3})\+([0-9A-F]+);')
O_UU_RE = re.compile(r'&o-UU\+([0-9A-F]+);')

LOCAL_ENTITY_MAP = {
    '&GT-K00059;': {'char': '𬺢', 'kind': 'local-inferred'},
    '&JX2-7461;': {'char': '䍃', 'kind': 'local-inferred'},
    '&HD-TK-01032130;': {'char': '𢛳', 'kind': 'local-inferred'},
    '&MJ013489;': {'char': '曷', 'kind': 'heuristic-local'},
}


def cdp_to_pua(code):
    value = int(code, 16)
    H, L = value >> 8, value & 0xFF
    offset = (L - 0x40) if L < 0x80 else (L - 0x62)
    if 0xFA40 <= value <= 0xFEFE: return 0xE000 + (157 * (H - 0xFA)) + offset
    if 0x8E40 <= value <= 0xA0FE: return 0xE311 + (157 * (H - 0x8E)) + offset
    if 0x8140 <= value <= 0x8DFE: return 0xEEB8 + (157 * (H - 0x81)) + offset
    if 0xC6A1 <= value <= 0xC8FE: return 0xF672 + (157 * (H - 0xC6)) + offset
    raise ValueError(f"Unsupported CDP code range: {code}")


ids_text = IDS_PATH.read_text(encoding="utf-8")
entities = sorted(set(ENTITY_RE.findall(ids_text)))
mappings = {}
for entity in entities:
    cdp = CDP_RE.fullmatch(entity)
    u = U_RE.fullmatch(entity)
    a_u = A_U_RE.fullmatch(entity)
    o_uu = O_UU_RE.fullmatch(entity)
    if cdp:
        code = cdp.group(2)
        codepoint = cdp_to_pua(code)
        mappings[entity] = {"char": chr(codepoint), "codepoint": f"U+{codepoint:04X}", "kind": "cdp-pua", "status": "mapped", "source_code": code}
        continue
    if u:
        code = u.group(3)
        codepoint = int(code, 16)
        mappings[entity] = {"char": chr(codepoint), "codepoint": f"U+{codepoint:04X}", "kind": f"u-{u.group(1)}", "status": "mapped", "source_code": code}
        continue
    if a_u:
        code = a_u.group(3)
        codepoint = int(code, 16)
        mappings[entity] = {"char": chr(codepoint), "codepoint": f"U+{codepoint:04X}", "kind": f"a-u-{a_u.group(1)}", "status": "mapped", "source_code": code}
        continue
    if o_uu:
        code = o_uu.group(1)
        codepoint = int(code, 16)
        mappings[entity] = {"char": chr(codepoint), "codepoint": f"U+{codepoint:04X}", "kind": "o-uu", "status": "mapped", "source_code": code}
        continue
    if entity in LOCAL_ENTITY_MAP:
        char = LOCAL_ENTITY_MAP[entity]["char"]
        mappings[entity] = {"char": char, "codepoint": f"U+{ord(char):04X}", "kind": LOCAL_ENTITY_MAP[entity]["kind"], "status": "mapped", "source_code": f"{ord(char):X}"}
        continue
    mappings[entity] = {"char": "", "codepoint": "", "kind": "unresolved", "status": "unresolved", "source_code": ""}

rows = []
for entity, info in mappings.items():
    glyph = info["char"] if info["char"] else entity
    glyph_class = "glyph" if info["char"] else "raw-entity"
    rows += [f"""<tr><td><code>{entity}</code></td><td><code>{info["codepoint"]}</code></td><td>{info["kind"]}</td><td>{info["status"]}</td><td class="{glyph_class}">{glyph}</td></tr>"""]

html_text = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>CDP Render Test</title>
  <style>
    @font-face {{
      font-family: 'HanaMinA';
      src: url('../assets/anki/fonts/_HanaMinA.otf');
    }}
    @font-face {{
      font-family: 'HanaMinB';
      src: url('../assets/anki/fonts/_HanaMinB.otf');
    }}
    @font-face {{
      font-family: 'LXGW WenKai GB Lite Light';
      src: url('../assets/anki/fonts/_LXGWWenKaiGBLite-Light.ttf');
    }}
    body {{
      margin: 24px;
      font: 16px/1.5 'LXGW WenKai GB Lite Light', sans-serif;
      color: #222;
      background: #faf7ef;
    }}
    h1 {{
      margin: 0 0 12px 0;
      font-size: 28px;
    }}
    p {{
      max-width: 980px;
    }}
    table {{
      border-collapse: collapse;
      margin-top: 16px;
      min-width: 760px;
      background: white;
    }}
    th, td {{
      border: 1px solid #c9c0ac;
      padding: 8px 12px;
      text-align: left;
      vertical-align: middle;
    }}
    th {{
      background: #efe7d2;
    }}
    .glyph {{
      font-family: 'HanaMinA', 'HanaMinB';
      font-size: 34px;
      line-height: 1;
    }}
    .note {{
      color: #6a6357;
      font-size: 14px;
    }}
  </style>
</head>
<body>
  <h1>CDP Render Test</h1>
  <p>This is a test-only preview. It does not affect Anki generation. <code>CDP</code>/<code>A-CDP</code> entities are converted to Unicode PUA codepoints with the published Big5/EUDC conversion formula used by <code>cjkvi-ids</code>. <code>U-*</code>, <code>A-U-*</code>, and <code>o-UU+*</code> entities fall back to their embedded Unicode codepoint. A few source-specific entities are additionally mapped from local repo evidence. Unresolved entities remain visible as raw entity text.</p>
  <p class="note">Generated mappings: {len(mappings)}. JSON map: <code>{MAP_PATH.relative_to(ROOT_DIR)}</code>.</p>
  <table>
    <thead>
      <tr><th>Entity</th><th>Codepoint</th><th>Kind</th><th>Status</th><th>Rendered glyph</th></tr>
    </thead>
    <tbody>
      {"".join(rows)}
    </tbody>
  </table>
</body>
</html>
"""

DERIVED_DIR.mkdir(parents=True, exist_ok=True)
BUILD_DIR.mkdir(exist_ok=True)
MAP_PATH.write_text(json.dumps(mappings, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
OUTPUT_PATH.write_text(html_text, encoding="utf-8")
print(f"Wrote {MAP_PATH}")
print(f"Wrote {OUTPUT_PATH}")
