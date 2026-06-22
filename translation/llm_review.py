import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from qwen_api import OpenAIAPI


DASHSCOPE_API_KEY = 'sk-2cbe14e057f14615b670eda42a55af9b'


def main_gloss_review():
    system_prompt = """You are a professional specializing in Chinese characters and their meanings. Your task is to eveluate and review French glosses of Chinese character.

## CRITICAL REQUIREMENTS:
1. Return ONLY valid JSON with the EXACT same structure.
2. Fill ONLY the `gloss_review` field with `good` or `bad` based.
3. You MUST NOT add, remove, or modify any input entries - except the `gloss_review` field that you are expected to fill.
4. Do not add explanatory notes, Unicode references, or additional context.

# Output format:
EXAMPLE INPUT:
{
  "余": {"gloss_en": "I", "gloss_fr": "Je", "gloss_review": ""},
  "𠬝": {"gloss_en": "subdue", "gloss_fr": "soumettre", "gloss_review": ""},
  "刻": {"gloss_en": "carve", "gloss_fr": "graver", "gloss_review": ""},
  "敫": {"gloss_en": "shining light", "gloss_fr": "lueur éclatante", "gloss_review": ""},
  "夺": {"gloss_en": "take by force", "gloss_fr": "prendre par la force", "gloss_review": ""},
  "踪": {"gloss_en": "footprints", "gloss_fr": "traces de pied", "gloss_review": ""},
  "躺": {"gloss_en": "lie down", "gloss_fr": "être allongé", "gloss_review": ""},
  "邪": {"gloss_en": "evil", "gloss_fr": "maléfique", "gloss_review": ""},
  "抛": {"gloss_en": "throw (away)", "gloss_fr": "jeter", "gloss_review": ""},
  "撞": {"gloss_en": "knock against", "gloss_fr": "heurter", "gloss_review": ""},
  "驰": {"gloss_en": "go quickly or swiftly", "gloss_fr": "galoper, filer", "gloss_review": ""}
  "扣": {"gloss_en": "knock", "gloss_fr": "attacher, boutonner", "gloss_review": ""},
}
EXAMPLE OUTPUT:
{
  "余": {"gloss_en": "I", "gloss_fr": "Je", "gloss_review": "bad"},
  "𠬝": {"gloss_en": "subdue", "gloss_fr": "soumettre", "gloss_review": "good"},
  "刻": {"gloss_en": "carve", "gloss_fr": "graver", "gloss_review": "good"},
  "敫": {"gloss_en": "shining light", "gloss_fr": "lueur éclatante", "gloss_review": "good"},
  "夺": {"gloss_en": "take by force", "gloss_fr": "prendre par la force", "gloss_review": "good"},
  "踪": {"gloss_en": "footprints", "gloss_fr": "traces de pied", "gloss_review": "good"},
  "躺": {"gloss_en": "lie down", "gloss_fr": "être allongé", "gloss_review": "good"},
  "邪": {"gloss_en": "evil", "gloss_fr": "maléfique", "gloss_review": "good"},
  "抛": {"gloss_en": "throw (away)", "gloss_fr": "jeter", "gloss_review": "good"},
  "撞": {"gloss_en": "knock against", "gloss_fr": "heurter", "gloss_review": "good"},
  "驰": {"gloss_en": "go quickly or swiftly", "gloss_fr": "galoper, filer", "gloss_review": "good"}
  "扣": {"gloss_en": "knock", "gloss_fr": "attacher, boutonner", "gloss_review": "good"},
}

## Guidelines:
- Strictly following the requirements and guidelines above.
- The folowing glosses have been translated, but may contain inaccuracy.
- Please review and evaluate that the French glosses (provided `gloss_fr`) contain no translation error, is accurate, natural, and represent the meaning of the character.

Review and evaluate the following character glosses:

"""

    with open("translation_review/bad_translations.json", "r", encoding="utf-8") as file_obj:
        gloss_list: dict = json.load(file_obj)
    for gloss in gloss_list.values():
        gloss["gloss_review"] = ""

    client = OpenAIAPI(model="qwen-max", api_key=DASHSCOPE_API_KEY)

    out_dir = "googletranslation_review"
    os.makedirs(out_dir, exist_ok=True)

    records_keys = list(gloss_list)[:]

    merged_path = os.path.join(out_dir, "gloss_translation.json")
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

    batch_size = 250
    for i in range(0, len(pending_keys), batch_size):
        batch_idx = i // batch_size + 1
        batch = {k: gloss_list[k] for k in pending_keys[i:i + batch_size]}

        user_prompt = json.dumps(batch, ensure_ascii=False)
        messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]

        print(f"  Streaming batch {batch_idx:02d} (items {i+1}-{i+len(batch)})...")
        result_batch = client.chat_json_streamed(messages, temperature=1.1)

        if isinstance(result_batch, dict):
            merged.update(result_batch)

        with open(merged_path, "w", encoding="utf-8") as f_out:
            json.dump(merged, f_out, ensure_ascii=False, indent=4)


def split_bad3good():
    with open("gloss_translation-thinking.json", "r", encoding="utf-8") as f_in:
        merged = json.load(f_in)

    good = {k: v for k, v in merged.items() if v.get("gloss_review") == "G"}
    bad = {k: v for k, v in merged.items() if v.get("gloss_review") == "B"}

    with open("gloss_translation-thinking-G.json", "w", encoding="utf-8") as f_good:
        json.dump(good, f_good, ensure_ascii=False, indent=4)

    with open("gloss_translation-thinking-B.json", "w", encoding="utf-8") as f_bad:
        json.dump(bad, f_bad, ensure_ascii=False, indent=4)


if __name__ == "__main__":
    # main_gloss_review()
    split_bad3good()
