import html
import json
import os
import re
import unicodedata
from urllib.parse import unquote
import numpy.random
import hashlib
import glob

import pandas

from hanzipy.decomposer import HanziDecomposer

decomposer = HanziDecomposer()

import re

_re_number = re.compile(r'\d')

import genanki

AUDIO_DIR = "../pinyin-audio/allsetlearning"

def pinyin_audio_filename(pinyin_data):
    final = pinyin_data["final"].replace("u", "ü") if pinyin_data["u_is_v"] else pinyin_data["final"]
    return unicodedata.normalize("NFD", f'{pinyin_data["initial"]}{final}{pinyin_data["tone"]}.mp3')

with open("css.css", "r", encoding="utf-8") as file_obj:
    CSS = file_obj.read()

with open("frontcloze_template.html", "r", encoding="utf-8") as file_obj:
    FRONT_TEMPLATE = file_obj.read()

with open("backcloze_template.html", "r") as file_obj:
    BACK_TEMPLATE = file_obj.read()

with open("memo.json", "r", encoding="utf-8") as file_obj:
    memo_data = json.load(file_obj)


def generate_character_html(entry, memo_data):
    """Generate HTML content for a single character's answer section"""
    char = entry["character"]
    pinyin_data = entry["pinyin"]
    pinyin_str = pinyin_data["pinyin"]
    gloss = entry["gloss"]
    gloss_fr = entry["gloss_fr"]
    hint = entry["hint"]
    subcomponents_fr = entry["subcomponents_fr"]

    # Build decomposition HTML
    decomp_html = ""
    if "components" in entry and entry["components"]:
        decomp_html += '<div class="acentersmall" style="text-align:left;"><strong>Decomposition:</strong><br>'
        for component in entry["components"]:
            component_gloss_str = f'{component["gloss_fr"]} [{component["gloss"]}]'
            decomp_html += f'<div style="margin-top:2px;text-align:left;margin-left:5%;"><strong>━</strong> <span class="decomp-char">{component["character"]}</span> ({component_gloss_str})'
            if "hint" in component and component["hint"] and component["hint"] not in ["None", ""]:
                decomp_html += f"[Hint: {component['hint']}]"
            decomp_html += "<br></div>"

        if not (len(subcomponents_fr) == 1 and component["character"] in list(subcomponents_fr)[0]):
            subcomp_str = ""
            for subcomponent in list(subcomponents_fr.items()):
                sub_key, sub_value = subcomponent[0], subcomponent[1]
                subcomp_str += f'<span class="decomp-char">{sub_key}</span>({sub_value}); '
            if subcomp_str:
                decomp_html += f'<div style="margin-top:2px;text-align:left;margin-left:10%;"><strong class="subdetail-marker">●</strong> {subcomp_str}<br></div>'

    # Build hint HTML
    hint_html = ""
    if hint and hint != "":
        hint_html += '<div class="acentersmall" style="text-align:left;"><strong>Hint:</strong><br>'
        hint_html += f'<div style="margin-top:2px;text-align:left;margin-left:5%;"><strong>━</strong> {hint}<br></div>'
        hint_html += '</div>'

    # Build gloss HTML
    gloss_html = ""
    gloss_html += f'<div class="acentersmall" style="text-align:left;"><strong>Gloss:</strong></div>'
    gloss_html += f'<div style="margin-top:2px;text-align:left;margin-left:5%;"><strong>━</strong> {gloss_fr} [{gloss}]</div>'

    # Build character display
    char_html = f'[sound:{pinyin_audio_filename(pinyin_data)}]'
    char_html += f'<div style="font-family:\'LXGW WenKai GB Lite Light\';font-size:45px;line-height:normal;text-align:center;margin-top:25px;">{char}</div>'
    char_html += f'<div class="acentersmall" style="text-align:center;"><strong>P</strong>: {entry["position"]} / <strong>R</strong>: {entry["rank"]} / <strong>C</strong>: {float(entry["coverage"]):.2f}%</div><br>'

    # Build detailed pinyin breakdown
    pinyin_initial = pinyin_data["initial"]
    pinyin_final = pinyin_data["final"]
    pinyin_tone = pinyin_data["tone"]
    u_is_v = pinyin_data["u_is_v"]

    pinyin_detailed = '<div class="acentersmall" style="text-align:left;"><strong>Pinyin:</strong><br>'
    pinyin_detailed += f'<div style="margin-top:2px;text-align:left;margin-left:5%;"><strong>━</strong> {pinyin_str}<br></div>'

    if pinyin_initial != "":
        pinyin_detailed += f'<div style="margin-top:2px;text-align:left;margin-left:10%;"><strong class="subdetail-marker">●</strong> <strong>[{pinyin_initial}]</strong> - {memo_data["initials"][pinyin_initial]}<br></div>'

    if pinyin_final in memo_data["finals"]:
        action_str = f"{memo_data['finals'][pinyin_final]['action']}({memo_data['finals'][pinyin_final]['image']})"
        pinyin_detailed += f'<div style="margin-top:2px;text-align:left;margin-left:10%;"><strong class="subdetail-marker">●</strong> <strong>[{pinyin_final}]</strong> - {action_str}<br></div>'
    else:
        pinyin_detailed += f'<div style="margin-top:2px;text-align:left;margin-left:10%;"><strong class="subdetail-marker">●</strong> <strong>[{pinyin_final}]</strong> - {memo_data["initials"][pinyin_final]}<br></div>'

    pinyin_detailed += f'<div style="margin-top:2px;text-align:left;margin-left:10%;"><strong class="subdetail-marker">●</strong> <strong>[{memo_data["tones"][pinyin_tone]["symbol"]}]</strong> - {memo_data["tones"][pinyin_tone]["view"]}'
    if u_is_v:
        pinyin_detailed += f" - <strong>[{memo_data['tones']['6']['symbol']}]</strong>"
    pinyin_detailed += "<br></div>"
    pinyin_detailed += "</div>"

    # Combine all HTML
    answer_html = char_html
    answer_html += pinyin_detailed
    answer_html += gloss_html
    answer_html += hint_html
    answer_html += decomp_html
    answer_html += "</div><br>"

    return answer_html


def build_cloze_note(radical_key, guid, radical_entrys, loci_key="", loci_name="", loci_range=None):
    """Build a single cloze note for all characters in a radical group"""

    # Create title text with loci metadata
    if loci_range:
        length = loci_range[1] - loci_range[0] + 1
        # look if ther is a number at the end of the string and if yes store it in a viariable and remove it
        match = re.search(r'(\d+)\s*$', loci_key)
        if match: loci_key = loci_key[:match.start()].rstrip() + f' #{int(match.group(1))}'

        title_text = f"{loci_key} <br> {loci_name} <br> [{loci_range[0]}-{loci_range[1]}] ({length})"

    # Build the cloze text with all characters
    cloze_text = ""
    note_text = ""

    # Get loci image for this loci group (all entries share same loci)
    first_entry = radical_entrys[0]
    img, loci_name = get_image_file(radical_key, loci_data, first_entry["position"], first_entry["character"])
    locus_info = f"{loci_key}<br>" + loci_name
    loci_html = f'<div class="acentersmall" style="text-align:center">{locus_info}</div><br>'
    loci_html += f'<div class="image" style="text-align:center;"><img src="{img.split("/")[-1]}"></div><br>'

    for idx, entry in enumerate(radical_entrys, start=1):
        char = entry["character"]
        answer_html = generate_character_html(entry, memo_data)
        # Create cloze deletion - all use c1 to appear on same card; use position as hint
        cloze_text += f"{{{{c1::{answer_html}::{char} : {entry['position']}}}}} "

    # Create the model
    model_id = int(hashlib.sha256(("Cloze-Model-Device").encode()).hexdigest(), 16) % (1 << 16)
    model = genanki.Model(model_id, f'Cloze-Model-Device', fields=[{
        'name': 'Title'
    }, {
        'name': 'Content'
    }, {
        'name': 'Note'
    }, {
        'name': 'Loci'
    }], templates=[{
        'name': 'Cloze',
        'qfmt': FRONT_TEMPLATE,
        'afmt': BACK_TEMPLATE,
    }], css=CSS, model_type=genanki.Model.CLOZE)

    # Create the note
    note = genanki.Note(model=model, fields=[title_text, cloze_text, note_text, loci_html], guid=guid)

    return note


def generate_guid(entry):
    """Generate a unique GUID for an entry based on character and position"""
    content = f"{entry['character']}-{entry['position']}-standard"
    return int(hashlib.sha256(content.encode()).hexdigest(), 16) % (1 << 63)


def build_standard_note(entry, memo_data, next_entry=None):
    """Build a standard (non-cloze) note for a single character"""
    char = entry["character"]
    answer_html = generate_character_html(entry, memo_data)

    # Get image for the character
    radical_key = entry.get('_radical_key', '')
    full_img = False
    if radical_key in ["⺁音夕文㇎比乂气非黑革⺕龙匕彐玨牙麻吅羽", "㇇出生戶多面无长已见西回老水入金弋色品飞风言兵示彡首众足母斗双网血食州香圭玉肉森弱㚘鼓页麦兟瓦鬲鸟炎鼻赫疋歺⺺竹昌赤韦鼠吕晶豆隶瓜乙⺪寸欠卜卵⺳鼎龟厽镸犬戋凸凹棘毋", "亻", "口", "手至而自㇗里从巳曰己⺧角廴北川隹片卯缶骨鬼尢臼辡辰", "木", "甘丬牛爫罒鱼虍", "羊走士弓", "艹", "覀子干行耂冖身夂匸舌龴刀斤", "讠", "一"]:
        full_img = True
    img, loci_name = get_image_file(radical_key, loci_data, entry["position"], char, full_img=full_img)
    # Determine loci key for display and include trailing number as #N if present
    loci_key_std = get_loci_key(radical_key, entry["position"], char, loci_data)
    m = re.search(r'(\d+)\s*$', loci_key_std)
    if m:
        loci_display_key = loci_key_std[:m.start()].rstrip() + f' #{int(m.group(1))}'
    else:
        loci_display_key = loci_key_std
    locus_info = f"{loci_display_key}<br>{loci_name}"
    loci_html = f'<div class="acentersmall" style="text-align:center">{locus_info}</div><br>'
    loci_html += f'<div class="image" style="text-align:center;"><img src="{img.split("/")[-1]}"></div><br>'

    # Add next entry preview if available (as collapsible spoiler)
    if next_entry:
        next_char = next_entry["character"]
        next_html = '<hr style="margin: 15px 0;">'
        next_html += '<div class="spoiler" style="padding:0px; margin:0 0; text-align:center;">'
        next_html += f'<div class="spoiler-hint" onclick="this.style.display=\'none\'; this.nextElementSibling.style.display=\'block\';" style="cursor:pointer; color:#4285f4; font-size:22px; padding:5px;">▼ {next_char} ▼</div>'
        next_html += '<div class="spoiler-content" style="display:none;">'
        next_html += generate_character_html(next_entry, memo_data)
        next_html += '</div></div><br>'
        answer_html += next_html

    # Format question with the large character and French gloss
    char_display = f'<div style="font-family:\'LXGW WenKai GB Lite Light\';font-size:45px;line-height:normal;text-align:center;margin-top:25px;">{char}</div><div class="acentersmall" style="text-align:center;">({entry["gloss_fr"]})</div>'
    question_html = char_display

    # Add image to bottom of answer
    answer_html += loci_html

    model = genanki.Model(20594999998, "Standard-Model-Device", fields=[{
        "name": "Character"
    }, {
        "name": "Answer"
    }], templates=[
        {
            "name": "Card 1",
            "qfmt": "<div id='card-body'>{{Character}}</div>",
            "afmt": "{{FrontSide}}<hr id=answer>{{Answer}}"
        },
    ], css=CSS)

    guid = generate_guid(entry)
    note = genanki.Note(model=model, fields=[question_html, answer_html], guid=guid)

    return note


def get_loci_key(radical_key: str, position: int, char: str, loci_data: dict) -> str:
    """Determine which loci key a character belongs to based on its radical and position"""
    special = ["㇒雨虫", "𠂇囗丿田礻耳", "衤巾", "⺊又⺈勹饣"]

    if radical_key in special:
        radical = decomposer.decompose(char, 2)["components"][0]
        return radical

    for loci, loci_info in loci_data.items():
        if loci.startswith(radical_key):
            if loci_info["range"][0] <= position <= loci_info["range"][1]:
                return loci

    return radical_key  # fallback to radical if no loci found


def get_image_file(key: str, loci_data: dict, k: int, char: str, full_img=False):
    img_file = ""

    special = ["㇒雨虫", "𠂇囗丿田礻耳", "衤巾", "⺊又⺈勹饣"]
    if key in special:
        radical = decomposer.decompose(char, 2)["components"][0]

        img_file = f"loci/{radical}.png"
        loci_name = loci_data.get(radical, {}).get("name", "")
        return img_file, loci_name

    for loci, loci_info in loci_data.items():
        if loci.startswith(key):

            if full_img:
                if key[0] == "㇇": key = "㇇"

                img_file = f"loci/{key}.png"
                loci_name = loci_data.get(loci, {}).get("name", "")
                break

            if loci_info["range"][0] <= k <= loci_info["range"][1]:
                loci_name = loci_data.get(loci, {}).get("name", "")

                if loci[0] == "㇇":
                    loci = "㇇" + loci[-1]
                img_file = f"loci/{loci}.png"
                break

    return img_file, loci_name


def excelmemo_sets():
    dictionary_char = []
    with open("dictionary_char.jsonl", "r", encoding="utf-8") as file_obj:
        for json_line in file_obj:
            entry = json.loads(json_line)
            dictionary_char += [entry]
    dictionary_char = {entry["char"]: entry for entry in dictionary_char if "char" in entry}

    with open("gloss_translated.json", "r", encoding="utf-8") as file_obj:
        gloss_list = json.load(file_obj)

    with pandas.ExcelWriter(f"memo_sets.xlsx") as writer:
        df = pandas.DataFrame(counter_list)
        df.to_excel(writer, sheet_name="Loci Sets", index=False)
        writer.sheets["Loci Sets"].autofit()

        loci_path = []
        for loci in counter_list:
            if loci['loci'] not in [entry['loci'] for entry in loci_path]: loci_path += [loci]

        for i, loci in enumerate(loci_path):
            del loci['length']
            loci['set'] = i + 1
            loci['meaning'] = gloss_list.get(loci['loci'], '').get('gloss_fr', '')

        df = pandas.DataFrame(loci_path)
        df.to_excel(writer, sheet_name="Loci Path", index=False)
        writer.sheets["Loci Path"].autofit()


with open("data_memodevice.json", "r", encoding="utf-8") as file_obj:
    dict_entries = json.load(file_obj)

with open("loci.json", "r", encoding="utf-8") as file_obj:
    loci_data = json.load(file_obj)

# open guid txt list
with open("guids.txt", "r", encoding="utf-8") as file_obj:
    guid_list = [line.strip() for line in file_obj.readlines()]

counter_list = []

if __name__ == "__main__":
    entries, decks = [], []

    # Reorganize entries by loci instead of radical
    loci_groups = {}
    deck_counter = 0
    all_entries_list = []  # For standard deck

    for radical_key, radical_entrys in dict_entries.items():
        for entry in radical_entrys:
            # Store radical_key in entry for later use in build_standard_note
            entry['_radical_key'] = radical_key
            # Determine which loci this character belongs to
            loci_key = get_loci_key(radical_key, entry["position"], entry["character"], loci_data)

            if loci_key not in loci_groups:
                loci_groups[loci_key] = {"radical_key": radical_key, "entries": []}

            loci_groups[loci_key]["entries"].append(entry)
            all_entries_list.append(entry)  # Collect for standard deck

    # Create cloze decks grouped by loci
    for m, (loci_key, loci_group) in enumerate(loci_groups.items()):
        radical_key = loci_group["radical_key"]
        loci_entrys = loci_group["entries"]

        # Get loci name and range for deck title
        loci_info = loci_data.get(loci_key, {})
        loci_name = loci_info.get("name", loci_key)
        loci_range = loci_info.get("range", [])

        if loci_range:
            range_str = f"[{loci_range[0]}-{loci_range[1]}]"
            length = loci_range[1] - loci_range[0] + 1
            deck_title = f'Character Set::{m+1:03d} {loci_key[0]} - {range_str} ({length}): {loci_name}'
            counter_list += [{'set': m + 1, 'loci': loci_key[0], 'name': loci_name, 'length': length}]

        deck = genanki.Deck(20594000000 + m + 1, deck_title)
        decks.append(deck)

        print(f"Processing: {loci_key[0]:5}; Loci {m+1}/{len(loci_groups)}; {len(loci_entrys)} chars")

        # Create one cloze note for all characters in this loci group
        cloze_note = build_cloze_note(radical_key, guid_list[m], loci_entrys, loci_key, loci_name, loci_range)
        deck.add_note(cloze_note)

    # Create standard deck with individual notes ordered by loci
    print("\nBuilding standard deck...")
    standard_deck = genanki.Deck(20594999999, "Character List")

    # Add each character as a separate note, grouped by loci with next entry reference
    guid_list_verify = []
    for loci_key, loci_group in loci_groups.items():
        loci_entrys = loci_group["entries"]
        # Sort entries within each loci by position
        loci_entrys.sort(key=lambda x: int(x["position"]))

        for idx, entry in enumerate(loci_entrys):
            # Get next entry in the same loci, or None if this is the last one
            next_entry = loci_entrys[idx + 1] if idx + 1 < len(loci_entrys) else None
            standard_note = build_standard_note(entry, memo_data, next_entry)
            standard_deck.add_note(standard_note)
            guid_list_verify += [standard_note.guid]

    decks.append(standard_deck)
    print(f"Added {len(guid_list_verify)} standard notes to deck")

    # Verify GUID uniqueness
    guid_set = set(guid_list_verify)
    print(f"\nGUID Verification:")
    print(f"  Total notes: {len(guid_list_verify)}")
    print(f"  Unique GUIDs (set): {len(guid_set)}")
    if len(guid_list_verify) == len(guid_set):
        print(f"  ✓ All GUIDs are unique!")
    else:
        duplicates = len(guid_list_verify) - len(guid_set)
        print(f"  ✗ Warning: {duplicates} duplicate GUID(s) found!")

    package = genanki.Package(decks)
    package.media_files = glob.glob("loci/*.png")
    package.media_files += ["_LXGWWenKaiGBLite-Light.ttf", "_HanaMinA.otf", "_HanaMinB.otf"]
    audio_files = {pinyin_audio_filename(e["pinyin"]) for entrys in dict_entries.values() for e in entrys}
    package.media_files += [f"{AUDIO_DIR}/{f}" for f in audio_files if os.path.exists(f"{AUDIO_DIR}/{f}")]

    package.write_to_file('memo_anki.apkg')

    # # Generate memo_sets.xlsx
    # excelmemo_sets()
