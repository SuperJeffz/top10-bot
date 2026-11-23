"""สร้างไฟล์ Word (.docx)
1) script.docx      — บทพูด + ตารางเวลา (อ่านง่าย)
2) storyboard.docx  — สตอรี่บอร์ดสำหรับตัดต่อ (ภาพ + สิ่งที่เห็นบนจอ + เสียงพากย์)
"""

import os

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

THAI_FONT = "Sarabun"

TYPE_LABEL = {
    "hook": "HOOK",
    "intro": "เกริ่นนำ",
    "item": "อันดับ",
    "outro": "ปิดท้าย",
}

GREY = RGBColor(0x77, 0x77, 0x77)
BLUE = RGBColor(0x1D, 0x4E, 0xD8)


def _apply_font(obj, name=THAI_FONT):
    """ตั้งชื่อฟอนต์ให้รองรับภาษาไทย (ทั้ง ascii / hAnsi / eastAsia / cs)"""
    obj.font.name = name
    rpr = obj.element.get_or_add_rPr()
    rfonts = rpr.get_or_add_rFonts()
    for attr in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
        rfonts.set(qn(attr), name)


def _setup(doc):
    for style_name in ("Normal", "Title", "Heading 1", "Heading 2", "Heading 3"):
        try:
            _apply_font(doc.styles[style_name])
        except KeyError:
            pass
    doc.styles["Normal"].font.size = Pt(12)
    for section in doc.sections:
        section.left_margin = Cm(2.2)
        section.right_margin = Cm(2.2)
        section.top_margin = Cm(1.8)
        section.bottom_margin = Cm(1.8)


def _para(doc, text, size=12, bold=False, color=None, align=None, space_after=None):
    p = doc.add_paragraph()
    if align is not None:
        p.alignment = align
    if space_after is not None:
        p.paragraph_format.space_after = Pt(space_after)
    run = p.add_run(text)
    run.bold = bold
    run.font.size = Pt(size)
    if color is not None:
        run.font.color.rgb = color
    _apply_font(run)
    return p


def _scene_label(s):
    kind = (s.get("type") or "item").lower()
    label = TYPE_LABEL.get(kind, kind)
    if kind == "item":
        label = f"อันดับ {s.get('rank', '?')}"
    return label


def _cover(doc, storyboard, subtitle):
    _para(
        doc,
        f"10 อันดับ {storyboard['topic']}",
        size=22, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER,
    )
    _para(
        doc,
        f"{subtitle} · ความยาว {storyboard['total_minutes']} นาที "
        f"({storyboard['total_seconds']} วินาที) · {len(storyboard['scenes'])} ฉาก",
        size=11, color=GREY, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=14,
    )


# ---------------------------------------------------------------- script.docx
def build_docx(storyboard, path):
    """บทพูด + ตารางเวลา"""
    doc = Document()
    _setup(doc)
    _cover(doc, storyboard, "บทวิดีโอ")

    _para(doc, "ตารางเวลา (Timeline)", size=14, bold=True)
    table = doc.add_table(rows=1, cols=5)
    table.style = "Light Grid Accent 1"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, text in enumerate(["ฉาก", "เริ่ม", "จบ", "ระยะ", "หัวข้อ"]):
        cell = table.rows[0].cells[i]
        cell.text = ""
        run = cell.paragraphs[0].add_run(text)
        run.bold = True
        run.font.size = Pt(10)
        _apply_font(run)

    for s in storyboard["scenes"]:
        cells = table.add_row().cells
        values = [
            str(s["scene_id"]),
            s["start_timecode"],
            s["end_timecode"],
            f"{s['duration_seconds']}s",
            f"{_scene_label(s)} · {s.get('title', '')}",
        ]
        for i, text in enumerate(values):
            cells[i].text = ""
            run = cells[i].paragraphs[0].add_run(text)
            run.font.size = Pt(10)
            _apply_font(run)

    doc.add_page_break()
    _para(doc, "บทพูด (Voice Over)", size=18, bold=True)

    for s in storyboard["scenes"]:
        head = doc.add_paragraph()
        hr = head.add_run(f"{s['scene_id']}. [{_scene_label(s)}] {s.get('title', '')}")
        hr.bold = True
        hr.font.size = Pt(13)
        _apply_font(hr)

        meta = doc.add_paragraph()
        mr = meta.add_run(
            f"⏱ {s['start_timecode']} – {s['end_timecode']} "
            f"({s['duration_seconds']} วินาที)"
            + (f"   🖼 ภาพ: {s['image_query']}" if s.get("image_query") else "")
        )
        mr.font.size = Pt(9)
        mr.font.color.rgb = GREY
        _apply_font(mr)

        p = doc.add_paragraph()
        p.paragraph_format.line_spacing = 1.5
        p.paragraph_format.space_after = Pt(12)
        pr = p.add_run(s.get("script_text", ""))
        pr.font.size = Pt(12)
        _apply_font(pr)

    doc.save(path)
    return path


# ------------------------------------------------------------ storyboard.docx
def _prepare_image(img_path, tmp_dir):
    """ตรวจ/ย่อรูป + แปลง webp ให้ Word ฝังได้ (ใช้ Pillow ถ้ามี)"""
    if not os.path.isfile(img_path):
        return None

    try:
        from PIL import Image
    except ImportError:
        # ไม่มี Pillow: ให้ลองฝังตรง ๆ (ยกเว้น webp ที่ Word ไม่รองรับ)
        return None if img_path.lower().endswith(".webp") else img_path

    try:
        im = Image.open(img_path)
        im.load()
    except Exception:
        return None  # ไฟล์เสีย/ไม่ใช่รูปจริง

    # แปลงเป็น JPEG มาตรฐานทุกครั้ง (กัน JPEG บางแบบที่ python-docx อ่านไม่ได้)
    try:
        if im.mode in ("RGBA", "LA", "P"):
            im = im.convert("RGBA")
            bg = Image.new("RGB", im.size, (255, 255, 255))
            bg.paste(im, mask=im.split()[-1])
            im = bg
        else:
            im = im.convert("RGB")
        if im.width > 1280:
            im.thumbnail((1280, 1280))
        out = os.path.join(tmp_dir, "s_" + os.path.basename(img_path) + ".jpg")
        im.save(out, "JPEG", quality=88)
        return out
    except Exception:
        return None


def _scene_images(images_dir, scene_id):
    if not images_dir or not os.path.isdir(images_dir):
        return []
    prefix = f"scene_{scene_id:02d}_img"
    return [
        os.path.join(images_dir, f)
        for f in sorted(os.listdir(images_dir))
        if f.startswith(prefix)
    ]


def build_storyboard_docx(storyboard, images_dir, path):
    """สตอรี่บอร์ด: 1 ฉาก = 1 หน้า มีรูป + สิ่งที่เห็นบนจอ + บทพากย์"""
    import shutil
    import tempfile

    tmp_dir = tempfile.mkdtemp(prefix="sb_img_")
    doc = Document()
    _setup(doc)
    _cover(doc, storyboard, "สตอรี่บอร์ดสำหรับตัดต่อ")

    # --- shot list สรุปสั้น ๆ ---
    _para(doc, "ลำดับภาพ (Shot List)", size=14, bold=True)
    table = doc.add_table(rows=1, cols=4)
    table.style = "Light Grid Accent 1"
    for i, text in enumerate(["ฉาก", "ประเภท", "เวลา", "สิ่งที่เห็นบนจอ"]):
        cell = table.rows[0].cells[i]
        cell.text = ""
        run = cell.paragraphs[0].add_run(text)
        run.bold = True
        run.font.size = Pt(9)
        _apply_font(run)

    for s in storyboard["scenes"]:
        cells = table.add_row().cells
        values = [
            str(s["scene_id"]),
            _scene_label(s),
            f"{s['start_timecode']}–{s['end_timecode']}",
            s.get("visual") or s.get("title", ""),
        ]
        for i, text in enumerate(values):
            cells[i].text = ""
            run = cells[i].paragraphs[0].add_run(text)
            run.font.size = Pt(9)
            _apply_font(run)

    # --- รายละเอียดทีละฉาก ---
    for s in storyboard["scenes"]:
        doc.add_page_break()

        head = doc.add_paragraph()
        hr = head.add_run(
            f"ฉาก {s['scene_id']} · {_scene_label(s)} · {s.get('title', '')}"
        )
        hr.bold = True
        hr.font.size = Pt(16)
        _apply_font(hr)

        meta = doc.add_paragraph()
        mr = meta.add_run(
            f"⏱ {s['start_timecode']} – {s['end_timecode']} "
            f"({s['duration_seconds']} วินาที)"
        )
        mr.font.size = Pt(10)
        mr.font.color.rgb = GREY
        _apply_font(mr)

        imgs = _scene_images(images_dir, s["scene_id"])
        tbl = doc.add_table(rows=1, cols=2)
        tbl.style = "Table Grid"
        left, right = tbl.rows[0].cells
        left.width = Cm(8.4)
        right.width = Cm(8.6)

        # ซ้าย: รูปอ้างอิง
        left.paragraphs[0].text = ""
        if imgs:
            placed = 0
            for img in imgs[:2]:
                prepared = _prepare_image(img, tmp_dir)
                if not prepared:
                    continue
                try:
                    run = left.add_paragraph().add_run()
                    run.add_picture(prepared, width=Cm(7.8))
                    cap = left.add_paragraph()
                    cr = cap.add_run(os.path.basename(img))
                    cr.font.size = Pt(8)
                    cr.font.color.rgb = GREY
                    _apply_font(cr)
                    placed += 1
                except Exception as e:
                    print(f"[WARN] ฝังรูป {img} ไม่ได้: {e}")
            if placed == 0:
                left.add_paragraph().add_run("(ฝังรูปไม่สำเร็จ)").font.size = Pt(9)
        else:
            ph = left.paragraphs[0].add_run("(โหมดเร็ว: ไม่ได้ดาวน์โหลดรูป)\nคำค้นภาพ:")
            ph.font.size = Pt(9)
            _apply_font(ph)
            left.add_paragraph().add_run(s.get("image_query") or "-").font.size = Pt(9)

        # ขวา: รายละเอียด
        right.paragraphs[0].text = ""

        def _line(label, value):
            p = right.add_paragraph()
            r1 = p.add_run(label)
            r1.bold = True
            r1.font.size = Pt(10)
            _apply_font(r1)
            r2 = p.add_run(value or "-")
            r2.font.size = Pt(10)
            _apply_font(r2)

        _line("สิ่งที่เห็นบนจอ: ", s.get("visual") or "-")
        _line("ข้อความบนจอ: ", s.get("on_screen_text") or "-")
        _line("คำค้นภาพ: ", s.get("image_query") or "-")
        _line("ไฟล์ภาพ: ", ", ".join(os.path.basename(i) for i in imgs) or "-")

        # --- เสียงพากย์ ---
        _para(doc, "🎙 เสียงพากย์", size=13, bold=True, color=BLUE)
        p = doc.add_paragraph()
        p.paragraph_format.line_spacing = 1.5
        pr = p.add_run(s.get("script_text", ""))
        pr.font.size = Pt(12)
        _apply_font(pr)

        if s.get("type") == "item":
            _para(
                doc,
                f"จบฉากนี้ → ขึ้นอันดับถัดไป (ทิ้งท้ายด้วย cliffhanger)",
                size=9, color=GREY,
            )

    doc.save(path)
    shutil.rmtree(tmp_dir, ignore_errors=True)
    return path


# -------------------------------------------------------- video_prompts.docx
def _shade_paragraph(p, fill="F1F5F9"):
    """ใส่สีพื้นหลังให้ย่อหน้า (ทำให้พรอมป์ตดูเป็นกล่อง ก๊อปง่าย)"""
    from docx.oxml import OxmlElement

    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    p._p.get_or_add_pPr().append(shd)


def _boxed(doc, text, size=11, fill="F1F5F9", mono=False):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(8)
    p.paragraph_format.left_indent = Cm(0.2)
    p.paragraph_format.line_spacing = 1.25
    run = p.add_run(text)
    run.font.size = Pt(size)
    _apply_font(run, "Consolas" if mono else THAI_FONT)
    _shade_paragraph(p, fill)
    return p


def build_video_prompts_docx(storyboard, shots, images_dir, path, max_seconds=10):
    """พรอมป์ต gen วิดีโอทีละช็อต (1 ช็อต = 1 หน้า) พร้อมรูปอ้างอิง"""
    import shutil
    import tempfile

    tmp_dir = tempfile.mkdtemp(prefix="vp_img_")
    doc = Document()
    _setup(doc)

    _para(
        doc,
        f"10 อันดับ {storyboard['topic']}",
        size=22, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER,
    )
    _para(
        doc,
        f"พรอมป์ตสร้างวิดีโอ · {len(shots)} ช็อต · ช็อตละไม่เกิน {max_seconds} วินาที",
        size=11, color=GREY, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=12,
    )

    _para(doc, "วิธีใช้", size=14, bold=True)
    for i, step in enumerate([
        "เปิดเครื่องมือ gen วิดีโอ (Kling / Hailuo / Dreamina / Veo) เลือกโหมด Image to Video",
        "อัปโหลดรูปอ้างอิงของช็อตนั้น (อยู่ในโฟลเดอร์ shots/)",
        "ก๊อป «VIDEO PROMPT» ของช็อตนั้นไปวางในช่อง prompt",
        "ตั้งความยาว 5–10 วินาที และอัตราส่วน 9:16 (หรือ 16:9 ตามช่องทาง)",
        "ดาวน์โหลดไฟล์ เปลี่ยนชื่อเป็น shot_XX.mp4 แล้วทำช็อตถัดไป",
        "ตัดต่อเรียงช็อตตามเวลา แล้วพากย์เสียงเองทีหลัง (บทอยู่ในไฟล์ script.docx)",
    ], start=1):
        _para(doc, f"{i}. {step}", size=10, space_after=2)

    _para(
        doc,
        "ช็อตถูกแบ่งจาก «เวลาของภาพ» เท่านั้น (ไม่ผูกกับบทพากย์) "
        "พรอมป์ตเป็นภาษาอังกฤษเพราะ video model เข้าใจตรงกว่า "
        "ส่วนบทพากย์ของแต่ละฉากแสดงไว้ให้พี่ใช้ตอนพากย์เอง",
        size=9, color=GREY, space_after=10,
    )

    # ---- shot list ----
    _para(doc, "ตารางช็อตทั้งหมด", size=14, bold=True)
    table = doc.add_table(rows=1, cols=5)
    table.style = "Light Grid Accent 1"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, text in enumerate(["ช็อต", "ฉาก", "เวลา", "ระยะ", "พรอมป์ต (ย่อ)"]):
        cell = table.rows[0].cells[i]
        cell.text = ""
        run = cell.paragraphs[0].add_run(text)
        run.bold = True
        run.font.size = Pt(9)
        _apply_font(run)

    for s in shots:
        cells = table.add_row().cells
        prompt_short = (s.get("video_prompt") or "")[:70]
        values = [
            f"{s['shot_id']:02d}",
            f"{s['scene_id']}. {s['scene_label']}",
            f"{s['start_timecode']}–{s['end_timecode']}",
            f"{s['duration_seconds']}s",
            prompt_short + ("…" if len(s.get("video_prompt") or "") > 70 else ""),
        ]
        for i, text in enumerate(values):
            cells[i].text = ""
            run = cells[i].paragraphs[0].add_run(text)
            run.font.size = Pt(8)
            _apply_font(run)

    # ---- รายละเอียดทีละช็อต ----
    for s in shots:
        doc.add_page_break()

        head = doc.add_paragraph()
        hr = head.add_run(
            f"SHOT {s['shot_id']:02d} · ฉาก {s['scene_id']} · "
            f"{s.get('heading') or s['scene_label']}"
        )
        hr.bold = True
        hr.font.size = Pt(15)
        _apply_font(hr)

        meta = doc.add_paragraph()
        mr = meta.add_run(
            f"⏱ {s['start_timecode']} – {s['end_timecode']} "
            f"({s['duration_seconds']} วินาที)"
            + (f"   ·   ช็อตที่ {s['part']}/{s['parts']} ของฉาก" if s.get("parts", 1) > 1 else "")
        )
        mr.font.size = Pt(10)
        mr.font.color.rgb = GREY
        _apply_font(mr)

        imgs = []
        if s.get("ref_image"):
            # รูปที่คัดลอกไว้ในโฟลเดอร์ shots/ อยู่ข้างไฟล์ docx
            cand = os.path.join(os.path.dirname(path), "shots", s["ref_image"])
            if os.path.isfile(cand):
                imgs = [cand]

        tbl = doc.add_table(rows=1, cols=2)
        tbl.style = "Table Grid"
        left, right = tbl.rows[0].cells
        left.width = Cm(8.0)
        right.width = Cm(9.0)

        left.paragraphs[0].text = ""
        if imgs:
            prepared = _prepare_image(imgs[0], tmp_dir)
            if prepared:
                try:
                    left.paragraphs[0].add_run().add_picture(prepared, width=Cm(7.4))
                except Exception as e:
                    print(f"[WARN] ฝังรูปช็อต {s['shot_id']} ไม่ได้: {e}")
                    left.paragraphs[0].add_run("(ฝังรูปไม่สำเร็จ)").font.size = Pt(9)
                cap = left.add_paragraph()
                cap_text = f"ไฟล์อ้างอิง: {s['ref_image']}"
                if s.get("ref_note"):
                    cap_text += f"  ({s['ref_note']})"
                cr = cap.add_run(cap_text)
                cr.font.size = Pt(8)
                cr.font.color.rgb = GREY
                _apply_font(cr)
        else:
            ph = left.paragraphs[0].add_run("(ไม่มีรูปอ้างอิง — ใช้คำค้นนี้หาเอง)\nคำค้นภาพ:")
            ph.font.size = Pt(9)
            _apply_font(ph)
            left.add_paragraph().add_run(s.get("image_query") or "-").font.size = Pt(9)

        right.paragraphs[0].text = ""

        def _line(label, value, size=9):
            p = right.add_paragraph()
            r1 = p.add_run(label)
            r1.bold = True
            r1.font.size = Pt(size)
            _apply_font(r1)
            r2 = p.add_run(value or "-")
            r2.font.size = Pt(size)
            _apply_font(r2)

        _line("ภาพที่ต้องเห็น: ", s.get("visual") or "-")
        if s.get("on_screen_text"):
            _line("ข้อความบนจอ: ", s["on_screen_text"])
        _line("มุมกล้องที่แนะนำ: ", s.get("camera") or "-")
        if s.get("warn"):
            wp = right.add_paragraph()
            wr = wp.add_run("⚠ " + s["warn"])
            wr.font.size = Pt(9)
            wr.font.color.rgb = RGBColor(0xB4, 0x53, 0x09)
            _apply_font(wr)

        # บทพากย์ของ "ฉาก" (ผู้ใช้พากย์เอง ไม่ผูกกับช็อต)
        vh = right.add_paragraph()
        vhr = vh.add_run(
            f"🎙 บทพากย์ของฉากนี้ (~{s.get('vo_seconds_est', 0)} วินาที)"
        )
        vhr.bold = True
        vhr.font.size = Pt(9)
        vhr.font.color.rgb = BLUE
        _apply_font(vhr)

        vo = right.add_paragraph()
        vo.paragraph_format.line_spacing = 1.3
        vr = vo.add_run(s.get("vo_text") or "-")
        vr.font.size = Pt(9)
        _apply_font(vr)

        # ---- prompt กล่องใหญ่ ก๊อปง่าย ----
        _para(doc, "🎬 VIDEO PROMPT (ก๊อปไปวาง)", size=12, bold=True, color=BLUE)
        _boxed(doc, (s.get("video_prompt") or "").strip(), size=11, fill="E0E7FF")

        _para(doc, "⛔ Negative prompt", size=11, bold=True, color=RGBColor(0xB9, 0x1C, 0x1C))
        _boxed(doc, (s.get("negative_prompt") or "").strip(), size=9, fill="FEF2F2")

        tail = doc.add_paragraph()
        tr = tail.add_run(
            f"ไฟล์: shots/shot_{s['shot_id']:02d}_ref.jpg · "
            f"shots/shot_{s['shot_id']:02d}_prompt.txt · "
            f"shots/scene_{int(s['scene_id']):02d}_vo.txt"
        )
        tr.font.size = Pt(8)
        tr.font.color.rgb = GREY
        _apply_font(tr)

    doc.save(path)
    shutil.rmtree(tmp_dir, ignore_errors=True)
    return path
