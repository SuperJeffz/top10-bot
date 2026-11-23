# ขึ้นแอปฟรีบน Render (เปิดจากมือถือได้ทุกที่ ไม่ต้องเปิดคอม)

แอปทั้งตัว (API + worker + หน้าเว็บ) รันใน **Docker container เดียว** บน Render Free
ได้ลิงก์ `https://<ชื่อ-service>.onrender.com` เปิดจากมือถือได้เลย

## สิ่งที่เตรียมไว้แล้ว
- `Dockerfile` — build frontend ด้วย Node แล้วเสิร์ฟจาก Python (`/app/static`)
- `render.yaml` — Blueprint ตั้งค่า service แบบ free + region singapore
- `.dockerignore` / `.gitignore` — กัน `.env` และความลับไม่ให้ขึ้น repo
- worker มี **self-keepalive** ping `/health` ทุก 4 นาทีเฉพาะตอนมีงานค้าง
  (Render Free หลับหลังไม่มีคนเข้า 15 นาที)

## 1) สร้าง GitHub repo แล้ว push
```powershell
cd D:\shell\top10_free_bot
git init
git add .
git commit -m "top10 bot for render"
git branch -M main
git remote add origin https://github.com/<USER>/<REPO>.git
git push -u origin main
```
> ตรวจว่า **ไม่มีไฟล์ `.env`** ใน repo (`git ls-files | findstr /R "\.env$"` ต้องไม่ขึ้นอะไร)

## 2) สร้าง Render service
1. สมัคร/ล็อกอิน https://dashboard.render.com (ฟรี ไม่ต้องใส่บัตร)
2. **New → Blueprint** → เลือก repo ที่ push ไป → **Apply**
3. ตอน.apply Render จะถามค่าที่ `sync: false` ใน `render.yaml` — ใส่ตามตารางด้านล่าง
4. รอ build (~5–10 นาทีครั้งแรก) แล้วเปิดลิงก์ `https://top10-bot.onrender.com`

หรือสร้างแบบ **New → Web Service → Docker** ก็ได้ แล้วใส่ env เองในแท็บ Environment

## 3) Environment variables (_secret_ — ใส่ใน Render ห้ามใส่ในโค้ด)

| Key | _value_ | หมายเหตุ |
|---|---|---|
| `APP_PASSWORD` | รหัสที่พี่ตั้งเอง | เว็บจะถามรหัสตอนเปิดครั้งแรก เก็บใน browser |
| `GEMINI_API_KEY` | กุญแจ Gemini | จาก `backend\.env` |
| `LLM_PROVIDER` | `gemini` | |
| `GEMINI_MODEL` | `gemini-3.6-flash` | |
| `GOOGLE_DRIVE_CLIENT_ID` | จาก GCP | `top10-desktop` |
| `GOOGLE_DRIVE_CLIENT_SECRET` | จาก GCP | ห้ามแชร์ |
| `GOOGLE_DRIVE_REFRESH_TOKEN` | จาก `get_drive_token.py` | ห้ามแชร์ |
| `DATABASE_URL` | `sqlite:////tmp/jobs.db` | ตั้งใน render.yaml แล้ว |
| `LOCAL_OUTPUT_DIR` | `/tmp/output` | ตั้งใน render.yaml แล้ว |
| `SHOT_MAX_SECONDS` | `10` | |
| `SHOT_LLM_PROMPTS` | `1` | |
| `ENABLE_IMAGE_SEARCH` | `0` | ตั้ง `1` เพื่อเปิดค้นหารูปอินเทอร์เน็ต (ช้ากว่ามาก) |
| `GEMINI_STORYBOARD_BUDGET` | `150` | วิ — หมดเวลาแล้วใช้บทสำรองทันที |
| `GEMINI_JSON_BUDGET` | `45` | วิ — จำกัดเวลาปรับพรอมป์ตช็อต |

> `RENDER_EXTERNAL_URL` Render ตั้งให้เอง — หนูใช้มันใน keepalive

## 4) การใช้งาน
1. เปิดลิงก์ → ใส่รหัสผ่าน → พิมพ์หัวข้อ + เลือกนาที → ส่งงาน
2. งานทำเบื้องหลัง (worker thread) ไม่ติดขีด 5 นาที
3. ผลลัพธ์อัปโหลด Google Drive อัตโนมัติ → โชว์ลิงก์ในหน้าเว็บ
4. ปิดมือถือ/ปิดคอมก็ได้ งานยังทำต่อบน Render

## ข้อจำกัดของฟรี
-  inactive 15 นาที → service หลับ ครั้งต่อไปรอ ~1 นาทีตื่น (หน้าเว็บจะโหลดช้าครั้งแรก)
- `/tmp` เป็น disk ชั่วคราว → ประวัติงานหายหลัง service restart (ไฟล์ขึ้น Drive อยู่แล้ว ไม่หาย)
- 750 ชม./เดือน พอสำหรับ 1 service ตลอดเดือน (24×30=720)

## แก้ปัญหา
- `401` ตอนเปิด → ใส่รหัสผ่านถูกต้อง (หรือลบ `top10_pw` ใน localStorage แล้วโหลดใหม่)
- งานค้าง → ดู log ใน Render dashboard → Logs
- Drive 403 → เช็กว่า `snowroom011@gmail.com` ยังเป็น Test user ใน Google Auth Platform
- Drive `invalid_grant` → รัน `backend\get_drive_token.py` ใหม่ แล้วอัปเดต secret ใน Render
