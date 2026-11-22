import os
import json
import tempfile
import shutil

from app.llm import generate_storyboard
from app.image_search import search_image_urls, download_image
from app.database import SessionLocal, Job


def _update_job(db, job_id, **kwargs):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        return None
    for k, v in kwargs.items():
        setattr(job, k, v)
    db.commit()
    db.refresh(job)
    return job


def _write_script_md(storyboard, path):
    lines = [
        f"# 10 อันดับ {storyboard['topic']}",
        "",
        f"ความยาวรวม: {storyboard['total_minutes']} นาที "
        f"({storyboard.get('total_seconds', storyboard['total_minutes'] * 60)} วินาที)",
        "",
        "| ฉาก | ประเภท | เวลา | ระยะ | หัวข้อ | คำค้นภาพ |",
        "|---|---|---|---|---|---|",
    ]
    type_label = {"hook": "HOOK", "intro": "เกริ่นนำ", "item": "อันดับ", "outro": "ปิดท้าย"}
    for s in storyboard["scenes"]:
        kind = (s.get("type") or "item").lower()
        label = type_label.get(kind, kind)
        if kind == "item":
            label = f"อันดับ {s.get('rank', '?')}"
        lines.append(
            f"| {s['scene_id']} | {label} | {s['start_timecode']} - {s['end_timecode']} "
            f"| {s['duration_seconds']}s | {s.get('title', '')} "
            f"| {s.get('image_query') or '-'} |"
        )

    lines += ["", "---", "", "## บทพูด (Voice Over)", ""]
    for s in storyboard["scenes"]:
        kind = (s.get("type") or "item").lower()
        label = type_label.get(kind, kind)
        if kind == "item":
            label = f"อันดับ {s.get('rank', '?')}"
        lines.append(
            f"### ฉาก {s['scene_id']} — [{label}] {s.get('title', '')} "
            f"({s['start_timecode']} – {s['end_timecode']})"
        )
        lines.append("")
        if s.get("visual"):
            lines.append(f"**ภาพ:** {s['visual']}")
            lines.append("")
        if s.get("on_screen_text"):
            lines.append(f"**ข้อความบนจอ:** {s['on_screen_text']}")
            lines.append("")
        lines.append(s.get("script_text", ""))
        lines.append("")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def _build_shots(storyboard, workdir, images_dir, use_llm=True):
    """สร้างชุดช็อต 10 วินาที + พรอมป์ตวิดีโอ (คืน dict ของ path ที่ได้)"""
    from app import shot_splitter as sb

    max_seconds = int(os.getenv("SHOT_MAX_SECONDS", "10") or 10)
    shots = sb.split_storyboard(storyboard, max_seconds=max_seconds,
                               topic=storyboard.get("topic"))
    if use_llm:
        shots = sb.polish_prompts_with_llm(shots, storyboard.get("topic") or "")

    shots_dir = os.path.join(workdir, "shots")
    sb.attach_reference_images(shots, images_dir, shots_dir)

    meta = {
        "topic": storyboard.get("topic"),
        "total_minutes": storyboard.get("total_minutes"),
        "total_seconds": storyboard.get("total_seconds"),
        "max_seconds_per_shot": max_seconds,
        "shot_count": len(shots),
        "negative_prompt": sb.NEGATIVE_PROMPT,
    }

    paths = {
        "shots_json": sb.write_shots_json(
            shots, meta, os.path.join(workdir, "shots.json")),
        "shots_csv": sb.write_shots_csv(
            shots, os.path.join(workdir, "shots.csv")),
        "shots_readme": sb.write_shots_readme(
            shots, storyboard.get("topic") or "", max_seconds,
            os.path.join(workdir, "shots_README.md")),
    }

    try:
        from app.docx_writer import build_video_prompts_docx

        paths["video_prompts_docx"] = build_video_prompts_docx(
            storyboard, shots, images_dir,
            os.path.join(workdir, "video_prompts.docx"),
            max_seconds=max_seconds,
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[WARN] video_prompts docx build failed: {e}")
        paths["video_prompts_docx"] = None

    paths["shots"] = shots
    paths["shots_dir"] = shots_dir
    return paths


def _drive_configured():
    return all(
        os.getenv(k)
        for k in (
            "GOOGLE_DRIVE_CLIENT_ID",
            "GOOGLE_DRIVE_CLIENT_SECRET",
            "GOOGLE_DRIVE_REFRESH_TOKEN",
        )
    )


def _mime_for(path):
    ext = os.path.splitext(path)[1].lower()
    return {
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".json": "application/json",
        ".csv": "text/csv",
        ".md": "text/markdown",
        ".txt": "text/plain",
        ".png": "image/png",
        ".webp": "image/webp",
    }.get(ext, "image/jpeg" if ext in (".jpg", ".jpeg") else "application/octet-stream")


def _unique_local_dir(topic, minutes):
    """หาโฟลเดอร์เก็บผลลัพธ์ในเครื่อง (ไม่เขียนทับของเดิม)"""
    out_root = os.getenv("LOCAL_OUTPUT_DIR", r"E:\top10bot\output")
    os.makedirs(out_root, exist_ok=True)
    base = f"10 อันดับ {topic} - {minutes} นาที"
    out_dir = os.path.join(out_root, base)
    n = 2
    while os.path.exists(out_dir):
        out_dir = os.path.join(out_root, f"{base} ({n})")
        n += 1
    return out_dir


def upload_folder_to_drive(local_folder, topic, minutes):
    """อัปโหลดโฟลเดอร์งานที่อยู่ในเครื่องขึ้น Google Drive → คืน (folder_id, link, จำนวนไฟล์)"""
    from app.drive_uploader import create_folder, get_drive_service, upload_file

    service = get_drive_service()
    folder_id = create_folder(service, f"10 อันดับ {topic} - {minutes} นาที")
    count = 0

    def put(path, parent):
        nonlocal count
        upload_file(service, path, parent, _mime_for(path))
        count += 1

    for fname in sorted(os.listdir(local_folder)):
        p = os.path.join(local_folder, fname)
        if os.path.isfile(p):
            try:
                put(p, folder_id)
            except Exception as e:
                print(f"[WARN] upload failed {fname}: {e}")
        elif os.path.isdir(p) and fname in ("images", "shots"):
            # รูป = ของจริงที่ฝังใน Word / shots = พรอมป์ต + บทพากย์ (ไม่เอาฮาร์ดลิงก์รูปซ้ำ)
            sub_id = create_folder(service, fname, folder_id)
            for inner in sorted(os.listdir(p)):
                if fname == "shots" and not inner.endswith(".txt"):
                    continue
                fp = os.path.join(p, inner)
                if os.path.isfile(fp):
                    try:
                        put(fp, sub_id)
                    except Exception as e:
                        print(f"[WARN] upload failed {fname}/{inner}: {e}")

    return folder_id, f"https://drive.google.com/drive/folders/{folder_id}", count


def process_top10_job(job_id: str, topic: str, minutes: int):
    """ทำงานทั้งหมดของงานหนึ่งชิ้น (เรียกจาก worker thread)"""
    db = SessionLocal()
    workdir = None
    try:
        _update_job(db, job_id, status="processing", error_message=None)

        # 1. สร้างสคริป + สตอรี่บอร์ด
        storyboard = generate_storyboard(topic, minutes)

        workdir = tempfile.mkdtemp(prefix=f"top10_{job_id[:8]}_")
        json_path = os.path.join(workdir, "storyboard.json")
        md_path = os.path.join(workdir, "script.md")
        docx_path = os.path.join(workdir, "script.docx")
        sb_docx_path = os.path.join(workdir, "storyboard.docx")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(storyboard, f, ensure_ascii=False, indent=2)
        _write_script_md(storyboard, md_path)
        try:
            from app.docx_writer import build_docx

            build_docx(storyboard, docx_path)
        except Exception as e:
            print(f"[WARN] docx build failed: {e}")
            docx_path = None

        # 2. ค้นหา + ดาวน์โหลดรูป
        images_dir = os.path.join(workdir, "images")
        os.makedirs(images_dir, exist_ok=True)
        for scene in storyboard["scenes"]:
            query = scene.get("image_query")
            if not query:
                continue
            for i, url in enumerate(search_image_urls(query, num=2)):
                ext = os.path.splitext(url.split("?")[0])[1].lower()
                if ext not in (".jpg", ".jpeg", ".png", ".webp"):
                    ext = ".jpg"
                fname = f"scene_{scene['scene_id']:02d}_img{i}{ext}"
                try:
                    download_image(url, os.path.join(images_dir, fname))
                except Exception as e:
                    print(f"[WARN] download failed {url}: {e}")

        # 2.5 สร้างสตอรี่บอร์ด Word (ฝังรูปที่โหลดมาแล้ว)
        try:
            from app.docx_writer import build_storyboard_docx

            build_storyboard_docx(storyboard, images_dir, sb_docx_path)
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"[WARN] storyboard docx build failed: {e}")
            sb_docx_path = None

        # 2.7 แบ่งช็อต 10 วินาที + พรอมป์ตวิดีโอ
        shot_paths = {}
        try:
            shot_paths = _build_shots(
                storyboard, workdir, images_dir,
                use_llm=os.getenv("SHOT_LLM_PROMPTS", "1") != "0",
            )
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"[WARN] shot split failed: {e}")
            shot_paths = {}

        # เก็บไฟล์ไว้ในเครื่องก่อนเสมอ (ห้ามเขียนทับงานเดิม — ใช้ชื่อใหม่ถ้าซ้ำ)
        out_dir = _unique_local_dir(topic, minutes)
        shutil.move(workdir, out_dir)
        workdir = None

        # 3. อัปโหลด Google Drive ถ้าตั้งค่าไว้
        if _drive_configured():
            try:
                folder_id, link, uploaded = upload_folder_to_drive(out_dir, topic, minutes)
                print(f"[drive] uploaded {uploaded} files → {link}")
                _update_job(
                    db, job_id, status="completed",
                    drive_folder_id=folder_id, drive_folder_link=link,
                    local_folder_path=out_dir, error_message=None,
                )
            except Exception as e:
                import traceback
                traceback.print_exc()
                print(f"[WARN] Drive upload failed: {e}")
                _update_job(
                    db, job_id, status="completed",
                    drive_folder_link=f"local:{out_dir}", local_folder_path=out_dir,
                    error_message="อัปโหลด Drive ไม่สำเร็จ — ไฟล์อยู่ในเครื่องที่ " + out_dir,
                )
            return

        _update_job(
            db, job_id, status="completed",
            drive_folder_link=f"local:{out_dir}", local_folder_path=out_dir,
            error_message="ยังไม่ได้ตั้งค่า Google Drive — ไฟล์ถูกเก็บไว้ที่ " + out_dir,
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        _update_job(db, job_id, status="failed", error_message=str(e)[:2000])
    finally:
        if workdir:
            shutil.rmtree(workdir, ignore_errors=True)
        db.close()
