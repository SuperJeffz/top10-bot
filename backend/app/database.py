from sqlalchemy import create_engine, Column, String, Integer, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./jobs.db")
connect_args = {"check_same_thread": False} if "sqlite" in DATABASE_URL else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Job(Base):
    __tablename__ = "jobs"

    id = Column(String, primary_key=True, index=True)
    topic = Column(String, nullable=False)
    minutes = Column(Integer, nullable=False)
    status = Column(String, default="queued")  # queued, processing, completed, failed
    drive_folder_id = Column(String, nullable=True)
    drive_folder_link = Column(String, nullable=True)
    local_folder_path = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


def init_db():
    Base.metadata.create_all(bind=engine)
    # Migration สำหรับ DB ที่มีอยู่แล้ว (create_all ไม่เติมคอลัมน์ใหม่ให้)
    try:
        from sqlalchemy import inspect, text

        cols = {c["name"] for c in inspect(engine).get_columns("jobs")}
        if "local_folder_path" not in cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE jobs ADD COLUMN local_folder_path VARCHAR"))
    except Exception as e:
        print(f"[db] ไม่สามารถเพิ่มคอลัมน์ local_folder_path ได้: {e}")