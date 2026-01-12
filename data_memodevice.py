import pandas
import numpy
import json

import matplotlib
import matplotlib.pyplot

import os

# import decomposer
from hanzipy.decomposer import HanziDecomposer

decomposer = HanziDecomposer()
# import dictionary
from hanzipy.dictionary import HanziDictionary

dictionary = HanziDictionary()

import pypinyin
from pypinyin.contrib.tone_convert import to_tone
from pypinyin import style
from pypinyin import Style, pinyin

import re

from pypinyin_dict.pinyin_data import ktghz2013, kmandarin_8105
kmandarin_8105.load()
# khanyupinlu.load()

_re_number = re.compile(r'\d')

gloss_list = {}
def_list = {}

# lst_percent = []
# for i in range(1, 3000):
#     try:
#         character = dictionary.get_character_in_frequency_list_by_position(i)
#         if dictionary.determine_if_simplfied_char(character["character"]):
#             lst_percent += [float(character["percentage"])]
#     except:
#         pass

# matplotlib.pyplot.plot(range(1, len(lst_percent) + 1), lst_percent)
# matplotlib.pyplot.show()

entries = []
with open("dictionary_char.jsonl", "r", encoding="utf-8") as file_obj:
    for json_line in file_obj:
        entry = json.loads(json_line)
        entries += [entry]
entries = entries[:]  # For testing
entries_dict = {entry["char"]: entry for entry in entries if "char" in entry}

with open("ids_dictionary.json", "r", encoding="utf-8") as file_obj:
    ids_dict = json.load(file_obj)


def get_pinyin(char: str) -> str:
    # entry = entries_dict.get(char, {}).get("pinyinFrequencies", [])
    # dong_pinyin = max(entry, key=lambda x: x['count'], default={}).get("pinyin", "")
    lazy_pinyin = pypinyin.lazy_pinyin(character["character"], style=pypinyin.Style.TONE)[0]

    # if pinyin != lazy_pinyin:
    #     print("Pinyin mismatch:", character["character"], pinyin)
    # if pinyin == "":
    #     pinyin = lazy_pinyin
    #     print("Pinyin missing in dictionary:", char, lazy_pinyin)
    # pinyin = lazy_pinyin

    return lazy_pinyin


def process_hint(hint: str) -> str:
    if not hint or "Phonosemantic compound" not in hint:
        return hint

    # Split by "Phonosemantic compound. " to handle cases where it appears
    parts = hint.split("Phonosemantic compound. ", 1)

    if len(parts) == 1:
        # "Phonosemantic compound" exists but not followed by ". "
        return hint

    prefix = parts[0]  # Content before "Phonosemantic compound."
    remaining = parts[1]  # Content after "Phonosemantic compound."

    # Pattern to match Chinese character followed by "represents the meaning/sound"
    def add_pinyin_to_char(match):
        char = match.group(1)
        role = match.group(2)  # "meaning" or "sound"

        # Get pinyin for the character
        try:
            char_pinyin = pypinyin.lazy_pinyin(char, style=pypinyin.Style.TONE)[0]
            return f"{char} ({char_pinyin}) represents the {role}"
        except:
            return match.group(0)  # Return original if pinyin lookup fails

    # Replace pattern: Chinese character followed by "represents the meaning/sound"
    processed_remaining = re.sub(r'(\S) represents the (meaning|sound)', add_pinyin_to_char, remaining)

    # Combine prefix (if any) with processed remaining part
    result = prefix + processed_remaining

    return result.strip()


with open("memo.json", "r", encoding="utf-8") as file_obj:
    memo_data = json.load(file_obj)

with open("translation/gloss_translation-qwen-max.json", "r", encoding="utf-8") as file_obj:
    gloss_list = json.load(file_obj)
with open("translation/norare-llm_defselection-qwen-max.json", "r", encoding="utf-8") as file_obj:
    def_list = json.load(file_obj)

if __name__ == "__main__":

    dictcharacters = []
    for i in range(1, 3000):
        try:
            character = dictionary.get_character_in_frequency_list_by_position(i)
            if dictionary.determine_if_simplfied_char(character["character"]):
                pinyin = get_pinyin(character["character"])
                # print(f'{i:04d}: {float(character["percentage"]):.2f}%')

                pinyin_initial = style.convert(pinyin, Style.INITIALS, strict=False)
                pinyin_final = style.convert(pinyin, Style.FINALS, strict=False, v_to_u=True)
                pinyin_tone = style.convert(pinyin, Style.FINALS_TONE3, strict=False, neutral_tone_with_five=True)[-1]
                if not _re_number.findall(pinyin_tone): pinyin_tone = "5"

                # find if there is a v in finals
                u_is_v = False
                if 'v' in pinyin_final:
                    u_is_v = True
                    pinyin_final = pinyin_final.replace('v', 'u')

                pinyin_info = {"pinyin": pinyin, "initial": pinyin_initial, "final": pinyin_final, "tone": pinyin_tone, "u_is_v": u_is_v}

                # gloss = entries_dict[character["character"]]["gloss"]
                if character["character"] not in gloss_list:
                    print("Character/Translation missing from gloss_list:", character["character"])
                gloss = gloss_list.get(character["character"], {}).get("gloss_en", "")
                gloss_fr = gloss_list.get(character["character"], {}).get("gloss_fr", "")

                ids_components = ids_dict.get(character["character"], {}).get("components", [])
                # ids_gloss = {ids: gloss_list.get(ids, {}).get("gloss_en", "") for ids in ids_components}
                # ids_gloss_fr = {ids: gloss_list.get(ids, {}).get("gloss_fr", "") for ids in ids_components}

                subcomponents = {ids: gloss_list.get(ids, {}).get("gloss_en", "") for ids in ids_components}
                subcomponents_fr = {ids: gloss_list.get(ids, {}).get("gloss_fr", "") for ids in ids_components}
                subcomponents |= {sub: gloss_list.get(sub, {}).get("gloss_en", "") for sub in decomposer.decompose(character["character"], 2)["components"] if sub in gloss_list}
                subcomponents_fr |= {sub: gloss_list.get(sub, {}).get("gloss_fr", "") for sub in decomposer.decompose(character["character"], 2)["components"] if sub in gloss_list}

                dictcharacter = {
                    "character": character["character"],
                    "pinyin": pinyin_info,
                    "gloss": gloss,
                    "gloss_fr": gloss_fr,
                    "subcomponents": subcomponents,
                    "subcomponents_fr": subcomponents_fr,
                    # "ids_components": ids_components,
                    # "ids_gloss": ids_gloss,
                    # "ids_gloss_fr": ids_gloss_fr,
                    "coverage": float(character["percentage"]),
                    "rank": i,
                }

                if "hint" in entries_dict[character["character"]]:
                    hint = entries_dict[character["character"]]["hint"]
                    dictcharacter["hint"] = process_hint(hint)
                else:
                    dictcharacter["hint"] = ""
                dictcharacters += [dictcharacter]

                # TODO comment
                # if entries_dict.get(character["character"], {}).get("gloss", "") != "":
                #     gloss_list[character["character"]] = {}
                #     gloss_list[character["character"]]["gloss_en"] = entries_dict[character["character"]]["gloss"]
                #     gloss_list[character["character"]]["gloss_fr"] = ""

                # for ids_component in ids_components:
                #     if entries_dict.get(ids_component, {}).get("gloss", "") != "":
                #         gloss_list[ids_component] = {}
                #         gloss_list[ids_component]["gloss_en"] = entries_dict[ids_component]["gloss"]
                #         gloss_list[ids_component]["gloss_fr"] = ""

                # for components in decomposer.decompose(character["character"], 2)["components"]:
                #     if entries_dict.get(components, {}).get("gloss", "") != "":
                #         gloss_list[components] = {}
                #         gloss_list[components]["gloss_en"] = entries_dict[components]["gloss"]
                #         gloss_list[components]["gloss_fr"] = ""

                # def_list[character["character"]] = {}
                # def_list[character["character"]]["def_en"] = character.get("meaning", "")
                # def_list[character["character"]]["def_fr"] = ""
                # TODO comment

        except:
            pass

    # with open("translation/gloss_translation-qwen-max.json", "r", encoding="utf-8") as file_obj:
    #     gloss_list = json.load(file_obj)
    #     # json.dump(gloss_list, file_obj, ensure_ascii=False, indent=4)
    # with open("translation/norare-llm_defselection-qwen-max.json", "r", encoding="utf-8") as file_obj:
    #     def_list = json.load(file_obj)
    #     # json.dump(def_list, file_obj, ensure_ascii=False, indent=4)

    print("Number of character entry:", len(dictcharacters))

    for i in range(len(dictcharacters)):
        char = dictcharacters[i]["character"]
        components = entries_dict[char]["components"]
        if len(components) > 0:
            for component in components:
                if "hint" in component and component["hint"] is None: component["hint"] = ""

                component["gloss"], component["gloss_fr"] = "", ""
                if component["character"] in gloss_list:
                    component["gloss"] = gloss_list.get(component["character"], {}).get("gloss_en", "")
                    component["gloss_fr"] = gloss_list.get(component["character"], {}).get("gloss_fr", "")

                # subcomponents = [{sub: gloss_list.get(sub, {}).get("gloss_en", "")} for sub in decomposer.decompose(component["character"], 2)["components"] if sub in gloss_list]
                # component["subcomponents"] = subcomponents
                # subcomponents = [{sub: gloss_list.get(sub, {}).get("gloss_fr", "")} for sub in decomposer.decompose(component["character"], 2)["components"] if sub in gloss_list]
                # component["subcomponents_fr"] = subcomponents_fr
        else:
            components += [{"character": char, "hint": ""} for char in decomposer.decompose(char, 2)["components"]]

            for component in components:
                component["gloss"], component["gloss_fr"] = "", ""
                if component["character"] in gloss_list:
                    component["gloss"] = gloss_list.get(component["character"], {}).get("gloss_en", "")
                    component["gloss_fr"] = gloss_list.get(component["character"], {}).get("gloss_fr", "")

                # subcomponents = [{sub: gloss_list.get(sub, {}).get("gloss_en", "")} for sub in decomposer.decompose(component["character"], 2)["components"] if sub in gloss_list]
                # component["subcomponents"] = subcomponents
                # subcomponents_fr = [{sub: gloss_list.get(sub, {}).get("gloss_fr", "")} for sub in decomposer.decompose(component["character"], 2)["components"] if sub in gloss_list]
                # component["subcomponents_fr"] = subcomponents_fr

        dictcharacters[i]["components"] = components

        # subcomponents = {sub: gloss_list.get(sub, {}).get("gloss_en", "") for sub in decomposer.decompose(char, 2)["components"] if sub in gloss_list}
        # dictcharacters[i]["subcomponents"] = subcomponents
        # subcomponents_fr = {sub: gloss_list.get(sub, {}).get("gloss_fr", "") for sub in decomposer.decompose(char, 2)["components"] if sub in gloss_list}
        # dictcharacters[i]["subcomponents_fr"] = subcomponents_fr

    for i in range(len(dictcharacters)):
        components = dictcharacters[i]["components"]
        components_str = ""

        for component in components:
            components_str += f"- {component['character']} ({component['gloss']})"
            if "hint" in component and (component["hint"] != "" and component["hint"] != "None" and component["hint"] != None):
                components_str += f"[Hint: {component['hint']}]"
            components_str += "\n"

            if "subcomponents" in component:
                if len(component["subcomponents"]) == 1 and component["character"] in component["subcomponents"][0]:
                    continue

                components_str += f"   ·"
                for subcomponent in component["subcomponents"]:
                    sub_key, sub_value = list(subcomponent.items())[0]
                    components_str += f"{sub_key}({sub_value}); "
                components_str += "\n"

        dictcharacters[i]["components_str"] = components_str

    for i in range(len(dictcharacters)):
        components = dictcharacters[i]["components"]
        components_str = ""

        for component in components:
            components_str += f"- {component['character']} ({component['gloss_fr'] if 'gloss_fr' in component else component['gloss']})"
            if "hint" in component and (component["hint"] != "" and component["hint"] != "None" and component["hint"] != None):
                components_str += f"[Hint: {component['hint']}]"
            components_str += "\n"

            if "subcomponents_fr" in component:
                if len(component["subcomponents_fr"]) == 1 and component["character"] in component["subcomponents_fr"][0]:
                    continue

                components_str += f"   ·"
                for subcomponent in component["subcomponents_fr"]:
                    sub_key, sub_value = list(subcomponent.items())[0]
                    components_str += f"{sub_key}({sub_value}); "
                components_str += "\n"

        dictcharacters[i]["components_strfr"] = components_str

    characters = [char["character"] for char in dictcharacters]
    radical = [decomposer.decompose(character, 2)["components"][0] for character in characters]
    for i in range(len(radical)):
        radical[i] = "◎" if radical[i] == "No glyph available" else radical[i]

    by_radical = {}
    for i in range(len(characters)):
        char_radical = radical[i]
        if char_radical not in by_radical:
            by_radical[char_radical] = []

        character_entry = dictcharacters[i]
        # character_entry["rank"] = i + 1
        by_radical[char_radical] += [character_entry]

    for radical in by_radical:
        for ii, char in enumerate(by_radical[radical]):
            char["position"] = ii + 1

    with pandas.ExcelWriter(f"memo_excel.xlsx") as writer:
        # Radicals sheet by frequency
        by_radical111 = dict(sorted(by_radical.items(), key=lambda item: len(item[1]), reverse=True))
        freq_sheet = {
            "Rank": [len(by_radical111[radical]) for radical in by_radical111],
            "Radical": [radical for radical in by_radical111],
            "Meaning": [entries_dict.get(radical, {}).get("gloss", "None") for radical in by_radical111],
        }
        freq_sheet = pandas.DataFrame(freq_sheet)
        freq_sheet.to_excel(writer, sheet_name="Radicals", index=False)
        writer.sheets["Radicals"].autofit()

        radical_sheet = {
            "Rank": [entry["rank"] for radical in by_radical for entry in by_radical[radical]],
            "Character": [entry["character"] for radical in by_radical for entry in by_radical[radical]],
            "Pinyin": [entry["pinyin"]["pinyin"] for radical in by_radical for entry in by_radical[radical]],
            "Meaning": [entry["gloss_fr"] for radical in by_radical for entry in by_radical[radical]],
        }
        radical_sheet = pandas.DataFrame(radical_sheet)
        radical_sheet.to_excel(writer, sheet_name="All", index=False)
        writer.sheets["All"].autofit()

        by_radical = dict(sorted(by_radical.items(), key=lambda item: len(item[1]), reverse=True))

        # if size is smaller than 14, merdge the ones with the smame size together
        merdge_keys = ["".join([k for k in list(by_radical.keys()) if len(by_radical[k]) == kk]) for kk in range(15, 0, -1)]

        for mk in merdge_keys:
            by_radical[mk] = []
            for k in mk:
                by_radical[mk] += by_radical[k]
                del by_radical[k]

        for radical in by_radical:
            if radical not in merdge_keys[0:4]:
                for ii, char in enumerate(by_radical[radical]):
                    char["position"] = ii + 1

        # memo_data
        for radical in by_radical:
            for entry in by_radical[radical]:
                entry["memo_str"] = ""
                entry["memo_data"] = {}

                if entry["pinyin"]["initial"] != "":
                    entry["memo_data"]["initial"] = memo_data["initials"][entry["pinyin"]["initial"]]
                    entry["memo_str"] += f'Initial: {entry["memo_data"]["initial"]} - [{entry["pinyin"]["initial"]}]\n'

                if entry["pinyin"]["final"] in memo_data["finals"]:
                    entry["memo_data"]["final"] = f'{memo_data["finals"][entry["pinyin"]["final"]]["action"]}'
                    entry["memo_str"] += f'  Final: {entry["memo_data"]["final"]} - [{entry["pinyin"]["final"]}]\n'
                else:
                    entry["memo_data"]["final"] = memo_data["initials"][entry["pinyin"]["final"]]
                    entry["memo_str"] += f'  Final: {entry["memo_data"]["final"]} - [{entry["pinyin"]["final"]}]\n'

                entry["memo_data"]["tone"] = memo_data["tones"][entry["pinyin"]["tone"]]
                entry["memo_str"] += f'   Tone: {entry["memo_data"]["tone"]["view"]} - [{entry["pinyin"]["tone"]}]\n'
                if entry["pinyin"]["u_is_v"]:
                    entry["memo_data"]["u_is_v"] = memo_data["tones"]["6"]["view"]

        by_radical_before_sort = by_radical.copy()
        # sort by number of entries per radical
        by_radical = dict(sorted(by_radical.items(), key=lambda item: len(item[1]), reverse=False))
        with open("data_memodevice.json", "w", encoding="utf-8") as file_obj:
            json.dump(by_radical, file_obj, ensure_ascii=False, indent=4)

        print("Number of radical entry:", len(by_radical))

        # rate = [numpy.mean([entry["rank"] for entry in by_radical[radical]]) for radical in by_radical]
        # by_radical = dict(sorted(by_radical.items(), key=lambda item: numpy.mean([entry["rank"] for entry in item[1]])))

        for radical in by_radical:
            radical_sheet = {
                "Position": [entry["position"] for entry in by_radical[radical]],
                "Character": [entry["character"] for entry in by_radical[radical]],
                "Pinyin": [entry["pinyin"]["pinyin"] for entry in by_radical[radical]],
                "Meaning": [entry["gloss_fr"] for entry in by_radical[radical]],
                "Memo": [entry["memo_str"].replace("\n", "\r\n") for entry in by_radical[radical]],
                "Components": [entry["components_strfr"].replace("\n", "\r\n") for entry in by_radical[radical]],
                "Rank": [entry["rank"] for entry in by_radical[radical]],
                # "Components": [str(entry["components_str"]) for entry in by_radical[radical]],
            }

            sheet_name = radical[0]
            radical_sheet = pandas.DataFrame(radical_sheet)
            radical_sheet.to_excel(writer, sheet_name=sheet_name, index=False)

            wrap_fmt = writer.book.add_format({'text_wrap': True})
            writer.sheets[sheet_name].set_column('E:E', 40, wrap_fmt)
            writer.sheets[sheet_name].set_column('F:F', 40, wrap_fmt)

            writer.sheets[sheet_name].autofit()
            # Set the police size of Character column to 20
            writer.sheets[sheet_name].set_column('B:B', None, writer.book.add_format({'font_size': 42}))
            writer.sheets[sheet_name].set_column('C:C', None, writer.book.add_format({'font_size': 12}))
