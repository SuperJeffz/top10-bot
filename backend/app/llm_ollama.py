"""Ollama (รันโมเดลในเครื่อง ฟรี 100%)"""

import os
import json
import requests

from app.story_prompt import build_prompt, finalize


def generate_storyboard(topic: str, minutes: int):
    base = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    model = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
    prompt = build_prompt(topic, minutes)

    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.8, "num_predict": 6000, "num_ctx": 8192},
    }

    r = requests.post(f"{base}/api/generate", json=payload, timeout=3600)
    r.raise_for_status()
    text = r.json().get("response", "")
    text = text.replace("```json", "").replace("```", "").strip()
    return finalize(json.loads(text), topic, minutes)
