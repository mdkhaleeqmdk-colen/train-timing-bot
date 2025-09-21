# llm.py
from __future__ import annotations
import os
import json
from dotenv import load_dotenv
from anthropic import Anthropic

# Load .env before reading keys
load_dotenv()

anthropic_client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

SYSTEM_PROMPT = (
    "You translate a user question about UK trains into a JSON intent. "
    "Fields: origin_name, destination_name, origin_crs, destination_crs, "
    "when ('now' or 'HH:MM'), and max_results. "
    "Prefer CRS codes if the user provides them; otherwise keep names. "
    "Only output strict JSON."
)

EXAMPLE_USER = "next fast train from king's cross to cambridge after 18:30"

EXAMPLE_JSON = {
    "origin_name": "king's cross",
    "destination_name": "cambridge",
    "origin_crs": "KGX",
    "destination_crs": "CBG",
    "when": "18:30",
    "max_results": 5
}

def parse_intent(text: str) -> dict:
    """Use Claude to convert a natural-language prompt into a JSON intent."""
    msg = anthropic_client.messages.create(
        model="claude-3-haiku-20240307",
        max_tokens=300,
        temperature=0,
        system=SYSTEM_PROMPT,
        messages=[
            {"role": "user", "content": f"User: {EXAMPLE_USER}\nReturn JSON for: {text}"}
        ],
    )
    raw = msg.content[0].text.strip()
    # Safety: remove code fences if they appear
    raw = raw.replace("```json", "").replace("```", "").strip()
    return json.loads(raw or "{}")
