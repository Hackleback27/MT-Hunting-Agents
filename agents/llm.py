"""
llm.py - one small helper every agent uses to ask Claude for structured JSON.
"""

import json
from dotenv import load_dotenv
import anthropic

load_dotenv()
_client = anthropic.Anthropic()

MODEL = "claude-haiku-5-5"   # cheap and fast; good enough for data-cleanup jobs


def ask_json(system: str, prompt: str, max_tokens: int = 1500) -> dict:
    """Send a prompt and return Claude's reply parsed as JSON."""
    reply = _client.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        system=system + "\nRespond with a single JSON object and nothing else.",
        messages=[{"role": "user", "content": prompt}],
    )
    text = reply.content[0].text
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"Claude did not return JSON:\n{text}")
    return json.loads(text[start:end + 1])
