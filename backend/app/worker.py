import os
import threading

import requests

from app.database import SessionLocal, Job
from app.tasks import process_top10_job

_lock = threading.Lock()
_stop = threading.Event()
_thread = None
_keepalive_thread = None


def _loop():
    while not _stop.is_set():
        job = None
        db = SessionLocal()
        try:
            job = (
                db.query(Job)
                .filter(Job.status == "queued")
                .order_by(Job.created_at)
                .first()
            )
            if job:
                _claim(db, job.id)
                job_id, topic, minutes = job.id, job.topic, job.minutes
        finally:
            db.close()

        if job:
            try:
                process_top10_job(job_id, topic, minutes)
            except Exception as e:  # กัน worker ตาย
                print(f"[ERROR] job {job_id} crashed: {e}")
        else:
            _stop.wait(3)


def _claim(db, job_id):
    """กันไม่ให้สอง worker หยิบงานเดียวกัน"""
    with _lock:
        job = db.query(Job).filter(Job.id == job_id).first()
        if job and job.status == "queued":
            job.status = "processing"
            db.commit()
            return True
        return False


def start():
    global _thread, _keepalive_thread
    if _thread and _thread.is_alive():
        return

    # งานที่ค้างจากรอบก่อน (เครื่องปิดกลางทาง) ให้กลับเข้าคิว
    db = SessionLocal()
    try:
        stuck = db.query(Job).filter(Job.status == "processing").all()
        for j in stuck:
            j.status = "queued"
        db.commit()
    finally:
        db.close()

    _stop.clear()
    _thread = threading.Thread(target=_loop, name="top10-worker", daemon=True)
    _thread.start()
    if not _keepalive_thread or not _keepalive_thread.is_alive():
        _keepalive_thread = threading.Thread(
            target=_keepalive_loop, name="top10-keepalive", daemon=True
        )
        _keepalive_thread.start()
    print("[worker] started")


def _keepalive_loop():
    """Render Free จะหลับหลังไม่มี request 15 นาที — ค่อย ping เฉพาะตอนมีงานค้าง"""
    external = os.getenv("RENDER_EXTERNAL_URL", "").strip().rstrip("/")
    port = os.getenv("PORT", "8000")
    target = f"{external}/health" if external else f"http://127.0.0.1:{port}/health"
    while not _stop.is_set():
        busy = False
        db = SessionLocal()
        try:
            busy = (
                db.query(Job)
                .filter(Job.status.in_(("queued", "processing")))
                .count()
                > 0
            )
        except Exception as e:
            print(f"[keepalive] db check failed: {e}")
        finally:
            db.close()
        if busy:
            try:
                requests.get(target, timeout=10)
            except Exception as e:
                print(f"[keepalive] ping failed: {e}")
        _stop.wait(240)  # 4 นาที < 15 นาทีของ Render


def stop():
    _stop.set()
    if _thread:
        _thread.join(timeout=5)
