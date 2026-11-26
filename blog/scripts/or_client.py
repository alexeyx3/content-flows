"""Thin OpenRouter client. Key comes from config/openrouter.env (gitignored)."""
from __future__ import annotations

import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://openrouter.ai/api/v1"


class ORError(RuntimeError):
    pass


def load_key(env_path: Path = ROOT / "config" / "openrouter.env") -> str:
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("OPENROUTER_API_KEY="):
            return line.split("=", 1)[1].strip()
    raise ORError("OPENROUTER_API_KEY not found in config/openrouter.env")


def extract_result(data: dict) -> dict:
    """Pull text + usage out of a chat-completion response. Raises ORError if unusable."""
    try:
        choice = data["choices"][0]
        text = choice["message"]["content"] or ""
    except (KeyError, IndexError, TypeError) as e:
        raise ORError(f"malformed response: {e}") from e
    if not text.strip():
        raise ORError("empty completion")
    usage = data.get("usage") or {}
    return {
        "text": text,
        "prompt_tokens": usage.get("prompt_tokens") or 0,
        "completion_tokens": usage.get("completion_tokens") or 0,
        "cost": usage.get("cost") or 0.0,
        "finish_reason": choice.get("finish_reason", ""),
    }


def chat(model: str, messages: list[dict], temperature: float, max_tokens: int, retries: int = 1,
         reasoning: dict | None = None) -> dict:
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "usage": {"include": True},  # OpenRouter puts cost into the response usage
    }
    if reasoning:
        payload["reasoning"] = reasoning
    headers = {"Authorization": f"Bearer {load_key()}"}
    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            r = requests.post(f"{BASE}/chat/completions", json=payload, headers=headers, timeout=600)
            r.raise_for_status()
            return extract_result(r.json())
        except (requests.RequestException, ORError, ValueError) as e:
            last = e
            if attempt < retries:
                time.sleep(5)
    raise ORError(f"{model}: {last}")


def chat_with_tools(model: str, messages: list[dict], tools: list[dict], tool_handler,
                    temperature: float, max_tokens: int, max_rounds: int = 12) -> dict:
    """Tool-calling loop: run tool_calls through tool_handler(name, args)->str
    until the model returns the final text. Returns {text, usage sums, rounds, tool_calls}."""
    headers = {"Authorization": f"Bearer {load_key()}"}
    msgs = list(messages)
    totals = {"prompt_tokens": 0, "completion_tokens": 0, "cost": 0.0}
    calls_made = []
    for _ in range(max_rounds):
        payload = {"model": model, "messages": msgs, "tools": tools,
                   "temperature": temperature, "max_tokens": max_tokens,
                   "usage": {"include": True}}
        r = requests.post(f"{BASE}/chat/completions", json=payload, headers=headers, timeout=600)
        r.raise_for_status()
        data = r.json()
        usage = data.get("usage") or {}
        totals["prompt_tokens"] += usage.get("prompt_tokens") or 0
        totals["completion_tokens"] += usage.get("completion_tokens") or 0
        totals["cost"] += usage.get("cost") or 0.0
        msg = data["choices"][0]["message"]
        tool_calls = msg.get("tool_calls") or []
        if not tool_calls:
            text = msg.get("content") or ""
            if not text.strip():
                raise ORError("empty completion in tool loop")
            return {"text": text, **totals, "rounds": len(calls_made), "tool_calls": calls_made,
                    "finish_reason": data["choices"][0].get("finish_reason", "")}
        msgs.append(msg)
        import json as _json
        for tc in tool_calls:
            name = tc["function"]["name"]
            try:
                args = _json.loads(tc["function"]["arguments"] or "{}")
            except _json.JSONDecodeError:
                args = {}
            calls_made.append({"name": name, "args": args})
            result = tool_handler(name, args)
            msgs.append({"role": "tool", "tool_call_id": tc["id"], "content": result})
    raise ORError(f"{model}: tool loop exceeded {max_rounds} rounds")
