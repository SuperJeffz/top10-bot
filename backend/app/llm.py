"""ตัวเลือก provider ของ LLM — สลับได้ผ่าน .env

LLM_PROVIDER=gemini   -> ใช้ Google Gemini (แนะนำ คุณภาพภาษาไทยดีสุด)
LLM_PROVIDER=ollama   -> ใช้โมเดลในเครื่องผ่าน Ollama (ฟรี 100% ไม่ต้องใช้เน็ต)
"""

import os


def provider_name():
    return (os.getenv("LLM_PROVIDER") or "ollama").strip().lower()


def generate_storyboard(topic: str, minutes: int):
    name = provider_name()

    if name == "gemini":
        from app.llm_gemini import generate_storyboard as gen

        return gen(topic, minutes)

    if name == "ollama":
        from app.llm_ollama import generate_storyboard as gen

        return gen(topic, minutes)

    raise RuntimeError(f"LLM_PROVIDER ไม่รู้จัก: {name} (ใช้ gemini หรือ ollama)")
