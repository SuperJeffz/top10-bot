import os

from dotenv import load_dotenv

# โหลด .env จากโฟลเดอร์ backend (ไฟล์นี้อยู่ข้างบน app/)
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
