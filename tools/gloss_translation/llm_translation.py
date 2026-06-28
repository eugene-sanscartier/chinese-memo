import json
import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
CACHE_DIR = ROOT_DIR / "data" / "cache" / "gloss_translation"
sys.path.insert(0, str(ROOT_DIR))
from qwen_api import OpenAIAPI


DASHSCOPE_API_KEY = 'sk-2cbe14e057f14615b670eda42a55af9b'


def main_gloss():
    system_prompt = """You are a professional specializing in Chinese characters and their meanings. Your task is to give French glosses to chinese character.

## CRITICAL REQUIREMENTS:
1. Return ONLY valid JSON with the EXACT same structure.
2. Fill ONLY the `gloss_fr` field with its French glosses.
3. You MUST NOT add, remove, or modify any input entries - except the `gloss_fr` field that you are expected to fill.
4. Do not add explanatory notes, Unicode references, or additional context.

## Output format:
EXAMPLE INPUT:
{
    "一": {"gloss_en": "one", "gloss_fr": "un", "gloss_review": "", "atlgloss_fr": "", "reason_fr": ""},
}
EXAMPLE OUTPUT:
{
    "一": {"gloss_en": "one", "gloss_fr": "un", "gloss_review": "G", "atlgloss_fr": "un", "reason_fr": "Traduction directe du sens du cheractère."},
}

## Guidelines:
- Maintain original formatting (brackets, punctuation, parenthetical notes).
- Use lowercase for general descriptors unless it's a proper noun.
- Use the meaning of the character to help translate `gloss_en`, always provide natural French glosses.

Give the following character glosses:

"""

    with open(CACHE_DIR / "translation_review" / "bad_translations.json", "r", encoding="utf-8") as file_obj:
        gloss_list: dict = json.load(file_obj)
    for char, gloss in gloss_list.items():
        del gloss["char"]
        gloss["gloss_fr"] = ""

    client = OpenAIAPI(model="qwen-plus", api_key=DASHSCOPE_API_KEY, logs_dir=CACHE_DIR / "llm_io")

    out_dir = CACHE_DIR / "llm_translation"
    os.makedirs(out_dir, exist_ok=True)

    records_keys = list(gloss_list)

    merged_path = out_dir / "gloss_translation.json"
    if os.path.exists(merged_path):
        try:
            with open(merged_path, "r", encoding="utf-8") as f_in:
                merged = json.load(f_in)
        except Exception:
            print(f"Warning: Failed to load existing merged file at {merged_path}. Starting fresh.")
            merged = {}
    else:
        merged = {}

    done_keys = set(merged.keys()) if isinstance(merged, dict) else set()
    pending_keys = [r for r in records_keys if r not in done_keys]

    print(f"Total gloss to be translated: {len(records_keys)}; pending: {len(pending_keys)}")

    batch_size = 5
    for i in range(0, len(pending_keys), batch_size):
        batch_idx = i // batch_size + 1
        batch = {k: gloss_list[k] for k in pending_keys[i:i + batch_size]}

        user_prompt = json.dumps(batch, ensure_ascii=False)
        messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]

        print(f"  Streaming batch {batch_idx:02d} (items {i+1}-{i+len(batch)}) {batch_idx*batch_size/len(records_keys)*100:.1f}% done...")
        result_batch = client.chat_json_streamed(messages, temperature=1.1, thinking=True, include_usage=True)

        if isinstance(result_batch, dict):
            merged.update(result_batch)

        with open(merged_path, "w", encoding="utf-8") as f_out:
            json.dump(merged, f_out, ensure_ascii=False, indent=4)


def main_gloss_review():
    system_prompt = """You are a professional specializing in Chinese characters and their meanings. Your task is to give French glosses to Chinese characters.

## CRITICAL REQUIREMENTS:
1. Return ONLY valid JSON with the EXACT same structure.
2. Fill ONLY `gloss_fr`, `gloss_review`, `atlgloss_fr`, and `reason_fr`.
3. You MUST NOT add, remove, or modify any input entries—except the `gloss_fr`, `gloss_review`, `atlgloss_fr`, and `reason_fr` fields that you are expected to fill.
4. Do not add explanatory notes, Unicode references, or additional context.

# Example format:
EXAMPLE INPUT:
{
    "一": {"gloss_en": "one", "gloss_fr": "un", "gloss_review": "", "atlgloss_fr": "", "reason_fr": ""},
}
EXAMPLE OUTPUT:
{
    "一": {"gloss_en": "one", "gloss_fr": "un", "gloss_review": "G", "atlgloss_fr": "un", "reason_fr": "Traduction directe du sens du character."},
}

## Guidelines:
- Maintain original formatting (brackets, punctuation, parenthetical notes).
- Use lowercase for general descriptors unless it's a proper noun.
- Use the character gloss, meaning, and name to translate the English gloss to French.
- Fill `gloss_review` with "G" if the gloss is good, or "B" if the gloss is bad and needs to be fixed.
- Fill `atlgloss_fr` with an improved version of the `gloss_fr` if the original gloss is bad, or the same as `gloss_fr` if it's already good.
- Fill `reason_fr` with a brief reason for why the gloss is bad or why it is really good.

The following glosses have been translated; enhance them when needed. They may also contain inaccuracies or errors.
Review the following character glosses:

"""

    with open(CACHE_DIR / "gloss_translation-good.json", "r", encoding="utf-8") as file_obj:
        gloss_list: dict = json.load(file_obj)
    for char, gloss in gloss_list.items():
        gloss["gloss_review"] = ""
        gloss["atlgloss_fr"] = ""
        gloss["reason_fr"] = ""

    client = OpenAIAPI(model="qwen3.5-plus", api_key=DASHSCOPE_API_KEY, logs_dir=CACHE_DIR / "llm_io")

    out_dir = CACHE_DIR / "llm_translation"
    os.makedirs(out_dir, exist_ok=True)

    records_keys = list(gloss_list)

    merged_path = out_dir / "gloss_translation.json"
    if os.path.exists(merged_path):
        try:
            with open(merged_path, "r", encoding="utf-8") as f_in:
                merged = json.load(f_in)
        except Exception:
            print(f"Warning: Failed to load existing merged file at {merged_path}. Starting fresh.")
            merged = {}
    else:
        merged = {}

    done_keys = set(merged.keys()) if isinstance(merged, dict) else set()
    pending_keys = [r for r in records_keys if r not in done_keys]

    print(f"Total gloss to be translated: {len(records_keys)}; pending: {len(pending_keys)}")

    batch_size = 5
    for i in range(0, len(pending_keys), batch_size):
        batch_idx = i // batch_size + 1
        batch = {k: gloss_list[k] for k in pending_keys[i:i + batch_size]}

        user_prompt = json.dumps(batch, ensure_ascii=False)
        messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]

        print(f"Streaming batch {batch_idx:02d}; this done {(i+1)}/{(len(pending_keys))} (items {i+1}-{i+len(batch)}) at {batch_idx*batch_size/len(records_keys)*100:.1f}% done... total done: {(i+1+len(done_keys))/(len(pending_keys)+len(done_keys))*100:.1f}%,")
        result_batch = client.chat_json_streamed(messages, temperature=1.1, thinking=True, include_usage=True)

        try:
            if isinstance(result_batch, dict):
                merged.update(result_batch)

            with open(merged_path, "w", encoding="utf-8") as f_out:
                json.dump(merged, f_out, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"Error while updating merged results: {e}")
            continue


def main_definitions():
    system_prompt = """You are a professional translator specializing in Chinese characters and their meanings. Your task is to translate character definitions from English to French.

CRITICAL REQUIREMENTS:
Return ONLY valid JSON with the EXACT same structure as the input.
Fill ONLY the def_fr field with its French translations.
You MUST NOT add, remove, or modify any input entries — except the def_fr field that you are expected to fill.
Do not add explanatory notes, Unicode references, or additional context.
Output format:
Return ONLY valid JSON with the EXACT same structure as input:
EXAMPLE INPUT:
{
"的": {"def_en": "(possessive particle)/of, really and truly, aim/clear", "def_fr": ""},
"一": {"def_en": "one/1/single/a(n)", "def_fr": ""},
"是": {"def_en": "is/are/am/yes/to be", "def_fr": ""}
}
EXAMPLE OUTPUT:
{
"的": {"def_en": "(possessive particle)/of, really and truly, aim/clear", "def_fr": "[particule possessive]/de, vraiment, but/clair"},
"一": {"def_en": "one/1/single/a(n)", "def_fr": "un/1/seul/une"},
"是": {"def_en": "is/are/am/yes/to be", "def_fr": "est/sont/suis/oui/être"}
}

Translation guidelines:
For grammatical categories (e.g., (possessive particle)), translate to natural French equivalents and keep the same punctuation and parentheses.
For slash-separated senses (e.g., one/1/single/a(n)), provide slash-separated French equivalents in the same order.
Preserve original formatting (slashes, brackets, parentheses, punctuation, and any ordering).
Use lowercase for general descriptors unless it's a proper noun.
Translate parentheses and parenthetical notes accurately and keep them attached to the corresponding sense.
For complex or compound English definitions, translate the full meaning faithfully and concisely.
RULES:
Keys MUST be the Chinese characters from the input.
Never remove or add entries.
Never change def_en values or the character keys — only set def_fr.
Translate the following definitions:
"""
    with open(CACHE_DIR / "definitions.json", "r", encoding="utf-8") as file_obj:
        definitions_list: dict = json.load(file_obj)

    client = OpenAIAPI(model="qwen-max", api_key=DASHSCOPE_API_KEY, logs_dir=CACHE_DIR / "llm_io")

    out_dir = CACHE_DIR / "llm_translation"
    os.makedirs(out_dir, exist_ok=True)

    records_keys = list(definitions_list)

    merged_path = out_dir / "definitions_translation.json"
    if os.path.exists(merged_path):
        try:
            with open(merged_path, "r", encoding="utf-8") as f_in:
                merged = json.load(f_in)
        except Exception:
            print(f"Warning: Failed to load existing merged file at {merged_path}. Starting fresh.")
            merged = {}
    else:
        merged = {}

    done_keys = set(merged.keys()) if isinstance(merged, dict) else set()
    pending_keys = [r for r in records_keys if r not in done_keys]

    print(f"Total definitions to be translated: {len(records_keys)}; pending: {len(pending_keys)}")

    batch_size = 75
    for i in range(0, len(pending_keys), batch_size):
        batch_idx = i // batch_size + 1
        batch = {k: definitions_list[k] for k in pending_keys[i:i + batch_size]}

        user_prompt = json.dumps(batch, ensure_ascii=False)
        messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]

        print(f"  Streaming batch {batch_idx:02d} (items {i+1}-{i+len(batch)})...")
        result_batch = client.chat_json_streamed(messages, temperature=1.2)

        if isinstance(result_batch, dict):
            merged.update(result_batch)

        with open(merged_path, "w", encoding="utf-8") as f_out:
            json.dump(merged, f_out, ensure_ascii=False, indent=4)


if __name__ == "__main__":
    # main_gloss()
    main_gloss_review()
    # main_definitions()
