import os
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.database import SessionLocal, Job, init_db
from app import worker
from app.settings_io import update_env


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    worker.start()
    yield
    worker.stop()


app = FastAPI(title="Top10 Bot (native)", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def simple_password_guard(request: Request, call_next):
    """รหัสผ่านง่าย ๆ สำหรับ_space_ที่เปิดสาธารณะ (ไม่ใส่ก็ไม่บังคับ)"""
    password = os.getenv("APP_PASSWORD", "").strip()
    path = request.url.path
    if (
        password
        and request.method != "OPTIONS"
        and path not in ("/health", "/")
        and not path.startswith(("/assets/", "/favicon"))
        and "." not in os.path.basename(path)
    ):
        supplied = request.headers.get("x-app-password") or request.query_params.get("pw")
        if supplied != password:
            return JSONResponse(
                status_code=401,
                content={"detail": "ต้องใส่รหัสผ่านก่อนใช้งาน"},
                headers={"WWW-Authenticate": "Top10App"},
            )
    return await call_next(request)


class JobRequest(BaseModel):
    topic: str = Field(min_length=1)
    minutes: int = Field(gt=0, le=120)


class ConfigUpdate(BaseModel):
    provider: str | None = None
    gemini_api_key: str | None = None
    gemini_model: str | None = None
    ollama_model: str | None = None


@app.get("/config")
def get_config():
    key = (os.getenv("GEMINI_API_KEY") or "").strip()
    return {
        "provider": (os.getenv("LLM_PROVIDER") or "ollama").strip(),
        "gemini_model": (os.getenv("GEMINI_MODEL") or "gemini-2.5-flash").strip(),
        "gemini_key_set": bool(key),
        "gemini_key_hint": (key[:6] + "..." + key[-4:]) if len(key) > 12 else "",
        "ollama_model": (os.getenv("OLLAMA_MODEL") or "llama3.1:8b").strip(),
        "can_open_local": os.name == "nt",
    }


@app.post("/config")
def set_config(cfg: ConfigUpdate):
    updates = {}
    if cfg.provider:
        p = cfg.provider.strip().lower()
        if p not in ("gemini", "ollama"):
            raise HTTPException(400, "provider ต้องเป็น gemini หรือ ollama")
        updates["LLM_PROVIDER"] = p
    if cfg.gemini_api_key and cfg.gemini_api_key.strip():
        updates["GEMINI_API_KEY"] = cfg.gemini_api_key.strip()
    if cfg.gemini_model:
        updates["GEMINI_MODEL"] = cfg.gemini_model.strip()
    if cfg.ollama_model:
        updates["OLLAMA_MODEL"] = cfg.ollama_model.strip()

    if updates:
        update_env(updates)
    return get_config()


@app.post("/jobs")
def create_job(req: JobRequest):
    job_id = str(uuid.uuid4())
    db = SessionLocal()
    try:
        db.add(Job(id=job_id, topic=req.topic, minutes=req.minutes, status="queued"))
        db.commit()
    finally:
        db.close()
    return {"job_id": job_id, "status": "queued"}


@app.get("/jobs/{job_id}")
def get_job(job_id: str):
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
    finally:
        db.close()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "job_id": job.id,
        "topic": job.topic,
        "minutes": job.minutes,
        "status": job.status,
        "drive_folder_id": job.drive_folder_id,
        "drive_folder_link": job.drive_folder_link,
        "local_folder_path": getattr(job, "local_folder_path", None),
        "error": job.error_message,
        "created_at": str(job.created_at),
    }


def _local_folder(job):
    """ตำแหน่งไฟล์ในเครื่อง (งานเก่ายังใช้รูปแบบ local: อยู่)"""
    p = getattr(job, "local_folder_path", None)
    if p and os.path.isdir(p):
        return p
    link = job.drive_folder_link or ""
    if link.startswith("local:"):
        p = link[len("local:"):]
        if os.path.isdir(p):
            return p
    return None


@app.post("/jobs/{job_id}/open")
def open_job_folder(job_id: str, file: str | None = None):
    """เปิดโฟลเดอร์ผลลัพธ์ของงานนี้ (หรือเปิดไฟล์ที่ระบุ) ใน File Explorer"""
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
    finally:
        db.close()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    path = _local_folder(job)
    if not path:
        raise HTTPException(
            status_code=400,
            detail="ไม่พบไฟล์ในเครื่องของงานนี้ (อาจอยู่บน Drive เพียงอย่างเดียว)",
        )
    if os.name != "nt":
        raise HTTPException(
            status_code=400,
            detail="เปิดไฟล์ในเครื่องได้เฉพาะเมื่อรันบน Windows — บน Render ให้ใช้ลิงก์ Google Drive",
        )

    if file:
        # อนุญาตเฉพาะชื่อไฟล์ในโฟลเดอร์นี้ (กัน path traversal)
        target = os.path.join(path, os.path.basename(file))
        if not os.path.isfile(target):
            raise HTTPException(status_code=404, detail=f"ไม่พบไฟล์: {file}")
        os.startfile(target)
        return {"opened": target}

    os.startfile(path)  # เปิดใน Explorer (Windows)
    return {"opened": path}


@app.post("/jobs/{job_id}/shots")
def rebuild_shots(job_id: str, max_seconds: int = 10, use_llm: bool = True):
    """สร้างช็อต + พรอมป์ตวิดีโอใหม่จากสตอรี่บอร์ดเดิม (ไม่ต้องรอ AI เขียนบทใหม่)"""
    from app import tasks

    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
    finally:
        db.close()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    folder = _local_folder(job)
    if not folder:
        raise HTTPException(
            status_code=400,
            detail="ไม่พบไฟล์ในเครื่องของงานนี้ — สร้างช็อตใหม่ไม่ได้",
        )
    sb_path = os.path.join(folder, "storyboard.json")
    if not os.path.isfile(sb_path):
        raise HTTPException(status_code=404, detail=f"ไม่พบ storyboard.json ใน {folder}")

    import json

    with open(sb_path, encoding="utf-8") as f:
        storyboard = json.load(f)

    if max_seconds < 3 or max_seconds > 60:
        raise HTTPException(status_code=400, detail="max_seconds ต้องอยู่ระหว่าง 3–60")

    try:
        paths = tasks._build_shots(
            storyboard, folder, os.path.join(folder, "images"), use_llm=use_llm
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"สร้างช็อตไม่สำเร็จ: {e}")

    shots = paths.get("shots") or []
    return {
        "folder": folder,
        "shot_count": len(shots),
        "max_seconds": max_seconds,
        "total_seconds": sum(s["duration_seconds"] for s in shots),
        "files": {
            k: os.path.basename(v)
            for k, v in paths.items()
            if isinstance(v, str)
        },
    }


@app.post("/jobs/{job_id}/upload-drive")
def upload_job_to_drive(job_id: str):
    """อัปโหลดผลลัพธ์ของงานที่อยู่ในเครื่องขึ้น Google Drive (ทำซ้ำได้ ไม่ซ้ำโฟลเดอร์เดิม)"""
    from app import tasks

    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        if job.status != "completed":
            raise HTTPException(status_code=400, detail="งานยังทำไม่เสร็จ")

        link = job.drive_folder_link or ""
        if job.drive_folder_id and link.startswith("https://drive.google.com"):
            return {
                "folder_id": job.drive_folder_id,
                "link": link,
                "count": None,
                "already_uploaded": True,
            }

        folder = _local_folder(job)
        if not folder:
            raise HTTPException(status_code=400, detail="ไม่พบโฟลเดอร์ผลลัพธ์ในเครื่อง")

        try:
            folder_id, drive_link, count = tasks.upload_folder_to_drive(
                folder, job.topic, job.minutes
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"อัปโหลด Drive ไม่สำเร็จ: {e}")

        job.drive_folder_id = folder_id
        job.drive_folder_link = drive_link
        job.local_folder_path = folder
        job.error_message = None
        db.commit()
        return {"folder_id": folder_id, "link": drive_link, "count": count,
                "already_uploaded": False}
    finally:
        db.close()


@app.get("/jobs")
def list_jobs():
    db = SessionLocal()
    try:
        rows = db.query(Job).order_by(Job.created_at.desc()).limit(50).all()
        return [
            {
                "job_id": j.id,
                "topic": j.topic,
                "minutes": j.minutes,
                "status": j.status,
                "drive_folder_link": j.drive_folder_link,
                "local_folder_path": getattr(j, "local_folder_path", None),
                "created_at": str(j.created_at),
            }
            for j in rows
        ]
    finally:
        db.close()


@app.get("/health")
def health():
    return {"ok": True, "auth_required": bool(os.getenv("APP_PASSWORD", "").strip())}


# เสิร์ฟหน้าเว็บ (frontend build) จาก service เดียวกัน — สำหรับ Render / Docker
def _find_static_dir():
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    candidates = [
        os.getenv("STATIC_DIR"),
        os.path.join(here, "static"),
        os.path.join(here, os.pardir, "frontend", "dist"),
    ]
    for c in candidates:
        if c and os.path.isdir(c):
            return os.path.abspath(c)
    return None


_static = _find_static_dir()
if _static:
    app.mount("/", StaticFiles(directory=_static, html=True), name="frontend")
