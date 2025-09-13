from __future__ import annotations
from typing import Any, Dict, List, Optional
import os

try:
    from openai import OpenAI
except Exception:  # optional
    OpenAI = None  # type: ignore


def _client_or_none():
    if OpenAI is None:
        return None
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    return OpenAI(api_key=api_key)


def generate_value_for_key(key_path: str, context: Dict[str, Any], template: Optional[str] = None) -> Any:
    client = _client_or_none()
    if client is None:
        # Fallback: return None to signal caller to use defaults
        return None

    # Default templates by key shape
    default_templates = {
        "subject": (
            "Return a JSON array of 3 concise subject phrases for a merch design. "
            "Style: concise, evocative, no periods."
        ),
        "icons_symbols": (
            "Return a JSON array of 2-3 succinct icon/symbol keywords coherent with the design."
        ),
        "text.secondary": (
            "Return a single short brand tagline string (no quotes) coherent with FULLY AUTOMATED ENTERPRISES aesthetics."
        ),
    }

    sys_prompt = (
        "You generate structured JSON snippets that fit a merch design JSON spec. "
        "Only output the requested JSON value and nothing else."
    )
    user_prompt = template or default_templates.get(key_path, f"Return a concise JSON string value for {key_path}.")

    # Use Responses/Chat; prefer Responses if available in SDK
    try:
        resp = client.chat.completions.create(
            model=os.getenv("FAE_LLM_MODEL", "gpt-4o-mini"),
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
        )
        text = resp.choices[0].message.content.strip()
    except Exception:
        return None

    # Try to parse JSON arrays; else treat as raw string
    import json
    try:
        val = json.loads(text)
        return val
    except Exception:
        return text.strip('"')

