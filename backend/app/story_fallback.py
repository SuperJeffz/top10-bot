"""บทสตอรี่บอร์ดสำรองแบบออฟไลน์

ใช้เมื่อ Gemini ทุกโมเดลไม่พร้อม (503/404/quota หมด) เพื่อให้งานยังเสร็จ
และได้ไฟล์ Word ครบชุด แม้คุณภาพภาษาจะสู้บทที่ AI เขียนให้ไม่ได้ก็ตาม
"""


def build_offline_storyboard(topic: str, minutes: int):
    topic = (topic or "").strip() or "หัวข้อนี้"
    scenes = []

    scenes.append({
        "scene_id": 1,
        "type": "hook",
        "title": "Hook เปิดคลิป",
        "script_text": (
            f"คุณอาจยังไม่รู้ว่าสิ่งที่อยู่ใน '{topic}' อันดับต้น ๆ "
            "คือสิ่งที่คนส่วนใหญ่มักมองข้าม — ดูให้จบก่อนใคร จะได้ไม่พลาดอันดับ 1"
        ),
        "visual": f"ภาพใกล้ ๆ ของ {topic} แสงอบอุ่น มีตัวเลข 10 ปรากฏบนจอ",
        "on_screen_text": "ดูให้จบ!",
        "duration_seconds": 5,
        "image_query": "top 10 ranking cinematic close up",
    })

    scenes.append({
        "scene_id": 2,
        "type": "intro",
        "title": "เกริ่นนำ",
        "script_text": (
            f"คลิปนี้เราจะจัดอันดับ {topic} กันแบบไม่ต้องเดา "
            "โดยไล่จากอันดับ 10 ขึ้นไปถึงอันดับ 1 พร้อมเหตุผลที่แต่ละอันดับสมควรอยู่ในลิสต์"
        ),
        "visual": f"ภาพมุมกว้างของ {topic} พร้อมแถบข้อความจัดอันดับ 10 อันดับ",
        "on_screen_text": None,
        "duration_seconds": 6,
        "image_query": "top 10 list infographic background",
    })

    for rank in range(10, 0, -1):
        left = rank - 1
        next_text = f"อีก {left} อันดับกำลังจะมาถึง" if left else "นี่คืออันดับ 1 ที่หลายคนรอคอย"
        scenes.append({
            "scene_id": 3 + (10 - rank),
            "type": "item",
            "rank": rank,
            "title": f"อันดับ {rank}",
            "script_text": (
                f"อันดับ {rank} ในเรื่อง {topic} พิเศษตรงที่ให้ทั้งความคุ้มค่า "
                f"และเรื่องราวที่เล่าต่อได้ทันที {next_text} — รับรองว่ามีอย่างน้อยหนึ่งอันดับ "
                "ที่ทำให้คุณเปลี่ยนใจแน่"
            ),
            "visual": f"ภาพสตอรี่บอร์ดของ {topic} พร้อมเลขอันดับ {rank} เด่นชัดบนจอ",
            "on_screen_text": f"อันดับ {rank}",
            "duration_seconds": 8,
            "image_query": f"{topic} rank {rank} cinematic",
        })

    scenes.append({
        "scene_id": 13,
        "type": "outro",
        "title": "ปิดท้าย",
        "script_text": (
            f"มาถึงอันดับ 1 ของ {topic} แล้ว ใครที่ชอบความคุ้มค่าและเรื่องราวมีวิธีคิด "
            "นี่คืออันดับที่ใช่สำหรับคุณ คอมเมนต์บอกหน่อยว่าคุณยกให้ใครอันดับ 1 "
            "แล้วกดไลก์ติดตามไว้นะ"
        ),
        "visual": f"ภาพสรุปทั้ง 10 อันดับของ {topic} แบบตารางสวย ๆ",
        "on_screen_text": None,
        "duration_seconds": 6,
        "image_query": "top 10 summary ranking board",
    })

    return {
        "topic": topic,
        "total_minutes": minutes,
        "total_seconds": minutes * 60,
        "scenes": scenes,
    }
