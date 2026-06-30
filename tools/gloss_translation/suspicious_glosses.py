import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import random
import sys
from pathlib import Path
from tqdm import tqdm

ROOT_DIR = Path(__file__).resolve().parents[2]
CACHE_DIR = ROOT_DIR / "data" / "cache" / "gloss_translation" / "suspicious_gloss_audit"
GLOSS_PATH = ROOT_DIR / "data" / "source" / "authored" / "gloss.json"
STATE_PATH = CACHE_DIR / "audit_state.json"
SUSPICIOUS_PATH = CACHE_DIR / "suspicious_glosses.json"
SUMMARY_PATH = CACHE_DIR / "summary.json"
SCHEMA_VERSION = 5
sys.path.insert(0, str(ROOT_DIR))
from qwen_api import OpenAIAPI


def main():
    parser = argparse.ArgumentParser(description="Flag suspicious gloss rows with Qwen and write a cache-side review report.")
    parser.add_argument("--input", default=str(GLOSS_PATH), help="Input gloss JSON file.")
    parser.add_argument("--model", default="qwen-plus", help="DashScope model used for the audit.")
    parser.add_argument("--batch-size", type=int, default=75, help="Number of gloss rows per LLM batch.")
    parser.add_argument("--temperature", type=float, default=0.4, help="Sampling temperature for the audit.")
    parser.add_argument("--sample-size", type=int, default=None, help="Audit only a random sample of this many characters.")
    parser.add_argument("--sample-seed", type=int, default=None, help="Random seed used with --sample-size. If omitted, one is generated and recorded.")
    parser.add_argument("--max-parallel", type=int, default=2, help="Number of batch requests to run concurrently.")
    parser.add_argument("--reset", action="store_true", help="Ignore any existing audit cache and restart from scratch.")
    args = parser.parse_args()

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    gloss_path = Path(args.input)
    glosses = json.loads(gloss_path.read_text(encoding="utf-8"))
    source_hash = hashlib.sha256(gloss_path.read_bytes()).hexdigest()
    available_chars = list(glosses)
    if args.max_parallel <= 0: raise ValueError("--max-parallel must be positive.")
    if args.sample_size is not None and args.sample_size <= 0:
        raise ValueError("--sample-size must be positive.")
    if args.sample_size is not None and args.sample_size > len(available_chars):
        raise ValueError(f"--sample-size={args.sample_size} is larger than the {len(available_chars)} available characters.")
    requested_selection = {"sample_size": args.sample_size, "sample_seed": args.sample_seed}
    state = None
    if STATE_PATH.exists() and not args.reset:
        loaded_state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        loaded_selection = loaded_state.get("selection")
        selection_matches = loaded_selection == requested_selection or (args.sample_size is not None and args.sample_seed is None and isinstance(loaded_selection, dict) and loaded_selection.get("sample_size") == args.sample_size)
        if loaded_state.get("schema_version") == SCHEMA_VERSION and loaded_state.get("source_hash") == source_hash and loaded_state.get("model") == args.model and selection_matches:
            state = loaded_state
    selection = state["selection"] if state is not None else {"sample_size": args.sample_size, "sample_seed": args.sample_seed}
    if selection["sample_size"] is not None and selection["sample_seed"] is None:
        selection["sample_seed"] = random.SystemRandom().randrange(0, 2**31)
        print(f"Using random sample_seed={selection['sample_seed']}")
    ordered_chars = list(glosses) if selection["sample_size"] is None else random.Random(selection["sample_seed"]).sample(available_chars, selection["sample_size"])
    if state is None:
        state = {"schema_version": SCHEMA_VERSION, "source_path": str(gloss_path.relative_to(ROOT_DIR)), "source_hash": source_hash, "model": args.model, "selection": selection, "done_chars": [], "suspicious": {}}

    done_chars = set(state.get("done_chars", []))
    pending_chars = [char for char in ordered_chars if char not in done_chars]
    print(f"Total glosses: {len(ordered_chars)}; pending: {len(pending_chars)}")
    if not pending_chars:
        write_reports(state, ordered_chars)
        return

    system_prompt = """You are auditing short learner-facing glosses for Chinese characters.

Your task is to flag only the rows that clearly need manual review or correction as character-study glosses.

Return ONLY valid JSON as a direct mapping from suspicious character to review object:
{
  "char3": {
    "category": "wrong_sense",
    "reason": "short reason",
    "gloss_en": "replacement english gloss",
    "gloss_fr": "replacement french gloss"
  }
}

If a batch contains no suspicious rows, return EXACTLY:
{}

Rules:
- Input is a JSON object mapping each character to {"gloss_en": "...", "gloss_fr": "..."}.
- Return ONLY the suspicious rows as top-level character keys. Do not return okay rows, counters, summaries, wrapper keys, or extra keys.
- Flag a row only when the issue is clear enough to justify manual review. Do not flag a row merely because you can imagine a slightly nicer wording.
- Do not flag acceptable rows just because another gloss would be slightly better, slightly more precise, or slightly more elegant.
- If you are unsure, do not flag the row.
- A suspicious row must be assigned exactly one PRIMARY category from this list:
  - "wrong_sense": the gloss points to the wrong meaning
  - "en_fr_mismatch": English and French do not point to the same sense
  - "overpacked": too many senses are packed into one short gloss
  - "meta_variant_encyclopedic": the gloss is a variant note, codepoint note, source note, or encyclopedic label rather than a study gloss
  - "awkward_french": the French is understandable but too literal, awkward, or not learner-facing
  - "non_core_meaning": the gloss is real but not the character's main learner-facing meaning
  - "other": use only if none of the above fits
- When multiple categories could apply, choose the PRIMARY failure mode using this precedence order:
  1. wrong_sense
  2. en_fr_mismatch
  3. meta_variant_encyclopedic
  4. overpacked
  5. awkward_french
  6. non_core_meaning
  7. other
- Keep `reason` short and concrete.
- Always provide both `gloss_en` and `gloss_fr` for every flagged row.
- If only the French is bad and the English sense is already acceptable, keep `gloss_en` identical to the input `gloss_en`.
- Proposed English and French glosses must point to the same sense.
- Proposed glosses should be short, learner-facing, and suitable as character-study glosses.
- Prefer one main sense. For `overpacked`, replace the row with one concise main sense rather than another packed gloss.
- Do not propose variant notes, codepoint notes, source notes, or encyclopedic descriptions as replacement glosses.
- Prefer modern, common, learner-facing meanings over archaic, classical, literary, rare, or highly technical senses.
- Use `non_core_meaning` sparingly. Only use it when the current gloss is clearly secondary, archaic, overly marginal, or clearly less useful than a more central learner-facing gloss.
- Do not flag a row as `non_core_meaning` just because the character is polyphonic or has another common meaning under a different reading.
- For polyphonic characters, do not switch to another reading unless the current gloss is clearly archaic, clearly marginal, clearly misleading, or clearly much less useful for a modern learner.
- Do not replace a gloss with a compound-only meaning unless that meaning is clearly the best learner-facing character gloss in practice.
- For polyphonic characters, prefer not flagging unless the current gloss is clearly poor or clearly not the most useful standalone study gloss.
- Do not add explanations outside the JSON."""

    batches = []
    for start in range(0, len(pending_chars), args.batch_size):
        batch_chars = pending_chars[start:start + args.batch_size]
        batches += [(start // args.batch_size + 1, batch_chars, {char: glosses[char] for char in batch_chars})]
    print(f"Submitting {len(batches)} batches with max_parallel={args.max_parallel}.")

    def run_batch(batch_number, batch_chars, batch):
        client = OpenAIAPI(model=args.model, logs_dir=CACHE_DIR / "llm_io", session_name=f"suspicious_gloss_audit_b{batch_number:03d}")
        messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": json.dumps(batch, ensure_ascii=False)}]
        result = client.chat_json_streamed(messages, temperature=args.temperature, thinking=True, include_usage=True, print_stream=False)
        return batch_number, batch_chars, result if isinstance(result, dict) else {}, usage_to_dict(client.last_usage)

    completed_batches = 0
    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_tokens = 0
    with tqdm(total=len(ordered_chars), unit="char", desc="Gloss audit", dynamic_ncols=True) as progress:
        progress.set_postfix(prompt_tok=0, completion_tok=0, total_tok=0, flagged=0)
        with ThreadPoolExecutor(max_workers=args.max_parallel) as executor:
            futures = {executor.submit(run_batch, batch_number, batch_chars, batch): (batch_number, batch_chars) for batch_number, batch_chars, batch in batches}
            for future in as_completed(futures):
                batch_number, batch_chars, suspicious, usage = future.result()
                for char, review in suspicious.items():
                    if char not in glosses or not isinstance(review, dict):
                        continue
                    state["suspicious"][char] = {
                        "current_gloss_en": glosses[char]["gloss_en"],
                        "current_gloss_fr": glosses[char]["gloss_fr"],
                        "category": review.get("category", ""),
                        "reason": review.get("reason", ""),
                        "gloss_en": review.get("gloss_en", review.get("proposed_gloss_en", "")),
                        "gloss_fr": review.get("gloss_fr", review.get("proposed_gloss_fr", "")),
                    }
                state["done_chars"] = sorted(done_chars | set(batch_chars), key=ordered_chars.index)
                done_chars = set(state["done_chars"])
                completed_batches += 1
                total_prompt_tokens += usage.get("prompt_tokens", 0)
                total_completion_tokens += usage.get("completion_tokens", 0)
                total_tokens += usage.get("total_tokens", 0)
                progress.update(len(batch_chars))
                progress.set_postfix(prompt_tok=total_prompt_tokens, completion_tok=total_completion_tokens, total_tok=total_tokens, flagged=len(state["suspicious"]))
                tqdm.write(f"Completed batch {batch_number:02d} ({completed_batches}/{len(batches)}); chars done: {len(done_chars)}/{len(ordered_chars)}; flagged: {len(state['suspicious'])}; tokens in/out/total: {total_prompt_tokens}/{total_completion_tokens}/{total_tokens}")
                write_reports(state, ordered_chars)
    print(f"Final tokens in/out/total: {total_prompt_tokens}/{total_completion_tokens}/{total_tokens}")


def write_reports(state, ordered_chars):
    suspicious = {char: state["suspicious"][char] for char in ordered_chars if char in state["suspicious"]}
    category_counts = {}
    for review in suspicious.values():
        category = review.get("category") if isinstance(review, dict) else None
        if isinstance(category, str) and category:
            category_counts[category] = category_counts.get(category, 0) + 1
    summary = {
        "schema_version": state["schema_version"],
        "source_path": state["source_path"],
        "source_hash": state["source_hash"],
        "model": state["model"],
        "selection": state["selection"],
        "done_count": len(state["done_chars"]),
        "total_count": len(ordered_chars),
        "pending_count": len(ordered_chars) - len(state["done_chars"]),
        "suspicious_count": len(suspicious),
        "category_counts": category_counts,
    }
    temporary_state_path = STATE_PATH.with_suffix(".tmp")
    temporary_suspicious_path = SUSPICIOUS_PATH.with_suffix(".tmp")
    temporary_summary_path = SUMMARY_PATH.with_suffix(".tmp")
    temporary_state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary_suspicious_path.write_text(json.dumps(suspicious, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary_summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary_state_path.replace(STATE_PATH)
    temporary_suspicious_path.replace(SUSPICIOUS_PATH)
    temporary_summary_path.replace(SUMMARY_PATH)


def usage_to_dict(usage):
    if usage is None: return {}
    if isinstance(usage, dict): return usage
    if hasattr(usage, "model_dump"): return usage.model_dump()
    result = {}
    for key in ["prompt_tokens", "completion_tokens", "total_tokens"]:
        value = getattr(usage, key, None)
        if isinstance(value, int): result[key] = value
    return result


if __name__ == "__main__":
    main()
