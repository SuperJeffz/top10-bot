"""Google Gemini (AI Studio) — คุณภาพภาษาไทยดีมาก และมี free tier

มีระบบ fallback: ถ้าโมเดลที่ตั้งไว้ใช้ไม่ได้ (404 / 429 / 503 / timeout / JSON เพี้ยน)
จะลองโมเดลสำรองใน FALLBACK_MODELS ให้อัตโนมัติ
ถ้าทุกโมเดลไม่พร้อมจะใช้บทสำรองออฟไลน์แทน เพื่อให้งานยังเสร็จและได้ไฟล์ครบ
"""

import json
import os
import re
import time

import requests

from app.story_prompt import build_prompt, finalize
from app.story_fallback import build_offline_storyboard

API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"

# ลำดับโมเดลสำรอง (ตัวหลัง ๆ ใช้เมื่อตัวหน้าใช้ไม่ได้)
# 3.8-flash คือโมเดลที่ Google แนะนำแทน 2.5-flash ที่ยกเลิกไปแล้ว
FALLBACK_MODELS = [
    "gemini-3.8-flash",
    "gemini-3.6-flash",
    "gemini-4-hydrogen",
    "gemini-3-flash-preview",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-3.1-flash-lite-preview",
]

STRICT_SUFFIX = (
    "\n\n【สำคัญมาก】ตอบเป็น JSON ที่ถูกต้องตามโครงสร้างด้านบนเท่านั้น "
    "ห้ามมีข้อความอื่น ห้ามใช้ markdown code fence ทุก string ต้องปิดเครื่องหมายคำพูดให้ครบ"
)


class GeminiError(RuntimeError):
    pass


def _parse_json(text: str):
    """อ่าน JSON ให้ทนทานต่อข้อความเพี้ยน ๆ ที่โมเดลบ่อยครั้งตอบกลับมา"""
    cleaned = (text or "").strip()
    cleaned = cleaned.replace("```json", "").replace("```", "").strip()

    candidates = [cleaned]
    for op, cl in (("{", "}"), ("[", "]")):
        i, j = cleaned.find(op), cleaned.rfind(cl)
        if i >= 0 and j > i:
            candidates.append(cleaned[i : j + 1])

    candidates.append(re.sub(r",\s*([}\]])", r"\1", cleaned))
    candidates.append(
        cleaned.translate(str.maketrans({"“": '"', "”": '"', "‘": "'", "’": "'"}))
    )

    last = None
    for cand in candidates:
        try:
            # strict=False อนุญาตให้มี control character (เช่น newline) ใน string
            return json.loads(cand, strict=False)
        except Exception as e:  # noqa: BLE001
            last = e

    for cand in candidates:
        try:
            obj, _ = json.JSONDecoder(strict=False).raw_decode(cand.lstrip())
            return obj
        except Exception as e:  # noqa: BLE001
            last = e

    raise last or json.JSONDecodeError("JSON ไม่ถูกต้อง", cleaned[:100], 0)


def _call_model(
    model,
    api_key,
    prompt,
    timeout=(20, 180),
    temperature=0.9,
    fast_fail=False,
):
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": temperature,
            "topP": 0.95,
            "maxOutputTokens": 16384,
        },
    }
    url = f"{API_BASE}/{model}:generateContent"

    for attempt in range(3):
        try:
            r = requests.post(
                url,
                headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
                json=payload,
                timeout=timeout,
            )
        except requests.exceptions.Timeout:
            if not fast_fail and attempt < 2:
                time.sleep(2 * (attempt + 1))
                continue
            raise

        # 503/429 เป็นช่วงโหลดสูงหรือโควต้าชั่วคราว → รอแล้ว retry โมเดลเดิมก่อน
        if r.status_code in (429, 503):
            if not fast_fail and attempt < 2:
                time.sleep(2 * (attempt + 1) + 2)
                continue
            raise GeminiError(f"{model} -> HTTP {r.status_code}: {r.text[:200]}")

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

        return _parse_json(text)

    raise GeminiError(f"{model} -> ไม่พร้อมหลัง retry 3 ครั้ง")


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
        # รอบแรกใช้ temperature ปกติ ถ้า JSON เพี้ยนให้retry รอบสองแบบเข้มงวด
        for strict in (False, True):
            try:
                final_prompt = prompt + STRICT_SUFFIX if strict else prompt
                data = _call_model(
                    model,
                    api_key,
                    final_prompt,
                    temperature=0.2 if strict else 0.9,
                )
                data = finalize(data, topic, minutes)
                if model != configured:
                    print(f"[gemini] ใช้โมเดลสำรอง {model} (ตัวหลักใช้ไม่ได้)")
                return data
            except json.JSONDecodeError as e:
                errors.append(f"{model} -> JSON เพี้ยน: {e}")
                print(f"[gemini] {model} JSON เพี้ยน {'ลองใหม่แบบเข้มงวด' if not strict else 'ลองตัวถัดไป'}")
                continue
            except Exception as e:  # GeminiError / network
                errors.append(str(e)[:300])
                print(f"[gemini] {model} ล้มเหลว ลองตัวถัดไป")
                break

    # Gemini ไม่พร้อมชั่วคราว (503 ทุกโมเดล) → ยัง delivers งานให้ได้
    print("[gemini] ทุกโมเดลไม่พร้อม ใช้บทสำรองออฟไลน์แทน")
    return finalize(build_offline_storyboard(topic, minutes), topic, minutes)


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
            return _call_model(
                model, api_key, prompt,
                timeout=timeout, temperature=temperature, fast_fail=True,
            )
        except Exception as e:  # noqa: BLE001
            last = e
            continue
    raise GeminiError(f"เรียก Gemini ไม่สำเร็จ: {str(last)[:300]}")
