"""Google Gemini (AI Studio) — คุณภาพภาษาไทยดีมาก และมี free tier

มีระบบ fallback: ถ้าโมเดลที่ตั้งไว้ใช้ไม่ได้ (404 / 429 โควตาหมด / 503 / timeout)
จะลองโมเดลสำรองใน FALLBACK_MODELS ให้อัตโนมัติ
"""

import os
import json
import requests

from app.story_prompt import build_prompt, finalize

API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"

# ลำดับโมเดลสำรอง (ตัวหลัง ๆ ใช้เมื่อตัวหน้าใช้ไม่ได้)
FALLBACK_MODELS = [
    "gemini-3.6-flash",
    "gemini-3-flash-preview",
    "gemini-3.5-flash",
    "gemini-3.1-flash-lite",
    "gemini-3.1-flash-lite-preview",
    "gemini-2.5-flash",
]


class GeminiError(RuntimeError):
    pass


def _call_model(model, api_key, prompt, timeout=(20, 180)):
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.9,
            "topP": 0.95,
            "maxOutputTokens": 16384,
        },
    }

    r = requests.post(
        f"{API_BASE}/{model}:generateContent",
        headers={
            "x-goog-api-key": api_key,
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=timeout,
    )

    if r.status_code != 200:
        raise GeminiError(f"{model} -> HTTP {r.status_code}: {r.text[:300]}")

    body = r.json()
    candidates = body.get("candidates") or []
    if not candidates:
        raise GeminiError(f"{model} -> ไม่คืนคำตอบ: {json.dumps(body)[:300]}")

    parts = candidates[0].get("content", {}).get("parts") or []
    text = "".join(p.get("text", "") for p in parts).strip()
    if not text:
        reason = candidates[0].get("finishReason")
        raise GeminiError(f"{model} -> ข้อความว่าง (finishReason={reason})")

    text = text.replace("```json", "").replace("```", "").strip()
    return json.loads(text)


def generate_storyboard(topic: str, minutes: int):
    api_key = (os.getenv("GEMINI_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError(
            "ยังไม่ได้ใส่ GEMINI_API_KEY — ใส่ได้ที่หน้า «ตั้งค่า AI» บนเว็บ "
            "หรือขอคีย์ที่ https://aistudio.google.com/apikey"
        )

    configured = (os.getenv("GEMINI_MODEL") or "gemini-3.6-flash").strip()

    # ลองโมเดลที่ตั้งไว้ก่อน แล้วค่อยไล่ตัวสำรอง (ไม่ซ้ำ)
    models = [configured] + [m for m in FALLBACK_MODELS if m != configured]

    prompt = build_prompt(topic, minutes)
    errors = []

    for model in models:
        try:
            data = _call_model(model, api_key, prompt)
            data = finalize(data, topic, minutes)
            if model != configured:
                print(f"[gemini] ใช้โมเดลสำรอง {model} (ตัวหลักใช้ไม่ได้)")
            return data
        except json.JSONDecodeError as e:
            errors.append(f"{model} -> JSON เพี้ยน: {e}")
            print(f"[gemini] {model} ตอบไม่เป็น JSON ลองตัวถัดไป")
        except requests.exceptions.Timeout:
            errors.append(f"{model} -> timeout")
            print(f"[gemini] {model} timeout ลองตัวถัดไป")
        except Exception as e:  # GeminiError / network
            errors.append(str(e)[:300])
            print(f"[gemini] {model} ล้มเหลว ลองตัวถัดไป")

    raise RuntimeError(
        "Gemini ใช้ไม่ได้ทุกโมเดล:\n" + "\n".join(errors)
        + "\n\nลองเปลี่ยนโมเดลในหน้า «ตั้งค่า AI» หรือเช็กโควตาที่ "
        "https://aistudio.google.com/apikey"
    )


def generate_json(prompt: str, temperature: float = 0.7, timeout=(20, 150)):
    """เรียก Gemini แบบทั่วไป (ขอผลเป็น JSON) พร้อม fallback โมเดล — ใช้กับงานเสริม เช่น พรอมป์ตวิดีโอ"""
    api_key = (os.getenv("GEMINI_API_KEY") or "").strip()
    if not api_key:
        raise GeminiError("ยังไม่ได้ใส่ GEMINI_API_KEY")

    configured = (os.getenv("GEMINI_MODEL") or "gemini-3.6-flash").strip()
    models = [configured] + [m for m in FALLBACK_MODELS if m != configured]

    last = None
    for model in models:
        try:
            payload = _call_model(model, api_key, prompt, timeout=timeout)
            return payload
        except Exception as e:
            last = e
            continue
    raise GeminiError(f"เรียก Gemini ไม่สำเร็จ: {str(last)[:300]}")
