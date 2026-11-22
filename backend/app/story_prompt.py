"""ตัวช่วยสร้าง prompt และจัดเรียงเวลาให้ตรงกับจำนวนนาที (ใช้ร่วมกันทุก provider)"""


def tc(sec):
    h, rem = divmod(int(sec), 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def _speech_seconds(text, chars_per_second=12.0):
    """ประมาณเวลาที่ใช้พูดจริงจากความยาวข้อความ (ภาษาไทย ~12 ตัวอักษร/วินาที)"""
    clean = "".join(ch for ch in (text or "") if not ch.isspace())
    if not clean:
        return 0.0
    return len(clean) / chars_per_second


def normalize_timings(scenes, total_seconds, use_text_length=False):
    """บังคับให้เวลารวมของทุกฉากเท่ากับ total_seconds พอดี และใส่ timecode ให้

    use_text_length=True → กระจายเวลาตามความยาวบทพูด (แม่นกว่าค่าที่โมเดลเดา)
    """
    if use_text_length:
        durations = [max(2, round(_speech_seconds(s.get("script_text")))) for s in scenes]
    else:
        durations = [max(1, int(s.get("duration_seconds") or 1)) for s in scenes]
    current = sum(durations)
    if current <= 0:
        durations = [max(1, total_seconds // max(1, len(scenes)))] * len(scenes)
        current = sum(durations)

    scaled = [max(1, round(d * total_seconds / current)) for d in durations]

    diff = total_seconds - sum(scaled)
    i = 0
    while diff != 0 and scaled:
        idx = i % len(scaled)
        if diff > 0:
            scaled[idx] += 1
            diff -= 1
        elif scaled[idx] > 1:
            scaled[idx] -= 1
            diff += 1
        i += 1

    t = 0
    for s, d in zip(scenes, scaled):
        s["duration_seconds"] = d
        s["start_seconds"] = t
        s["end_seconds"] = t + d
        s["start_timecode"] = tc(t)
        s["end_timecode"] = tc(t + d)
        t += d
    return scenes


def build_prompt(topic: str, minutes: int, words_per_second: float = 2.5):
    total_seconds = minutes * 60
    hook_s = max(4, min(8, round(total_seconds * 0.05)))
    intro_s = max(6, round(total_seconds * 0.06))
    outro_s = max(6, round(total_seconds * 0.07))
    per_item = max(8, round((total_seconds - hook_s - intro_s - outro_s) / 10))
    # ภาษาไทยพูดเร็วประมาณ 12 ตัวอักษร/วินาที (ไม่นับช่องว่าง)
    total_chars = int(total_seconds * 12)
    per_item_chars = max(40, int((total_chars - 200) / 10))

    return f"""คุณคือนักเขียนบทวิดีโอ YouTube สายจัดอันดับ (Top 10) ระดับมืออาชีพของประเทศไทย
งานของคุณคือเขียนบทวิดีโอ "10 อันดับ {topic}" ความยาวรวม {minutes} นาที ({total_seconds} วินาที)
บทนี้จะถูกนำไปบันทึกเสียงพากย์และตัดต่อภาพตามสตอรี่บอร์ด ทุกฉากจึงต้องมีทั้ง "บทพูด" และ "ภาพที่ต้องเห็น"

## โครงสร้างบังคับ 13 ฉาก (ห้ามตัดห้ามเพิ่ม)
1. ฉากที่ 1 — type = "hook" (3–{hook_s} วินาที): **Hook เปิดคลิป**
   - ประโยคเดียวหรือสองประโยคสั้น ๆ ที่ทำให้คนหยุดดูทันที ภายใน 3 วินาทีแรก
   - ต้อง**เกี่ยวข้องกับหัวข้อตรง ๆ** และสร้างช่องว่างความอยากรู้ (curiosity gap) เช่น คำถาม shocking,
     ตัวเลข/สถิติที่ค้านความรู้สึก, คำเตือน, หรือประโยคที่ทำให้คนคิดว่า "เดี๋ยว ๆ อะไรนะ"
   - **ห้าม**ขึ้นต้นด้วย "สวัสดีครับ/ค่ะ", "วันนี้เราจะพาไปดู", "คลิปนี้จะพาคุณไปรู้จัก" หรือประโยคแนะนำตัวใด ๆ
   - ตัวอย่าง Hook ที่ดี: "คุณอาจไม่เคยรู้ว่า 7 ใน 10 ของ {topic} ที่คนพูดถึงกัน คือของปลอม"
2. ฉากที่ 2 — type = "intro" (สั้น ๆ {intro_s} วินาที): **เกริ่นนำ**
   - ต่อจาก hook ทันที ด้วย 1–2 ประโยค บอกว่าคลิปนี้จะพาไปดูอะไร เกณฑ์การจัดอันดับคืออะไร
     และทำไมต้องดูจนจบ (เช่น มีอันดับ 1 ที่คาดไม่ถึง) แล้วปิดด้วยการเปลี่ยนผ่านไปอันดับ 10
   - ห้ามย้ำ hook และห้ามเกริ่นยาว
3. ฉากที่ 3–12 — type = "item" เรียงจาก **อันดับ 10 ไล่ลงไปถึงอันดับ 1**
   - แต่ละอันดับมี `rank` ระบุชัดเจน, ชื่อชัดเจน, 1–2 เหตุผลที่น่าสนใจ,
     รายละเอียดเฉพาะเจาะจง (ตัวเลข/สถานที่/ชื่อจริง/ปี) ไม่ใช่คำกว้าง ๆ
   - ยาวประมาณ {per_item} วินาทีต่ออันดับ
   - ปิดท้ายอันดับด้วยการทิ้งท้าย (cliffhanger) สั้น ๆ เพื่อดึงไปอันดับถัดไป
4. ฉากที่ 13 — type = "outro" (สั้น ๆ {outro_s} วินาที): **ปิดท้าย**
   - สรุปสั้น ๆ + ชี้ให้เห็นว่าอันดับ 1 เหมาะกับใคร + ถามคำถามปลายเปิดให้คนคอมเมนต์
   - ชวนกดไลก์/ติดตามแบบเป็นธรรมชาติ

## กติกาการเขียน (สำคัญมาก)
- **โทนเสียง** กระตือรือร้น เป็นกันเอง มีอารมณ์ขันเบา ๆ เหมือนพี่เล่าให้เพื่อนฟัง
- **ภาษาไทยพูดลื่น** ใช้ประโยคสั้น อ่านออกเสียงแล้วไหล ไม่ใช้ภาษาเขียนราชการ
- **ห้ามขึ้นต้นประโยคซ้ำกัน** ด้วย "ซึ่ง" / "โดย" / "นอกจากนี้" ติดกันหลายฉาก
- **ห้ามผสมภาษาอังกฤษในบทพูด** (script_text) ต้องเป็นภาษาไทยล้วน อ่านออกเสียงได้ไหล
  ถ้าจำเป็นต้องใช้คำทับศัพท์ ให้เขียนเป็นไทย (เช่น "นอร์ทเทิร์นสไตล์" ไม่ใช่ "northern style")
  ส่วน image_query ให้เป็นภาษาอังกฤษตามปกติ
- **เชื่อมโยงอันดับ** ให้มีการอ้างถึงอันดับก่อนหน้าอย่างน้อย 3 ครั้ง (เช่น "จากอันดับ 7 ที่พูดไป...")
- **ภาพต้องสัมพันธ์กับบท** — `visual` ต้องบอกว่าจอเห็นอะไรจริง ๆ ในจังหวะนั้น
  (เช่น "ภาพใกล้ ๆ น้ำกะทิราดข้าวเหนียวมะม่วง ฉากหลังเป็นร้านกลางคืน")
- **คำค้นภาพ** (`image_query`) เป็นภาษาอังกฤษสั้น 3–6 คำ ค้นแล้วได้ภาพจริง
  เจาะจงชื่อสถานที่/วัตถุ (ห้ามใช้คำนามลอย ๆ อย่าง "food" หรือ "amazing")
- **ข้อความบนจอ** (`on_screen_text`) สั้นไม่เกิน 6 คำ ภาษาไทย (หรือ null ถ้าไม่ต้องมี)
- **ความยาวบทพูด (สำคัญ)** — รวมทั้งคลิปประมาณ **{total_chars} ตัวอักษร** (ไม่นับช่องว่าง)
  / แต่ละอันดับยาวประมาณ **{per_item_chars} ตัวอักษร** / hook ไม่เกิน 80 ตัวอักษร
  ถ้าเขียนเกินกว่านี้ คนพากย์จะพูดไม่ทันเวลาจริง
- **ตอบเป็น JSON เท่านั้น** ห้ามมีข้อความอื่น ห้ามใช้ markdown code fence

## โครงสร้าง JSON (ทุกฉากต้องมีครบทุกฟิลด์)
{{"topic":"{topic}","total_minutes":{minutes},"scenes":[
{{"scene_id":1,"type":"hook","title":"Hook เปิดคลิป","script_text":"...","visual":"...","on_screen_text":"...","duration_seconds":{hook_s},"image_query":"..."}},
{{"scene_id":2,"type":"intro","title":"เกริ่นนำ","script_text":"...","visual":"...","on_screen_text":null,"duration_seconds":{intro_s},"image_query":"..."}},
{{"scene_id":3,"type":"item","rank":10,"title":"...","script_text":"...","visual":"...","on_screen_text":"...","duration_seconds":{per_item},"image_query":"..."}},
{{"scene_id":4,"type":"item","rank":9,"title":"...","script_text":"...","visual":"...","on_screen_text":"...","duration_seconds":{per_item},"image_query":"..."}},
{{"scene_id":5,"type":"item","rank":8,"title":"...","script_text":"...","visual":"...","on_screen_text":"...","duration_seconds":{per_item},"image_query":"..."}},
{{"scene_id":6,"type":"item","rank":7,"title":"...","script_text":"...","visual":"...","on_screen_text":"...","duration_seconds":{per_item},"image_query":"..."}},
{{"scene_id":7,"type":"item","rank":6,"title":"...","script_text":"...","visual":"...","on_screen_text":"...","duration_seconds":{per_item},"image_query":"..."}},
{{"scene_id":8,"type":"item","rank":5,"title":"...","script_text":"...","visual":"...","on_screen_text":"...","duration_seconds":{per_item},"image_query":"..."}},
{{"scene_id":9,"type":"item","rank":4,"title":"...","script_text":"...","visual":"...","on_screen_text":"...","duration_seconds":{per_item},"image_query":"..."}},
{{"scene_id":10,"type":"item","rank":3,"title":"...","script_text":"...","visual":"...","on_screen_text":"...","duration_seconds":{per_item},"image_query":"..."}},
{{"scene_id":11,"type":"item","rank":2,"title":"...","script_text":"...","visual":"...","on_screen_text":"...","duration_seconds":{per_item},"image_query":"..."}},
{{"scene_id":12,"type":"item","rank":1,"title":"...","script_text":"...","visual":"...","on_screen_text":"...","duration_seconds":{per_item},"image_query":"..."}},
{{"scene_id":13,"type":"outro","title":"ปิดท้าย","script_text":"...","visual":"...","on_screen_text":null,"duration_seconds":{outro_s},"image_query":"..."}}
]}}"""


def _fill_defaults(scenes):
    """เติมฟิลด์ที่ขาด (เผื่อโมเดลลืม) ให้สตอรี่บอร์ดสมบูรณ์"""
    last = len(scenes) - 1
    for i, s in enumerate(scenes):
        if not s.get("type"):
            if i == 0:
                s["type"] = "hook"
            elif i == 1:
                s["type"] = "intro"
            elif i == last:
                s["type"] = "outro"
            else:
                s["type"] = "item"
        s.setdefault("title", {"hook": "Hook เปิดคลิป", "intro": "เกริ่นนำ",
                               "outro": "ปิดท้าย"}.get(s["type"], f"อันดับ {s.get('rank', i)}"))
        if not s.get("visual"):
            s["visual"] = s.get("title", "")
        s.setdefault("on_screen_text", None)


def finalize(data, topic, minutes):
    """ตรวจ/เติมข้อมูลที่จำเป็นหลังได้ JSON จากโมเดล"""
    scenes = data.get("scenes") or []
    if not scenes:
        raise ValueError("โมเดลไม่ได้ส่ง scenes กลับมา")

    for i, s in enumerate(scenes, start=1):
        s.setdefault("scene_id", i)

    _fill_defaults(scenes)
    # กระจายเวลาตามความยาวบทพูดจริง เพื่อให้ timecode ตรงกับเสียงพากย์
    data["scenes"] = normalize_timings(scenes, minutes * 60, use_text_length=True)
    data["topic"] = topic
    data["total_minutes"] = minutes
    data["total_seconds"] = minutes * 60
    return data
