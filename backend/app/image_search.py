import os
import requests

try:  # แพ็กเกจใหม่ (2025) ชื่อ ddgs
    from ddgs import DDGS
except ImportError:  # fallback แพ็กเกจเก่า
    from duckduckgo_search import DDGS


def search_image_urls(query: str, num: int = 3):
    """ค้นหารูปภาพจาก DuckDuckGo (ฟรี ไม่ต้องมี API key)"""
    urls = []
    try:
        with DDGS() as ddgs:
            for r in ddgs.images(query, max_results=num):
                u = r.get("image") or r.get("url") or r.get("thumbnail")
                if u:
                    urls.append(u)
    except Exception as e:
        print(f"[WARN] image search error for '{query}': {e}")
    return urls


def download_image(url: str, save_path: str):
    r = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    if len(r.content) < 2048:
        raise ValueError("ไฟล์ภาพเล็กเกินไป (อาจไม่ใช่รูปจริง)")
    with open(save_path, "wb") as f:
        f.write(r.content)
    return save_path
