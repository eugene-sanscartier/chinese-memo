"""
LLM API Module for Qwen (Alibaba Cloud)
Supports Qwen3-MAX and other Qwen models via DashScope API
"""

# DASHSCOPE_API_KEY = 'sk-841c4fa613914ccaa7da9883aa759b11' # deepseek
# BASE_URL=https://api.deepseek.com  # deepseek
# MODELS = {  # deepseek
#     "": "",
# }

DASHSCOPE_API_KEY = 'sk-2cbe14e057f14615b670eda42a55af9b'  # aliyuncs
BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"  # aliyuncs
MODELS = {  # aliyuncs
    "qwen-max": "qwen-max",  # Latest Qwen3-MAX
    "qwen-max-0428": "qwen-max-0428",
    "qwen-max-0403": "qwen-max-0403",
    "qwen-max-0107": "qwen-max-0107",
    "qwen-plus": "qwen-plus",
    "qwen-turbo": "qwen-turbo",
}

import os
import json
import datetime
import threading
from typing import List, Dict, Any, Optional, Union, Tuple, Iterator
from openai import OpenAI


class OpenAIAPI:
    """
    API client using OpenAI-compatible interface via DashScope.
    """

    def __init__(self, api_key: Optional[str] = None, model: str = "qwen-max", logs_dir: Optional[str] = None, session_name: Optional[str] = None):
        """
        Initialize Qwen API client.

        Args:
            api_key: DashScope API key. If None, will use DASHSCOPE_API_KEY env variable
            model: Model name (default: qwen-max)
            logs_dir: Directory to write input/output logs (default: ./llm_io)
            session_name: Optional session label to prefix filenames
        """
        self.api_key = api_key or os.getenv("DASHSCOPE_API_KEY")
        if not self.api_key:
            raise ValueError("API key is required. Pass it as argument or set DASHSCOPE_API_KEY environment variable.")

        if model not in MODELS:
            raise ValueError(f"Invalid model: {model}. Available models: {list(self.MODELS.keys())}")

        self.model = model
        self.client = OpenAI(api_key=self.api_key, base_url=BASE_URL)
        # IO logging setup
        self.logs_dir = logs_dir or os.path.join(os.getcwd(), "llm_io")
        os.makedirs(self.logs_dir, exist_ok=True)
        self.session_name = session_name
        self._io_counter = 0
        self._io_lock = threading.Lock()

    def _next_io_filenames(self, kind: str, ext: str = "json") -> str:
        """
        Build a unique filename for input/output logging.
        kind: 'input' or 'output'
        ext: file extension (json or txt)
        """
        with self._io_lock:
            self._io_counter += 1
            counter = self._io_counter
        ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        prefix = f"{kind}_"
        parts = [prefix]
        if self.session_name:
            parts.append(f"{self.session_name}_")
        filename = f"{''.join(parts)}{ts}_{counter}.{ext}"
        return os.path.join(self.logs_dir, filename)

    def _log_input(self, payload: Dict[str, Any]) -> str:
        """Write the input payload to an input_*.json file and return path."""
        path = self._next_io_filenames("input", "json")
        record = {
            "type": "chat_input",
            "created_at": datetime.datetime.now().isoformat(),
            **payload,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=2)
        return path

    def _log_output_text(self, text: str) -> str:
        """Write the output text to an output_*.txt file and return path."""
        path = self._next_io_filenames("output", "txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return path

    def _open_stream_output_file(self) -> Tuple[str, Any]:
        """Open an output_*.txt file for streaming writes; return (path, handle)."""
        path = self._next_io_filenames("output", "txt")
        handle = open(path, "w", encoding="utf-8")
        return path, handle

    def chat(self, messages: List[Dict[str, str]], temperature: float = 1.0, top_p: float = 0.9, max_tokens: Optional[int] = None, response_format: Optional[Dict[str, str]] = None, stream: bool = False, **kwargs) -> Union[str, Any]:
        """
        Send a chat completion request.

        Args:
            messages: List of message dicts with 'role' and 'content' keys
            temperature: Sampling temperature (0.0-2.0)
            top_p: Nucleus sampling parameter
            max_tokens: Maximum tokens to generate
            response_format: Format specification, e.g., {'type': 'json_object'}
            stream: Whether to stream the response
            **kwargs: Additional parameters to pass to the API

        Returns:
            If stream=False: The response content as a string
            If stream=True: The raw streaming response object
        """
        params = {"model": self.model, "messages": messages, "temperature": temperature, "top_p": top_p, "stream": stream, **kwargs}

        if max_tokens is not None:
            params["max_tokens"] = max_tokens

        if response_format is not None:
            params["response_format"] = response_format

        # Log input
        try:
            self._log_input({
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "top_p": top_p,
                **({
                    "max_tokens": max_tokens
                } if max_tokens is not None else {}),
                **({
                    "response_format": response_format
                } if response_format is not None else {}),
                **({
                    k: v
                    for k, v in kwargs.items() if k != "api_key"
                }),
                "stream": stream,
            })
        except Exception:
            # Logging should never break inference
            pass

        response = self.client.chat.completions.create(**params)

        if stream:
            # Wrap the stream to log output progressively
            def _generator() -> Iterator[str]:
                path, fh = self._open_stream_output_file()
                try:
                    for chunk in response:
                        delta = getattr(chunk.choices[0].delta, "content", None)
                        if delta:
                            try:
                                fh.write(delta)
                                fh.flush()
                            except Exception:
                                pass
                            yield delta
                finally:
                    try:
                        fh.write("\n")
                        fh.close()
                    except Exception:
                        pass

            return _generator()
        else:
            content = response.choices[0].message.content
            try:
                self._log_output_text(content if isinstance(content, str) else str(content))
            except Exception:
                pass
            return content

    def chat_with_system(self, system_prompt: str, user_prompt: str, **kwargs) -> str:
        """
        Convenience method for simple system + user prompt chat.

        Args:
            system_prompt: System message content
            user_prompt: User message content
            **kwargs: Additional parameters passed to chat()

        Returns:
            The response content as a string
        """
        messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]
        return self.chat(messages, **kwargs)

    def chat_json(self, messages: List[Dict[str, str]], stream: bool = False, **kwargs) -> Union[Dict[str, Any], Iterator[str]]:
        """
        Chat with JSON response format.

        Args:
            messages: List of message dicts with 'role' and 'content' keys
            stream: If True, yields JSON chunks as they arrive; if False, returns parsed dict
            **kwargs: Additional parameters passed to chat()

        Returns:
            If stream=False: Parsed JSON response as a dictionary
            If stream=True: Iterator yielding JSON text chunks (parse accumulated text when done)
        """
        if stream:
            return self.chat(messages, response_format={'type': 'json_object'}, stream=True, **kwargs)  # type: ignore
        else:
            response_text = self.chat(messages, response_format={'type': 'json_object'}, **kwargs)
            return json.loads(response_text)

    def stream_chat(self, messages: List[Dict[str, str]], **kwargs):
        """
        Stream chat responses.

        Args:
            messages: List of message dicts with 'role' and 'content' keys
            **kwargs: Additional parameters passed to chat()

        Yields:
            Content chunks from the streaming response
        """
        # chat(stream=True) already wraps and logs; just pass through
        stream = self.chat(messages, stream=True, **kwargs)
        for chunk in stream:
            yield chunk

    def chat_json_streamed(self, messages: List[Dict[str, str]], **kwargs) -> Dict[str, Any]:
        accumulated = []
        for chunk in self.chat_json(messages, stream=True, **kwargs):
            accumulated.append(chunk)
            print(chunk, end="", flush=True)
        print()  # newline after stream
        full_text = "".join(accumulated)
        return json.loads(full_text)


with open("gloss.json", "r", encoding="utf-8") as file_obj:
    gloss_list: dict = json.load(file_obj)
# with open("definitions.json", "r", encoding="utf-8") as file_obj:
#     definitions_list: dict = json.load(file_obj)

with open("onev3-llm_defselection.json", "r", encoding="utf-8") as file_obj:
    definitions_list: dict = json.load(file_obj)
for char, defs in definitions_list.items():
    if "def_fr" not in defs: defs["def_fr"] = ""


def main_gloss():
    system_prompt = """You are a professional specializing in Chinese characters and their meanings. Your task is to give French glosses to chinese character.

## CRITICAL REQUIREMENTS:
1. Return ONLY valid JSON with the EXACT same structure
2. Fill ONLY the `gloss_fr` field with its French glosses
3. You MUST NOT add, remove, or modify any input entries - except the `gloss_fr` field that you are expected to fill
4. Do not add explanatory notes, Unicode references, or additional context

# Output format:
Return ONLY valid JSON with the EXACT same structure as input:
EXAMPLE INPUT:
{
    "的": {"gloss_en": "[possessive]", "gloss_fr": ""},
    "白": {"gloss_en": "white", "gloss_fr": ""},
}
EXAMPLE OUTPUT:
{
    "的": {"gloss_en": "[possessive]", "gloss_fr": "[possessif]"},
    "白": {"gloss_en": "white", "gloss_fr": "blanc"},
}

## Guidelines:
- Maintain original formatting (brackets, punctuation, parenthetical notes)
- Use lowercase for general descriptors unless it's a proper noun
- You can use the "gloss_en" field to help understand the meaning, but always provide natural French glosses

Goves the following character glosses:
"""

    client = OpenAIAPI(model="qwen-max", api_key=DASHSCOPE_API_KEY)

    out_dir = "llm_translation"
    os.makedirs(out_dir, exist_ok=True)

    # Flattened
    records_keys = list(gloss_list)

    # Cumulative output file (append/merge across runs)
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

    # Filter out already processed characters to support resume
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

    client = OpenAIAPI(model="qwen-max", api_key=DASHSCOPE_API_KEY)

    out_dir = "llm_translation"
    os.makedirs(out_dir, exist_ok=True)

    # Flattened
    records_keys = list(definitions_list)

    # Cumulative output file (append/merge across runs)
    merged_path = os.path.join(out_dir, "definitions_translation.json")
    if os.path.exists(merged_path):
        try:
            with open(merged_path, "r", encoding="utf-8") as f_in:
                merged = json.load(f_in)
        except Exception:
            print(f"Warning: Failed to load existing merged file at {merged_path}. Starting fresh.")
            merged = {}
    else:
        merged = {}

    # Filter out already processed characters to support resume
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
    main_gloss()
    # main_definitions()

# system_prompt = """You are a professional translator specializing in Chinese characters and their meanings. Your task is to translate character glosses (short definitions/meanings) from English to French.

# ## CRITICAL REQUIREMENTS:
# 1. Return ONLY valid JSON with the EXACT same structure
# 2. Fill ONLY the `gloss_fr` field with its French translations
# 3. You MUST NOT add, remove, or modify any input entries - except the `gloss_fr` field that you are expected to fill in with the French translation
# 4. Do not add explanatory notes, Unicode references, or additional context

# # Output format:
# Return ONLY valid JSON with the EXACT same structure as input:
# EXAMPLE INPUT:
# {
#     "的": {"gloss_en": "[possessive]", "gloss_fr": ""},
#     "白": {"gloss_en": "white", "gloss_fr": ""},
#     "丷": {"gloss_en": "“ears-out” component used in some Chinese characters (e.g. U+5151 兑)", "gloss_fr": ""}
# }
# EXAMPLE OUTPUT:
# {
#     "的": {"gloss_en": "[possessive]", "gloss_fr": "[possessif]"},
#     "白": {"gloss_en": "white", "gloss_fr": "blanc"},
#     "丷": {"gloss_en": "“ears-out” component used in some Chinese characters (e.g. U+5151 兑)", "gloss_fr": "composant “oreilles sortantes” utilisé dans certains caractères chinois (par ex. U+5151 兑)"}
# }

# ## Translation guidelines:
# - For grammatical categories (like "[possessive]"), translate to French equivalents: "[possessif]", "[verbe]", etc.
# - For nouns and descriptors, use the most common and natural French translation
# - Maintain original formatting (brackets, punctuation, parenthetical notes)
# - Use lowercase for general descriptors unless it's a proper noun
# - For compound or complex English glosses, translate the entire meaning accurately

# ## RULES:
# - Keys MUST be the Chinese characters from the input
# - Never remove or add new entries
# - Never change gloss_en values or the character keys

# Translate the following glosses:
# """
