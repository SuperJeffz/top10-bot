"""แบ่งสตอรี่บอร์ดออกเป็น "ช็อต" สั้น ๆ (ค่าเริ่มต้น 10 วินาที) เพื่อเอาไป gen วิดีโอทีละคลิป

หลักการ
- ตัดบทพูดตามช่องว่าง (ภาษาไทยใช้ช่องว่างคั่นวลี) ให้แต่ละช็อตพูดได้ไม่เกิน max_seconds
- เวลาของแต่ละช็อตกระจายตามจำนวนตัวอักษรจริง รวมกันแล้วเท่ากับเวลาของฉากเป๊ะ
- สร้าง video prompt ภาษาอังกฤษ (video model ส่วนใหญ่ ถนัดอังกฤษ) จาก visual + image_query
- ถ้ามี LLM จะเรียบเรียงพรอมป์ตให้ละเอียดขึ้น (ล้มเหลวก็ยังใช้พรอมป์ตพื้นฐานได้)

ผลลัพธ์: shots.json / shots.csv / video_prompts.docx / shots/ (ref image + prompt.txt + vo.txt)
"""

import csv
import json
import os
import re

CHARS_PER_SECOND = 12.0  # ภาษาไทยพูดเร็วประมาณ 12 ตัวอักษร/วินาที
MIN_SHOT_SECONDS = 3
DEFAULT_MAX_SECONDS = 10

# มุมกล้องหมุนวนให้แต่ละช็อตไม่ซ้ำกัน (ภาษาอังกฤษ เพราะ video model เข้าใจตรงกว่า)
CAMERA_MOVES = [
    "slow cinematic push-in",
    "smooth handheld tracking shot",
    "slow pan from left to right",
    "close-up detail shot with shallow depth of field",
    "slow pull-back reveal",
    "steady dolly shot moving forward",
    "gentle orbit around the subject",
    "static wide establishing shot",
]

STYLE_SUFFIX = (
    "photorealistic, natural lighting, warm cinematic color grade, "
    "shallow depth of field, 24fps film look, ultra detailed, 4k"
)

NEGATIVE_PROMPT = (
    "text, subtitle, watermark, logo, caption, distorted face, extra limbs, "
    "deformed hands, blurry, low quality, oversaturated, flickering, "
    "jittery motion, warped perspective, duplicate subject"
)


# ------------------------------------------------------------------ utilities
def clean_len(text):
    """นับเฉพาะตัวอักษรที่ไม่ใช่ช่องว่าง"""
    return len("".join(ch for ch in (text or "") if not ch.isspace()))


def speech_seconds(text, chars_per_second=CHARS_PER_SECOND):
    n = clean_len(text)
    return n / chars_per_second if n else 0.0


def tc(sec):
    h, rem = divmod(int(sec), 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


_THAI_MARKS = set(range(0x0E31, 0x0E3B)) | set(range(0x0E47, 0x0E4F)) | {0x0E33, 0x0E4C, 0x0E4D, 0x0E4E}


def _safe_cut(text, limit):
    """ตัดข้อความที่ตำแหน่งปลอดภัย (ไม่ให้สระ/วรรณยุกต์ไทยลอยไปอยู่ต้นท่อนใหม่)"""
    cut = min(limit, len(text))
    while cut > 1 and (ord(text[cut]) in _THAI_MARKS or ord(text[cut - 1]) == 0x0E4E):
        cut -= 1
    return text[:cut], text[cut:]


def _safe_split(text, max_chars):
    """ผ่าก้อนที่ยาวเกินเพดาน (ใช้เมื่อไม่มีช่องว่างให้ตัดเลย)"""
    out, rest = [], (text or "").strip()
    while clean_len(rest) > max_chars * 1.1:
        head, rest = _safe_cut(rest, max_chars)
        if not head:
            break
        out.append(head.strip())
    if rest.strip():
        out.append(rest.strip())
    return out


def split_into_n(text, n):
    """แบ่งข้อความเป็น n ก้อนที่ความยาวใกล้เคียงกัน (ตัดที่ช่องว่างเท่านั้น ไม่ตัดกลางคำ)"""
    text = (text or "").strip()
    if not text:
        return []
    n = max(1, int(n))
    if n == 1:
        return [text]

    tokens = text.split()
    if len(tokens) <= n:
        return tokens or [text]

    total = sum(clean_len(t) for t in tokens)
    target = total / n

    chunks, cur, cur_len = [], [], 0
    for idx, tok in enumerate(tokens):
        cur.append(tok)
        cur_len += clean_len(tok)

        remaining = len(tokens) - (idx + 1)
        chunks_left = n - len(chunks)
        if chunks_left <= 1:
            continue  # ก้อนสุดท้ายเก็บที่เหลือทั้งหมด
        if cur_len >= target or remaining <= chunks_left - 1:
            chunks.append(" ".join(cur))
            cur, cur_len = [], 0

    if cur:
        chunks.append(" ".join(cur))

    return [c for c in chunks if c.strip()] or [text]


def chunk_text(text, max_chars):
    """แบ่งข้อความเป็นก้อน ๆ ให้แต่ละก้อนยาวไม่เกิน max_chars (ตัดที่ช่องว่าง ไม่ตัดกลางคำ)"""
    text = (text or "").strip()
    if not text:
        return []
    if clean_len(text) <= max_chars:
        return [text]

    import math

    if len(text.split()) <= 1:
        # ไม่มีช่องว่างเลย (ไทยล้วนไม่มีวรรค) → ต้องผ่า
        return _safe_split(text, max_chars)

    n = max(2, math.ceil(clean_len(text) / max_chars))
    chunks = split_into_n(text, n)

    out = []
    for c in chunks:
        # กันเคสมีคำยาวผิดปกติก้อนเดียวลากยาวเกินเพดาน
        if clean_len(c) > max_chars * 1.5:
            out.extend(_safe_split(c, max_chars))
        else:
            out.append(c)
    return out


def distribute(total_seconds, weights):
    """แบ่งเวลารวม (วินาที) ตามน้ำหนัก แล้วปัดเป็นจำนวนเต็มให้รวมได้เท่าเดิมเป๊ะ"""
    n = len(weights)
    if n == 0:
        return []
    total_seconds = max(n, int(total_seconds))
    weights = [max(1e-6, float(w)) for w in weights]
    s = sum(weights)

    raw = [w / s * total_seconds for w in weights]
    base = [max(1, int(x)) for x in raw]

    # ปรับส่วนที่ขาด/เกิน โดยให้ช็อตที่เศษมากที่สุดได้เพิ่มก่อน
    diff = total_seconds - sum(base)
    order = sorted(range(n), key=lambda i: raw[i] - int(raw[i]), reverse=True)
    idx = 0
    while diff != 0 and order:
        i = order[idx % n]
        if diff > 0:
            base[i] += 1
            diff -= 1
        elif base[i] > 1:
            base[i] -= 1
            diff += 1
        idx += 1
        if idx > len(order) * total_seconds:
            break
    return base


# --------------------------------------------------------------- shot builder
def _scene_label(scene):
    kind = (scene.get("type") or "item").lower()
    if kind == "item":
        return f"อันดับ {scene.get('rank', '?')}"
    return {"hook": "HOOK", "intro": "เกริ่นนำ", "outro": "ปิดท้าย"}.get(kind, kind)


def _heading_parts(scene_label, scene_title):
    """กันหัวข้อซ้ำ เช่น 'เกริ่นนำ · เกริ่นนำ'"""
    label = (scene_label or "").strip()
    title = (scene_title or "").strip()
    if not title or title == label:
        return label
    return f"{label} · {title}"


def base_video_prompt(shot, topic):
    """พรอมป์ตวิดีโอภาษาอังกฤษแบบพื้นฐาน (ไม่ต้องพึ่ง LLM)"""
    subject = (shot.get("image_query") or "").replace("_", " ").strip()
    if not subject:
        subject = (shot.get("title") or topic).strip()

    camera = shot.get("camera") or CAMERA_MOVES[0]
    label = shot.get("scene_label") or ""

    parts = [
        f"{camera} of {subject}",
        f"theme: {topic}" if topic else "",
        STYLE_SUFFIX,
    ]
    if label.lower().startswith("อันดับ"):
        parts.insert(1, "energetic ranking video mood")
    return ". ".join(p for p in parts if p).strip() + "."


def clamp_durations(durations, max_seconds, total_seconds=None):
    """กันไม่ให้ช็อตไหนยาวเกินเพดาน: ส่วนที่เกินย้ายไปช็อตที่ยังมีที่ว่าง"""
    durations = list(durations)
    total = sum(durations) if total_seconds is None else int(total_seconds)

    for _ in range(len(durations) * 3):
        over = [i for i, d in enumerate(durations) if d > max_seconds]
        if not over:
            break
        for i in over:
            extra = durations[i] - max_seconds
            durations[i] = max_seconds
            for j in range(len(durations)):
                room = max_seconds - durations[j]
                if room > 0 and extra > 0:
                    take = min(room, extra)
                    durations[j] += take
                    extra -= take
                if extra <= 0:
                    break

    if sum(durations) != total:
        durations[-1] += total - sum(durations)
        if durations[-1] < 1:
            durations[-1] = 1
    return durations


def split_storyboard(storyboard, max_seconds=DEFAULT_MAX_SECONDS, topic=None):
    """แปลง storyboard → list ของช็อต ≤ max_seconds

    แบ่งจาก "เวลาของฉาก" ล้วน ๆ (ไม่ผูกกับบทพากย์ เพราะผู้ใช้จะพากย์เอง)
    เช่น ฉาก 14 วินาที + เพดาน 10 → 2 ช็อต ช็อตละ 7 วินาที
    """

    import math

    topic = topic or storyboard.get("topic") or ""
    max_seconds = max(2, int(max_seconds))

    shots = []
    shot_no = 0

    for scene in storyboard.get("scenes") or []:
        scene_id = scene.get("scene_id")
        scene_start = int(scene.get("start_seconds") or 0)
        scene_dur = max(1, int(scene.get("duration_seconds") or 1))
        text = scene.get("script_text") or ""

        n = max(1, math.ceil(scene_dur / max_seconds))
        durations = distribute(scene_dur, [1] * n)
        durations = clamp_durations(durations, max_seconds, scene_dur)

        offset = 0
        for i, dur in enumerate(durations):
            shot_no += 1
            shot = {
                "shot_id": shot_no,
                "scene_id": scene_id,
                "scene_label": _scene_label(scene),
                "scene_title": scene.get("title") or "",
                "heading": _heading_parts(_scene_label(scene), scene.get("title")),
                "scene_type": (scene.get("type") or "item").lower(),
                "rank": scene.get("rank"),
                "part": i + 1,
                "parts": len(durations),
                "start_seconds": scene_start + offset,
                "duration_seconds": dur,
                # บทพากย์ของ "ฉาก" (ไม่ใช่ของช็อต) — ไว้ให้ผู้ใช้พากย์เองทีหลัง
                "vo_text": text,
                "vo_chars": clean_len(text),
                "vo_seconds_est": round(speech_seconds(text), 1),
                "vo_scope": "scene",
                "visual": scene.get("visual") or "",
                "on_screen_text": scene.get("on_screen_text") if i == 0 else None,
                "image_query": scene.get("image_query") or "",
                "camera": CAMERA_MOVES[(shot_no - 1) % len(CAMERA_MOVES)],
            }
            shot["end_seconds"] = shot["start_seconds"] + dur
            shot["start_timecode"] = tc(shot["start_seconds"])
            shot["end_timecode"] = tc(shot["end_seconds"])
            shot["video_prompt"] = base_video_prompt(shot, topic)
            shot["negative_prompt"] = NEGATIVE_PROMPT
            shot["warn"] = (
                f"ช็อตสั้นกว่า 5 วินาที — เครื่องมือ gen ส่วนใหญ่บังคับขั้นต่ำ 5 วิ"
                if dur < 5 else ""
            )
            shots.append(shot)
            offset += dur

    return shots


# ------------------------------------------------------------------- LLM ต่อยอด
LLM_PROMPT = """คุณคือผู้กำกับและผู้เชี่ยวชาญการเขียน prompt สำหรับ AI video generation

งาน: เขียน video prompt ภาษาอังกฤษ 1 อันต่อ 1 ช็อต สำหรับวิดีโอจัดอันดับเรื่อง "{topic}"

บริบทสำคัญ
- วิดีโอนี้ **ไม่มีเสียงในตัว** ผู้ใช้จะพากย์เสียงเองทีหลัง
- ดังนั้นพรอมป์ตต้องบรรยาย "ภาพ" เท่านั้น ห้ามพูดถึงการพูด การบรรยาย หรือเสียง
- ฉากหนึ่งอาจถูกแบ่งเป็นหลายช็อต (ช็อตที่ 2/3 ของฉาก ฯลฯ) ให้แต่ละช็อตเป็นมุมกล้อง/จังหวะที่ต่างกัน
  แต่ยังเล่าเรื่องเดียวกันต่อเนื่องกัน ดูแล้วต่อกันได้ลื่น

กติกา (สำคัญ)
- 1 พรอมป์ต ยาว 35-60 คำ เป็นภาษาอังกฤษล้วน
- ต้องบรรยาย: ตัวแบบหลัก + การเคลื่อนไหว/แอ็กชัน + มุมกล้อง/การเคลื่อนกล้อง + แสง + อารมณ์ภาพ + สไตล์
- ใช้ข้อมูล "ภาพที่ต้องเห็น" (visual) และ "คำค้นภาพ" (image_query) เป็นแกน ห้ามเปลี่ยนเนื้อหา
- ห้ามให้มีตัวอักษร ข้อความ ป้าย หรือโลโก้ในภาพ
- ห้ามใส่ค่า aspect ratio / ความละเอียด (ระบบเติมให้เอง)
- ภาพแนวท่องเที่ยว–สารคดี–ของกิน ให้ดูสมจริง ถ่ายด้วยกล้องจริง
- ถ้า visual บอกว่าเป็นภาพกราฟิก/แผนที่/ตัวเลข ให้เขียนว่าภาพกราฟิกเคลื่อนไหวสไตล์โมชันกราฟิกส์
- ห้ามให้ช็อตที่อยู่ฉากเดียวกันใช้พรอมป์ตซ้ำกัน ต้องเปลี่ยนมุมมอง/ระยะภาพ

ข้อมูลช็อตทั้งหมด ({count} ช็อต):
{shots}

ตอบเป็น JSON เท่านั้น รูปแบบ:
{{"shots":[{{"id":1,"prompt":"..."}},{{"id":2,"prompt":"..."}}]}}
"""


def _shots_for_llm(shots):
    lines = []
    for s in shots:
        part = (
            f"ช็อตที่ {s['part']}/{s['parts']} ของฉาก"
            if s.get("parts", 1) > 1 else "ช็อตเดียวของฉาก"
        )
        lines.append(
            f"- id={s['shot_id']} | ฉาก {s['scene_id']} ({s['scene_label']} · {s['scene_title']}) "
            f"| {s['duration_seconds']}s | {part}\n"
            f"  ภาพที่ต้องเห็นของฉาก: {s.get('visual') or '-'}\n"
            f"  คำค้นภาพ: {s.get('image_query') or '-'}\n"
            f"  มุมกล้องที่แนะนำ: {s.get('camera') or '-'}"
        )
    return "\n".join(lines)


def polish_prompts_with_llm(shots, topic, batch_size=12, verbose=True):
    """เรียบเรียง video prompt ให้ละเอียดขึ้นด้วย LLM (ถ้าใช้ไม่ได้จะคืนค่าเดิม)"""
    if not shots:
        return shots

    try:
        from app.llm_gemini import generate_json
    except Exception as e:  # pragma: no cover
        if verbose:
            print(f"[shots] ใช้พรอมป์ตพื้นฐาน (import LLM ไม่ได้: {e})")
        return shots

    by_id = {s["shot_id"]: s for s in shots}
    total = len(shots)
    for start in range(0, total, batch_size):
        batch = shots[start:start + batch_size]
        prompt = LLM_PROMPT.format(
            topic=topic, count=len(batch), shots=_shots_for_llm(batch)
        )
        try:
            data = generate_json(prompt, temperature=0.8)
        except Exception as e:
            if verbose:
                print(f"[shots] LLM เรียบเรียงพรอมป์ตไม่สำเร็จ: {str(e)[:200]}")
            continue

        for row in (data or {}).get("shots") or []:
            try:
                sid = int(row.get("id"))
                text = (row.get("prompt") or "").strip()
            except (TypeError, ValueError):
                continue
            if sid in by_id and len(text) > 20:
                by_id[sid]["video_prompt"] = text
                by_id[sid]["prompt_source"] = "llm"

    return shots


# ------------------------------------------------------------------- outputs
def attach_reference_images(shots, images_dir, shots_dir):
    """คัดลอกรูปอ้างอิงของแต่ละช็อตไว้ในโฟลเดอร์ shots/ (พร้อมพรอมป์ตเป็น .txt)"""
    os.makedirs(shots_dir, exist_ok=True)

    # ล้างไฟล์ช็อตจากรอบก่อน (กันไฟล์เก่าค้างเมื่อจำนวนช็อตเปลี่ยน)
    for fname in os.listdir(shots_dir):
        if re.match(r"^(shot_\d+_(ref|prompt)\.|scene_\d+_vo\.txt$)", fname):
            try:
                os.remove(os.path.join(shots_dir, fname))
            except OSError:
                pass

    per_scene = {}
    if images_dir and os.path.isdir(images_dir):
        for fname in sorted(os.listdir(images_dir)):
            m = re.match(r"scene_(\d+)_img", fname)
            if m:
                per_scene.setdefault(int(m.group(1)), []).append(
                    os.path.join(images_dir, fname)
                )

    for s in shots:
        scene_no = int(s["scene_id"] or 0)
        files = per_scene.get(scene_no, [])
        s["ref_image"] = None
        s["ref_note"] = ""
        if not files:
            # ยืมรูปจากฉากที่ใกล้ที่สุด (ให้ยังใช้โหมด image-to-video ได้)
            for dist in range(1, 15):
                for cand in (scene_no - dist, scene_no + dist):
                    if cand in per_scene:
                        files = per_scene[cand]
                        s["ref_note"] = f"ยืมรูปจากฉาก {cand}"
                        break
                if files:
                    break
        if not files:
            continue
        src = files[(s["part"] - 1) % len(files)]
        ext = os.path.splitext(src)[1].lower() or ".jpg"

        dst = os.path.join(shots_dir, f"shot_{s['shot_id']:02d}_ref{ext}")
        try:
            from app.docx_writer import _prepare_image
            import tempfile

            tmp = tempfile.mkdtemp(prefix="shotimg_")
            prepared = _prepare_image(src, tmp)
            if prepared and os.path.isfile(prepared):
                with open(prepared, "rb") as f:
                    data = f.read()
                dst = os.path.join(shots_dir, f"shot_{s['shot_id']:02d}_ref.jpg")
                with open(dst, "wb") as f:
                    f.write(data)
            else:
                with open(src, "rb") as f:
                    data = f.read()
                with open(dst, "wb") as f:
                    f.write(data)
            import shutil

            shutil.rmtree(tmp, ignore_errors=True)
            s["ref_image"] = os.path.basename(dst)
        except Exception as e:
            print(f"[shots] คัดลอกรูปช็อต {s['shot_id']} ไม่ได้: {e}")

        # ไฟล์ข้อความสำหรับ workflow แบบลากไฟล์วาง
        try:
            with open(os.path.join(shots_dir, f"shot_{s['shot_id']:02d}_prompt.txt"),
                      "w", encoding="utf-8") as f:
                f.write(s["video_prompt"])
        except Exception as e:
            print(f"[shots] เขียนไฟล์ txt ช็อต {s['shot_id']} ไม่ได้: {e}")

    # บทพากย์เขียนแยกเป็นรายฉาก (ผู้ใช้พากย์เอง ไม่ผูกกับช็อต)
    seen = set()
    for s in shots:
        sid = s.get("scene_id")
        if sid in seen:
            continue
        seen.add(sid)
        try:
            with open(os.path.join(shots_dir, f"scene_{int(sid):02d}_vo.txt"),
                      "w", encoding="utf-8") as f:
                f.write(s.get("vo_text") or "")
        except Exception as e:
            print(f"[shots] เขียนบทพากย์ฉาก {sid} ไม่ได้: {e}")

    return shots


def write_shots_json(shots, meta, path):
    payload = {"meta": meta, "shots": shots}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return path


def write_shots_csv(shots, path):
    fields = [
        "shot_id", "scene_id", "scene_label", "scene_title", "part", "parts",
        "start_timecode", "end_timecode", "duration_seconds",
        "video_prompt", "negative_prompt", "vo_text", "vo_chars",
        "vo_seconds_est", "on_screen_text", "ref_image",
    ]
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for s in shots:
            w.writerow({k: s.get(k, "") for k in fields})
    return path


def write_shots_readme(shots, topic, max_seconds, path):
    total = sum(s["duration_seconds"] for s in shots)
    lines = [
        f"# ช็อตสำหรับ gen วิดีโอ — 10 อันดับ {topic}",
        "",
        f"- จำนวนช็อต: **{len(shots)} ช็อต**",
        f"- ความยาวสูงสุดต่อช็อต: **{max_seconds} วินาที** "
        f"(รวม {total} วินาที = {total/60:.1f} นาที)",
        "",
        "## ไฟล์ในโฟลเดอร์นี้",
        "",
        "| ไฟล์ | ใช้ทำอะไร |",
        "|---|---|",
        "| `video_prompts.docx` | ⭐ พรอมป์ตทั้งหมด + รูปอ้างอิง เปิดอ่าน/ก๊อปง่าย |",
        "| `shots.csv` | เปิดใน Excel เพื่อทำทีละแถว / เช็กสถานะ |",
        "| `shots.json` | ให้โปรแกรมอื่นอ่านต่อ |",
        "| `shots/shot_XX_prompt.txt` | พรอมป์ตของช็อตนั้น (ก๊อปวางได้เลย) |",
        "| `shots/shot_XX_ref.jpg` | รูปอ้างอิง (อัปเป็น start frame) |",
        "| `shots/scene_XX_vo.txt` | บทพากย์ของฉาก (ไว้พากย์เสียงเอง) |",
        "",
        "## หลักการแบ่งช็อต",
        "",
        f"- แบ่งจาก **เวลาของภาพ** ล้วน ๆ ไม่เกี่ยวกับบทพากย์ "
        f"(เช่น ฉาก 14 วิ + เพดาน {max_seconds} วิ → 2 ช็อต ช็อตละ 7 วิ)",
        "- บทพากย์ไม่ถูกตัดตามช็อต เพราะพี่จะพากย์เสียงเองทีหลัง",
        "- เวลาของทุกช็อตรวมกันแล้วเท่ากับความยาวคลิปเป๊ะ",
        "",
        "## ขั้นตอน gen วิดีโอ (ใช้ของฟรี)",
        "",
        "1. เปิด `video_prompts.docx` ดูช็อตที่ 1",
        "2. เข้าเครื่องมือ gen วิดีโอที่ใช้ (ดูรายชื่อด้านล่าง)",
        "3. **Image to Video** → อัปโหลด `shots/shot_01_ref.jpg`",
        "4. ก๊อปพรอมป์ตจากช็อต 1 วางในช่อง prompt",
        "5. ตั้งความยาว 5–10 วินาที, อัตราส่วน 9:16 (หรือ 16:9 ตามช่องทาง)",
        "6. โหลดไฟล์ที่ได้ เปลี่ยนชื่อเป็น `shot_01.mp4` เก็บรวมกัน",
        "7. ทำซ้ำกับช็อตถัดไป แล้วนำไปเรียงต่อกันตอนตัดต่อ",
        "",
        "## เครื่องมือที่ใช้ฟรีได้ (โควตารายวัน)",
        "",
        "| เครื่องมือ | ฟรี | จุดเด่น |",
        "|---|---|---|",
        "| **Kling AI** | เครดิตฟรีรายวัน | image-to-video คุณภาพดี รองรับ 10 วิ |",
        "| **Hailuo / MiniMax** | เครดิตฟรีรายวัน | เคลื่อนกล้องลื่น |",
        "| **Dreamina (CapCut)** | เครดิตฟรีรายวัน | ต่อกับ CapCut ได้เลย |",
        "| **Google Veo ใน Gemini** | จำกัดจำนวน/วัน | คมชัดที่สุด แต่คิวช้า |",
        "| **Pika / Luma Dream Machine** | ทดลองฟรี | เร็ว เหมาะทดสอบ |",
        "",
        "> เคล็ดลับ: ทำทีละ 5–10 ช็อตต่อวัน แล้วเก็บไฟล์เป็น `shot_XX.mp4` "
        "เพื่อให้ต่อกลับมาง่ายในตอนตัดต่อ",
        "",
        "## หมายเหตุเรื่องความยาว",
        "",
        f"- แต่ละช็อต ≤ {max_seconds} วินาที และเวลารวมของทุกช็อตเท่ากับความยาวคลิปพอดี",
        "- **ช็อตที่สั้นกว่า 5 วินาที**: เครื่องมือ gen วิดีโอส่วนใหญ่บังคับยาวขั้นต่ำ 5 วินาที "
        "ให้เรนเดอร์ 5 วินาทีแล้วตัดทิ้งตอนตัดต่อ",
        "- พากย์เสียงเองทีหลังโดยใช้บทจาก `script.docx` หรือ `shots/scene_XX_vo.txt`",
        "- ถ้าอยากได้ช็อตสั้น/ยาวกว่านี้ ตั้งค่า `SHOT_MAX_SECONDS` ใน `.env` "
        "หรือเรียก `POST /jobs/{id}/shots?max_seconds=...` เพื่อสร้างใหม่",
        "",
    ]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return path
