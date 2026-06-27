import argparse
import csv
import heapq
import json
import logging
import math
import warnings
from pathlib import Path

logging.disable(logging.CRITICAL)
with warnings.catch_warnings():
    warnings.simplefilter("ignore", SyntaxWarning)
    import jieba.posseg
from hanzipy.dictionary import HanziDictionary


CHARACTER_COUNT = 3000
MAX_WORD_RANK = 35000
OUTSIDE_CHARACTER_WEIGHT = 2.0
HSK_UNLISTED_MULTIPLIER = 5.0
HSK_LEVEL_STEP = 0.25
NAME_FLAGS = {"j", "nz"}
NAME_FLAG_PREFIXES = ("nr", "ns", "nt")
NAME_DEFINITION_MARKERS = ("surname ", "(name)", " company", " corporation", " group ltd", " organization", " agency", " society", "(society", " ministry", " university", " institute", " foundation", " committee", " television", " website", " brand", " empire", " city", " county", " province", " district", " township", " village", " prefecture", " municipality", " capital of", " island", " airport", " stadium", " river", " mountain", " lake", " country", " autonomous region", " emperor", " general", " warlord", " singer", " actor", " actress", " writer", " poet", " politician", " philosopher", " scientist", " painter", " composer", " artist", " calligrapher", " player", " pop group")
CAPITALIZED_NAME_DEFINITION_MARKERS = (" liquor", " train", " trains")
REFERENCE_PREFIXES = ("see ", "see also ", "variant of ", "old variant of ", "erhua variant of ", "japanese variant of ", "archaic variant of ", "erroneous variant of ", "also written ", "abbr. for ", "(tw) abbr. for ", "same as ")


parser = argparse.ArgumentParser(description="Select common words covering the most frequent Chinese characters.")
parser.add_argument("--commonness-weight", type=float, default=5.0, help="Favor common words over a shorter list; 0 favors the fewest words.")
parser.add_argument("--clean-definitions", action="store_true", help="Rewrite definitions with Qwen and reuse cached results.")
parser.add_argument("--llm-model", default="qwen-max", help="DashScope model used by --clean-definitions.")
parser.add_argument("--llm-batch-size", type=int, default=75, help="Definitions sent in each Qwen request.")
args = parser.parse_args()
COMMONNESS_WEIGHT = args.commonness_weight

dictionary = HanziDictionary()

with Path(__file__).resolve().parent.parent.joinpath("complete-hsk-vocabulary", "complete.min.json").open(encoding="utf-8") as hsk_file:
    hsk_data = json.load(hsk_file)
hsk_levels = {}
for entry in hsk_data:
    levels = [int(level[1:]) for level in entry["l"] if level[0] in {"n", "o"}]
    hsk_levels[entry["s"]] = min(levels)

word_ranks = {}
previous_frequency = None
for position, (word, raw_frequency) in enumerate(sorted(dictionary.word_freq.items(), key=lambda item: (-int(item[1]), item[0])), start=1):
    frequency = int(raw_frequency)
    if frequency != previous_frequency:
        current_rank = position
        previous_frequency = frequency
    word_ranks[word] = current_rank

target_characters = set()
for position in range(1, CHARACTER_COUNT + 1):
    try:
        target_characters.add(dictionary.get_character_in_frequency_list_by_position(position)["character"])
    except KeyError:
        if position == 2719:
            continue
        raise

candidates = []
for word in dictionary.word_freq.keys() | hsk_levels.keys():
    hsk_level = hsk_levels.get(word)
    frequency = int(dictionary.word_freq.get(word, 0))
    rank = word_ranks.get(word)
    if hsk_level is None and rank > MAX_WORD_RANK:
        continue
    characters = {character for character in word if "\u4e00" <= character <= "\u9fff"}
    covered_characters = characters & target_characters
    definitions = dictionary.dictionary_simplified.get(word)
    if covered_characters and definitions:
        word_flags = {token.flag for token in jieba.posseg.cut(word)}
        word_has_name_flag = any(flag in NAME_FLAGS or flag.startswith(NAME_FLAG_PREFIXES) for flag in word_flags)
        ordinary_senses = []
        for entry in definitions:
            if entry["pinyin"][:1].isupper() and word_has_name_flag:
                continue
            ordinary_senses += [sense for sense in entry["definition"].split("/") if not sense.lower().startswith(REFERENCE_PREFIXES) and not any(marker in sense.lower() for marker in NAME_DEFINITION_MARKERS) and not (entry["pinyin"][:1].isupper() and any(marker in sense.lower() for marker in CAPITALIZED_NAME_DEFINITION_MARKERS))]
        if ordinary_senses:
            definition = "/".join(dict.fromkeys(ordinary_senses))
            candidates += [{"word": word, "covered": covered_characters, "outside": characters - target_characters, "frequency": frequency, "rank": rank, "hsk_level": hsk_level, "definition": definition}]

covered_by_frequency_data = set().union(*(candidate["covered"] for candidate in candidates))
for character in target_characters - covered_by_frequency_data:
    definitions = dictionary.definition_lookup(character, script_type="simplified")
    definition = "; ".join(dict.fromkeys(entry["definition"] for entry in definitions))
    candidates += [{"word": character, "covered": {character}, "outside": set(), "frequency": int(dictionary.word_freq.get(character, 0)), "rank": word_ranks.get(character), "hsk_level": hsk_levels.get(character), "definition": definition}]

maximum_frequency = max(candidate["frequency"] for candidate in candidates)
for candidate in candidates:
    rarity = math.log(maximum_frequency / max(candidate["frequency"], 1)) / math.log(maximum_frequency)
    hsk_multiplier = 1 + HSK_LEVEL_STEP * (candidate["hsk_level"] - 1) if candidate["hsk_level"] is not None else HSK_UNLISTED_MULTIPLIER
    candidate["cost"] = (1 + COMMONNESS_WEIGHT * rarity + OUTSIDE_CHARACTER_WEIGHT * len(candidate["outside"])) * hsk_multiplier

uncovered_characters = target_characters.copy()
heap = []
for index, candidate in enumerate(candidates):
    gain = len(candidate["covered"])
    heapq.heappush(heap, (-gain / candidate["cost"], -candidate["frequency"], candidate["word"], index, gain))

selected = []
while uncovered_characters:
    negative_score, negative_frequency, word, index, previous_gain = heapq.heappop(heap)
    candidate = candidates[index]
    gain = len(candidate["covered"] & uncovered_characters)
    if gain != previous_gain:
        if gain:
            heapq.heappush(heap, (-gain / candidate["cost"], negative_frequency, word, index, gain))
        continue
    selected += [candidate]
    uncovered_characters -= candidate["covered"]

if args.clean_definitions:
    from qwen_api import OpenAIAPI

    cleanup_dir = Path(__file__).resolve().with_name("llm_definition")
    cleanup_dir.mkdir(exist_ok=True)
    cache_path = cleanup_dir.joinpath("definitions.json")
    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
    records = {candidate["word"]: {"definition": candidate["definition"], "rank": candidate["rank"] if candidate["rank"] is not None else "unranked", "hsk_level": candidate["hsk_level"] if candidate["hsk_level"] is not None else "unlisted"} for candidate in selected}
    pending_words = [word for word, record in records.items() if word not in cache or not isinstance(cache[word], dict) or cache[word].get("source_definition") != record["definition"] or cache[word].get("model") != args.llm_model or not isinstance(cache[word].get("definition"), str) or not cache[word]["definition"].strip()]
    system_prompt = """You are a Chinese-language lexicographer. Your task is to rewrite CC-CEDICT definitions into concise, learner-focused English glosses.

## INPUT
A JSON object mapping Chinese words to their raw dictionary entry and metadata.

## OUTPUT
Return ONLY a valid JSON object mapping every input word to a single nonempty English definition string.
- Keep every input key exactly as-is.
- Do not add, remove, or rename any keys.
- No explanations, no markdown, no wrapping — raw JSON only.

## RULES FOR WRITING EACH GLOSS

**General words:**
- Give the most common, concrete, everyday modern meaning.
- Usually one sense; add a second sense separated by "; " (never "/") only when both are essential to the word's core meaning.
- Strip: archaic meanings, literary senses, rare/specialized uses, redundant synonyms, proper-name senses (unless the word has no other use).
- Keep: grammatical function words (particles, aspect markers, measure words) with their grammatical label, e.g. "(aspect marker) completed action".

**Idioms (成语 and fixed set phrases — typically 4-character words):**
- Always provide BOTH meanings in the format: "lit. [literal]; fig. [figurative/idiomatic]"
- Derive the literal meaning from the component characters if not in the source definition.
- The figurative meaning is the actual usage; make it clear and natural.
- Example: 半途而废 → "lit. abandon halfway; fig. give up before finishing"

## EXAMPLES
Input:  {"吃": {"definition": "to eat/to have one's meal/to erase/...", ...}}
Output: {"吃": "eat"}

Input:  {"马上": {"definition": "at once/right away/immediately/...", ...}}
Output: {"马上": "immediately; right away"}

Input:  {"一石二鸟": {"definition": "lit. one stone two birds/fig. kill two birds with one stone", ...}}
Output: {"一石二鸟": "lit. one stone, two birds; fig. kill two birds with one stone"}"""

    print(f"Total definitions: {len(records)}; pending: {len(pending_words)}")
    if pending_words:
        client = OpenAIAPI(model=args.llm_model, logs_dir=cleanup_dir.joinpath("io"))
        for start in range(0, len(pending_words), args.llm_batch_size):
            batch_words = pending_words[start:start + args.llm_batch_size]
            batch = {word: records[word] for word in batch_words}
            batch_number = start // args.llm_batch_size + 1
            print(f"Streaming batch {batch_number:02d} (items {start + 1}-{start + len(batch_words)})...")
            result = client.chat_json_streamed([{"role": "system", "content": system_prompt}, {"role": "user", "content": json.dumps(batch, ensure_ascii=False)}])
            for word in batch_words:
                cleaned_definition = result.get(word)
                if isinstance(cleaned_definition, str) and cleaned_definition.strip():
                    cache[word] = {"source_definition": records[word]["definition"], "definition": cleaned_definition.strip(), "model": args.llm_model}
            temporary_cache_path = cache_path.with_suffix(".tmp")
            temporary_cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
            temporary_cache_path.replace(cache_path)
    for candidate in selected:
        cached = cache.get(candidate["word"])
        cached_definition = cached.get("definition") if isinstance(cached, dict) else None
        if isinstance(cached, dict) and cached.get("source_definition") == candidate["definition"] and cached.get("model") == args.llm_model and isinstance(cached_definition, str) and cached_definition.strip():
            candidate["definition"] = cached_definition.strip()

with Path(__file__).resolve().with_name("data_words.csv").open("w", encoding="utf-8", newline="") as csv_file:
    writer = csv.writer(csv_file)
    writer.writerow(["word", "rank", "hsk_level", "definition"])
    for candidate in sorted(selected, key=lambda candidate: (-candidate["frequency"], candidate["word"])):
        writer.writerow([candidate["word"], candidate["rank"] if candidate["rank"] is not None else "unranked", candidate["hsk_level"] if candidate["hsk_level"] is not None else "unlisted", candidate["definition"]])
