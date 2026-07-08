"""
qwen_client.py
Thin wrapper around the Ollama Python client for talking to Qwen3:8B.

Qwen3 models support a "thinking" mode where the model emits its chain of
thought wrapped in <think>...</think> tags before the final answer. This
wrapper knows how to toggle that (via the `think` request option, and by
prefixing the prompt with /think or /no_think for older Ollama builds) and
how to split the raw response into (thinking, answer) so the UI/CLI can
show them separately.
"""

import re
import time
import json
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Generator

import ollama

MODEL_NAME = "qwen3:8b"

THINK_TAG_RE = re.compile(r"<think>(.*?)</think>", re.DOTALL)


@dataclass
class QwenResponse:
    thinking: str
    answer: str
    raw: str
    elapsed_s: float
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)


def _split_thinking(raw_text: str) -> (str, str):
    """Separate <think>...</think> content from the final answer text."""
    match = THINK_TAG_RE.search(raw_text)
    if match:
        thinking = match.group(1).strip()
        answer = THINK_TAG_RE.sub("", raw_text).strip()
        return thinking, answer
    return "", raw_text.strip()


def is_ollama_running() -> bool:
    try:
        ollama.list()
        return True
    except Exception:
        return False


def is_model_pulled(model: str = MODEL_NAME) -> bool:
    try:
        models = ollama.list().get("models", [])
        names = [m.get("model", m.get("name", "")) for m in models]
        return any(n.startswith(model.split(":")[0]) for n in names)
    except Exception:
        return False


def pull_model(model: str = MODEL_NAME):
    """Streams pull progress; yields status dicts."""
    for progress in ollama.pull(model, stream=True):
        yield progress


def chat(
    messages: List[Dict[str, str]],
    model: str = MODEL_NAME,
    think: bool = True,
    temperature: float = 0.7,
    tools: Optional[List[Dict[str, Any]]] = None,
    stream: bool = False,
) -> QwenResponse:
    """
    Single non-streaming (default) chat call.
    `think=True` asks Qwen3 to expose its reasoning trace.
    """
    start = time.time()
    kwargs: Dict[str, Any] = dict(
        model=model,
        messages=messages,
        options={"temperature": temperature},
    )
    if tools:
        kwargs["tools"] = tools
    try:
        # Newer Ollama python client supports a top-level `think` flag for Qwen3-style models.
        kwargs["think"] = think
        resp = ollama.chat(**kwargs)
    except TypeError:
        # Fallback for older client versions: use /think or /no_think prefix convention.
        kwargs.pop("think", None)
        if messages and messages[-1]["role"] == "user":
            prefix = "/think " if think else "/no_think "
            messages[-1]["content"] = prefix + messages[-1]["content"]
        resp = ollama.chat(**kwargs)

    elapsed = time.time() - start
    raw_content = resp["message"].get("content", "")
    thinking, answer = _split_thinking(raw_content)

    tool_calls = resp["message"].get("tool_calls", []) or []

    usage = resp.get("prompt_eval_count"), resp.get("eval_count")

    return QwenResponse(
        thinking=thinking,
        answer=answer,
        raw=raw_content,
        elapsed_s=elapsed,
        prompt_tokens=usage[0],
        completion_tokens=usage[1],
        tool_calls=tool_calls,
    )


def chat_stream(
    messages: List[Dict[str, str]],
    model: str = MODEL_NAME,
    think: bool = True,
    temperature: float = 0.7,
) -> Generator[str, None, None]:
    """Streaming generator, yields raw text chunks (may include <think> tags)."""
    kwargs: Dict[str, Any] = dict(
        model=model,
        messages=messages,
        options={"temperature": temperature},
        stream=True,
    )
    try:
        kwargs["think"] = think
        stream = ollama.chat(**kwargs)
    except TypeError:
        kwargs.pop("think", None)
        if messages and messages[-1]["role"] == "user":
            prefix = "/think " if think else "/no_think "
            messages[-1]["content"] = prefix + messages[-1]["content"]
        stream = ollama.chat(**kwargs)

    for chunk in stream:
        piece = chunk["message"].get("content", "")
        if piece:
            yield piece


def json_extract(prompt: str, schema_hint: str, model: str = MODEL_NAME) -> Dict[str, Any]:
    """Ask Qwen3 to return strict JSON matching a described schema."""
    system = (
        "You are a precise data-extraction engine. "
        "Respond with ONLY valid minified JSON matching this shape, no prose, "
        "no markdown fences, no <think> tags:\n" + schema_hint
    )
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": prompt},
    ]
    result = chat(messages, model=model, think=False, temperature=0.1)
    text = result.answer.strip()
    text = re.sub(r"^```(json)?|```$", "", text, flags=re.MULTILINE).strip()
    return json.loads(text)
