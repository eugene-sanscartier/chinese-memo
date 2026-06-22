import datetime
import json
import os
import threading
from pathlib import Path
from typing import Any, Dict, Iterator, List, Tuple, Union

from openai import OpenAI


BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
MODELS = {
    "qwen-max": "qwen-max",
    "qwen3.5-plus": "qwen3.5-plus",
    "qwen-max-0428": "qwen-max-0428",
    "qwen-max-0403": "qwen-max-0403",
    "qwen-max-0107": "qwen-max-0107",
    "qwen-plus": "qwen-plus",
    "qwen-turbo": "qwen-turbo",
}


class OpenAIAPI:
    def __init__(self, model="qwen-max", api_key=None, logs_dir=None, session_name=None):
        self.model = model
        self.api_key = api_key or os.getenv("DASHSCOPE_API_KEY")
        if not self.api_key:
            raise ValueError("Set DASHSCOPE_API_KEY before using LLM definition cleanup.")
        self.client = OpenAI(api_key=self.api_key, base_url=BASE_URL)
        self.logs_dir = Path(logs_dir or "llm_io")
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.session_name = session_name
        self._io_counter = 0
        self._io_lock = threading.Lock()

    def _next_io_filename(self, kind, ext="json"):
        with self._io_lock:
            self._io_counter += 1
            counter = self._io_counter
        ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        prefix = f"{kind}_" + (f"{self.session_name}_" if self.session_name else "")
        return str(self.logs_dir / f"{prefix}{ts}_{counter}.{ext}")

    def _log_input(self, payload):
        path = self._next_io_filename("input", "json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"type": "chat_input", "created_at": datetime.datetime.now().isoformat(), **payload}, f, ensure_ascii=False, indent=2)

    def _log_output(self, text):
        path = self._next_io_filename("output", "txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)

    def _open_stream_output_file(self) -> Tuple[str, Any]:
        path = self._next_io_filename("output", "txt")
        return path, open(path, "w", encoding="utf-8")

    def chat(self, messages: List[Dict[str, str]], temperature=1.0, top_p=0.9, max_tokens=None, response_format=None, stream=False, enable_thinking=False, include_usage=False, **kwargs) -> Union[str, Iterator[str]]:
        params = {"model": self.model, "messages": messages, "temperature": temperature, "top_p": top_p, "stream": stream, **kwargs}
        if max_tokens is not None: params["max_tokens"] = max_tokens
        if response_format is not None: params["response_format"] = response_format
        if enable_thinking: params["extra_body"] = {"enable_thinking": True}
        if include_usage and stream: params["stream_options"] = {"include_usage": True}
        try:
            self._log_input({"model": self.model, "messages": messages, "temperature": temperature, "top_p": top_p, **({"max_tokens": max_tokens} if max_tokens is not None else {}), **({"response_format": response_format} if response_format is not None else {}), **({"extra_body": {"enable_thinking": True}} if enable_thinking else {}), **({"stream_options": {"include_usage": True}} if include_usage and stream else {}), "stream": stream})
        except Exception:
            pass
        response = self.client.chat.completions.create(**params)
        if stream:
            def _generator() -> Iterator[str]:
                _, fh = self._open_stream_output_file()
                try:
                    for chunk in response:
                        if not chunk.choices:
                            if include_usage and getattr(chunk, "usage", None):
                                try: fh.write(f"\n[usage] {chunk.usage}\n"); fh.flush()
                                except Exception: pass
                            continue
                        delta = getattr(chunk.choices[0].delta, "content", None)
                        if delta:
                            try: fh.write(delta); fh.flush()
                            except Exception: pass
                            yield delta
                finally:
                    try: fh.write("\n"); fh.close()
                    except Exception: pass
            return _generator()
        content = response.choices[0].message.content
        try: self._log_output(content if isinstance(content, str) else str(content))
        except Exception: pass
        return content

    def chat_with_system(self, system_prompt: str, user_prompt: str, **kwargs) -> str:
        return self.chat([{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}], **kwargs)

    def chat_json(self, messages: List[Dict[str, str]], stream=False, **kwargs) -> Union[Dict[str, Any], Iterator[str]]:
        if stream:
            return self.chat(messages, response_format={"type": "json_object"}, stream=True, **kwargs)
        return json.loads(self.chat(messages, response_format={"type": "json_object"}, **kwargs))

    def stream_chat(self, messages: List[Dict[str, str]], **kwargs) -> Iterator[str]:
        for chunk in self.chat(messages, stream=True, **kwargs):
            yield chunk

    def chat_json_streamed(self, messages: List[Dict[str, str]], thinking=False, include_usage=False, **kwargs) -> Dict[str, Any]:
        if thinking:
            response = self.client.chat.completions.create(model=self.model, messages=messages, temperature=kwargs.pop("temperature", 1.0), top_p=kwargs.pop("top_p", 0.9), stream=True, extra_body={"enable_thinking": True}, **({"stream_options": {"include_usage": True}} if include_usage else {}), **kwargs)
            try:
                self._log_input({"model": self.model, "messages": messages, "extra_body": {"enable_thinking": True}, **({"stream_options": {"include_usage": True}} if include_usage else {}), "stream": True})
            except Exception:
                pass
            reasoning_content = ""
            answer_content = ""
            has_thinking = False
            is_answering = False
            _, fh = self._open_stream_output_file()
            try:
                for chunk in response:
                    if not chunk.choices:
                        if include_usage and getattr(chunk, "usage", None):
                            print("\n\033[90m\nUsage :"); print(chunk.usage); print("\033[0m")
                        continue
                    delta = chunk.choices[0].delta
                    if hasattr(delta, "reasoning_content") and delta.reasoning_content is not None:
                        if not is_answering and not has_thinking:
                            print("\033[94m\n" + "=" * 20 + " Reasoning :" + "\033[0m")
                            has_thinking = True
                        if not is_answering:
                            print(delta.reasoning_content, end="", flush=True)
                        reasoning_content += delta.reasoning_content
                        try: fh.write(delta.reasoning_content); fh.flush()
                        except Exception: pass
                    if hasattr(delta, "content") and delta.content:
                        if not is_answering:
                            print("\n\n\n\033[92m\n" + "=" * 20 + " Response :" + "\033[0m")
                            is_answering = True
                        print(delta.content, end="", flush=True)
                        answer_content += delta.content
                        try: fh.write(delta.content); fh.flush()
                        except Exception: pass
            finally:
                try: fh.write("\n"); fh.close()
                except Exception: pass
            print()
            return json.loads(answer_content)
        accumulated = []
        for chunk in self.chat_json(messages, stream=True, include_usage=include_usage, **kwargs):
            accumulated += [chunk]
            print(chunk, end="", flush=True)
        print()
        return json.loads("".join(accumulated))
