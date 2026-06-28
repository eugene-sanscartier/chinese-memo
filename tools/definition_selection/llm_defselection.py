import json
import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
CACHE_DIR = ROOT_DIR / "data" / "cache" / "definition_selection"
SNAPSHOTS_DIR = CACHE_DIR / "snapshots"
sys.path.insert(0, str(ROOT_DIR))
from qwen_api import OpenAIAPI


DASHSCOPE_API_KEY = 'sk-2cbe14e057f14615b670eda42a55af9b'


# with open("definitions.json", "r", encoding="utf-8") as file_obj:
#     definitions_list: dict = json.load(file_obj)
with open(SNAPSHOTS_DIR / "onev2-llm_defselection.json", "r", encoding="utf-8") as file_obj:
    definitions_list: dict = json.load(file_obj)
for char, defs in definitions_list.items():
    if "def_fr" in defs: del defs["def_fr"]


def main_defselection():
    system_prompt = """You are a Chinese language expert specializing in analyzing character definitions from CC-CEDICT. Your task is to identify and remove the LEAST COMMON or OBSOLETE definitions from Chinese character entries, keeping only the most frequently used modern meanings.

CRITICAL REQUIREMENTS:
1. Return ONLY valid JSON with the EXACT same structure as the input
2. For each character, analyze the definitions in def_en and REMOVE the least common/archaic meanings
3. Keep the most common, practical, and modern definitions
4. Preserve the original formatting (slashes, commas, parentheses)
5. Do NOT add, remove, or modify character keys
6. If a character has only one definition or all definitions are equally common, keep it unchanged

DEFINITION ANALYSIS GUIDELINES:
- Prioritize modern usage over archaic/literary meanings
- Keep grammatical particles and function word meanings (e.g., "possessive particle", "modal particle")
- Keep the most frequently encountered meanings in contemporary Chinese
- Remove obscure literary definitions, archaic meanings, or highly specialized senses
- For characters with multiple comma-separated definition groups, remove the entire group that is least common
- Preserve slash-separated alternatives within the same semantic group

INPUT STRUCTURE:
{
  "的": {"def_en": "(possessive particle)/of, really and truly, aim/clear"},
  "一": {"def_en": "one/1/single/a(n)"},
  "了": {"def_en": "(modal particle)/(completed action marker), to know/understand, clear, look afar from high place"}
}

OUTPUT STRUCTURE (with least common definitions removed):
{
  "的": {"def_en": "(possessive particle)/of"},
  "一": {"def_en": "one/1/single/a(n)"},
  "了": {"def_en": "(modal particle)/(completed action marker)"}
}

EXAMPLES:
- "的": Remove "really and truly, aim/clear" → Keep "(possessive particle)/of"
- "了": Remove "to know/understand, clear, look afar from high place" → Keep "(modal particle)/(completed action marker)"
- "在": Keep "(located) at/in/exist" → No change (all common)
- "人": Keep "man/person/people" → No change (all common)

RULES:
1. Character keys MUST remain exactly the same
2. Only modify the def_en values by removing least common definitions
3. Never return an empty def_en
4. Preserve the order and formatting of remaining definitions
5. Return valid JSON only, no explanations

Process the following character definitions:"""

    system_prompt = """You are a Chinese language expert. Your task is to simplify CC-CEDICT character definitions by keeping ONLY the most common, modern meaning.

TASK:
For each Chinese character, keep only the most frequently used definition that a learner would encounter in everyday modern Chinese. Remove archaic, literary, or rarely-used meanings.

RULES:
1. Return ONLY valid JSON with the exact same structure as input
2. Keep only the most common/useful definition (1 max per character)
3. Preserve original formatting (slashes between alternatives, parentheses for grammar notes)
4. Never return empty def_en
5. Do not add or remove character keys

WHAT TO KEEP:
- Primary grammatical functions (particles, markers)
- Most common concrete meanings
- Meanings learners encounter daily

WHAT TO REMOVE:
- Archaic or literary meanings
- Rare/specialized senses
- Redundant alternatives (e.g., "to know/to understand/to know" → pick one)
- Extended metaphorical meanings rarely used alone

Process the following:"""

    client = OpenAIAPI(model="qwen-max", api_key=DASHSCOPE_API_KEY, logs_dir=CACHE_DIR / "llm_io")

    out_dir = CACHE_DIR / "llm_defselection"
    os.makedirs(out_dir, exist_ok=True)

    records_keys = list(definitions_list)

    merged_path = out_dir / "llm_defselection.json"
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

    print(f"Total definitions to be processed: {len(records_keys)}; pending: {len(pending_keys)}")

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
    # main()
    main_defselection()
