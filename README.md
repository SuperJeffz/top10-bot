# 🎬 Top10 Bot — สร้างสคริป 10 อันดับ + สตอรี่บอร์ด + พรอมป์ตวิดีโอ + Google Drive

ระบบเว็บแอพที่พี่ใส่ **หัวข้อ + จำนวนนาที** → บอทจะ

1. เขียน **สคริปวิดีโอ 10 อันดับ** ภาษาไทย (Gemini หรือ Ollama เลือกได้)
2. สร้าง **สตอรี่บอร์ด** ที่มี **เวลารวมตรงกับจำนวนนาทีที่ใส่เป๊ะ** (มี timecode ทุกฉาก)
3. **แบ่งเป็นช็อต ≤10 วินาที** พร้อมพรอมป์ต gen วิดีโอ (คำค้นภาพยังระบุไว้ให้หาเอง)
4. ออกเป็น **ไฟล์ Word (.docx)** อ่านง่าย + `script.md` + `storyboard.json`
5. **อัปโหลดทั้งหมดเข้า Google Drive** ของพี่ (หรือเก็บในเครื่องถ้ายังไม่ตั้งค่า)

> โหมดเร็ว: ไม่ค้นหา/ดาวน์โหลดรูปจากอินเทอร์เน็ตตามค่าเริ่มต้น (ขั้นตอนนี้ช้าสุด)
> ถ้าอยากได้รูปฝังใน Word อีกครั้ง ตั้ง `ENABLE_IMAGE_SEARCH=1`

ทั้งหมด **ฟรี 100%** — รันบนเครื่องพี่เอง ไม่มีลิมิต 5 นาทีแบบ Make

---

## 🧩 สถาปัตยกรรมที่ติดตั้งจริงบนเครื่องนี้

| ส่วน | ที่อยู่ | หมายเหตุ |
|---|---|---|
| Ollama (runtime) | `C:\Users\jiepj\AppData\Local\Programs\Ollama` | ~1 GB |
| **โมเดล AI** | **`E:\ollama\models`** | llama3.1:8b + typhoon2.5 |
| Python venv + packages | `E:\top10bot\venv` | ไม่กิน C: |
| pip cache | `E:\pip-cache` | |
| ฐานข้อมูล (SQLite) | `E:\top10bot\data\jobs.db` | |
| ไฟล์ผลลัพธ์ (fallback) | `E:\top10bot\output` | |
| โค้ดโปรเจกต์ | `D:\shell\top10_free_bot` | |

> ไม่ใช้ Docker / Redis / Celery — ใช้ worker thread ในตัว FastAPI แทน
> (เพราะเครื่องนี้ยังไม่ได้เปิด Virtual Machine Platform ทำให้ WSL2/Docker ใช้ไม่ได้)

---

## ▶️ วิธีเปิดใช้งาน

### ดับเบิลคลิก
```
D:\shell\top10_free_bot\start.bat
```
จะเปิด 3 หน้าต่าง (Ollama / Backend / Frontend) และเปิดเบราว์เซอร์ที่
**http://localhost:5173** ให้อัตโนมัติ

### ปิดระบบ
```
D:\shell\top10_free_bot\stop.bat
```

### เปิดเองแบบ manual
```powershell
# 1) Ollama
$env:OLLAMA_MODELS='E:\ollama\models'
& "C:\Users\jiepj\AppData\Local\Programs\Ollama\ollama.exe" serve

# 2) Backend
cd D:\shell\top10_free_bot\backend
E:\top10bot\venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# 3) Frontend
cd D:\shell\top10_free_bot\frontend
npm run dev -- --port 5173
```

---

## 🔗 เชื่อม Google Drive (ทำครั้งเดียว)

อ่าน **[GDRIVE_SETUP.md](./GDRIVE_SETUP.md)** — ใช้เวลาประมาณ 5 นาที
แล้วรันสคริปต์ดึง token ให้อัตโนมัติ:

```powershell
E:\top10bot\venv\Scripts\python.exe D:\shell\top10_free_bot\backend\get_drive_token.py
```

ถ้ายังไม่ตั้งค่า ระบบจะเก็บไฟล์ไว้ที่ `E:\top10bot\output` แทน (ใช้งานได้ปกติ)

---

## 🧠 เปลี่ยนโมเดล AI

### วิธีง่ายสุด — ทำจากหน้าเว็บ

เปิด http://localhost:5173 → กด **⚙️ ตั้งค่า AI** → วาง Gemini API key → บันทึก
(ระบบจะเขียนลง `backend\.env` ให้เองทันที ไม่ต้องรีสตาร์ท)

ขอคีย์ Gemini ฟรีได้ที่ https://aistudio.google.com/apikey

### วิธีแก้ไฟล์ตรง ๆ

แก้ที่ `backend\.env`

```env
LLM_PROVIDER=gemini          # gemini = คุณภาพดีสุด | ollama = รันในเครื่อง
GEMINI_API_KEY=วางคีย์ตรงนี้
GEMINI_MODEL=gemini-3.6-flash  # แนะนำ (ถ้าใช้ไม่ได้ ระบบสลับตัวสำรองให้เอง)

# โมเดลอื่นที่ใช้ได้กับคีย์ฟรี: gemini-3-flash-preview, gemini-3.5-flash,
#   gemini-3.1-flash-lite, gemini-3.1-pro-preview (โควตาจำกัด)
# หมายเหตุ: gemini-2.5-flash / 2.5-pro เลิกให้ผู้ใช้ใหม่แล้ว

# ถ้าใช้ Ollama
OLLAMA_MODEL=scb10x/typhoon2.5-qwen3-30b-a3b   # โมเดลไทย 30B MoE (ติดตั้งแล้ว 18 GB)
# OLLAMA_MODEL=llama3.1:8b                     # ตัวเก่า เร็ว
# OLLAMA_MODEL=scb10x/typhoon2.1-gemma3-12b    # กลาง ๆ
```

โหลดโมเดลใหม่:
```powershell
$env:OLLAMA_MODELS='E:\ollama\models'
& "C:\Users\jiepj\AppData\Local\Programs\Ollama\ollama.exe" pull scb10x/typhoon2.1-gemma3-12b
```

---

## 📄 ผลลัพธ์ที่ได้ (ต่อ 1 งาน)

```
10 อันดับ <หัวข้อ> - <n> นาที/
├── script.docx          # ⭐ บทพูด + ตารางเวลา (เปิดอ่าน/พิมพ์ง่าย)
├── storyboard.docx      # ⭐ สตอรี่บอร์ดตัดต่อ: 1 ฉาก = 1 หน้า (รูปฝังในไฟล์)
├── video_prompts.docx   # ⭐ พรอมป์ต gen วิดีโอทีละช็อต (1 ช็อต = 1 หน้า)
├── shots.csv            #  ตารางช็อตทั้งหมด (เปิดใน Excel)
├── shots.json           #  ข้อมูลช็อตแบบละเอียด
├── shots_README.md      #  วิธีใช้ + เครื่องมือ gen วิดีโอฟรี
├── script.md
├── storyboard.json
├── images/
│   ├── scene_03_img0.jpg   # 2 รูปต่อฉาก
│   └── ...
└── shots/
    ├── shot_01_ref.jpg      # รูปอ้างอิงของช็อต 1 (อัปเป็น start frame)
    ├── shot_01_prompt.txt   # พรอมป์ตช็อต 1 (ก๊อปวาง)
    ├── shot_02_ref.jpg
    └── scene_01_vo.txt      # บทพากย์ของฉาก 1 (ไว้พากย์เอง)
```

### โครงสร้างบท (13 ฉาก)

| ฉาก | ประเภท | เนื้อหา |
|---|---|---|
| 1 | **HOOK** | ประโยคสะกดคนดู 3–8 วินาทีแรก (ไม่มีคำทักทาย) |
| 2 | เกริ่นนำ | ต่อจาก hook สั้น ๆ บอกสิ่งที่จะดู + เกณฑ์ + เหตุผลที่ต้องดูจนจบ |
| 3–12 | อันดับ 10 → 1 | บทพูด + ภาพประกอบ + ข้อความบนจอ |
| 13 | ปิดท้าย | สรุป + คำถามชวนคอมเมนต์ + CTA |

### `storyboard.docx` มีอะไรบ้าง

- **Shot list** สรุปทุกฉากในตารางเดียว
- **1 ฉาก = 1 หน้า** ประกอบด้วย
  - รูปอ้างอิงจากอินเทอร์เน็ต (ฝังในไฟล์ ไม่ต้องเปิดโฟลเดอร์แยก)
  - **สิ่งที่เห็นบนจอ** (visual direction)
  - **ข้อความบนจอ** (on-screen text)
  - **คำค้นภาพ** + ชื่อไฟล์รูป
  - **🎙 เสียงพากย์** ตัวบทเต็มของฉากนั้น

### `video_prompts.docx` — ต่อขั้น gen วิดีโอ (ทีละ 10 วินาที)

- แบ่ง **จากเวลาของภาพล้วน ๆ** ไม่ผูกกับบทพากย์ (พากย์เองทีหลังได้)
  - ฉาก 14 วิ + เพดาน 10 วิ → 2 ช็อต ช็อตละ 7 วิ
  - เวลารวมของทุกช็อต = ความยาวคลิปเป๊ะ
- **1 ช็อต = 1 หน้า** มี
  - รูปอ้างอิง (ใช้เป็น start frame ในโหมด Image-to-Video)
  - **🎬 VIDEO PROMPT** ภาษาอังกฤษ (ก๊อปไปวางได้เลย)
  - **⛔ Negative prompt**
  - ภาพที่ต้องเห็น · ข้อความบนจอ · มุมกล้องที่แนะนำ
  - **🎙 บทพากย์ของฉากนั้น** (สำหรับพากย์เอง ไม่ถูกตัดตามช็อต)
- ปรับความยาวช็อตได้ด้วย `SHOT_MAX_SECONDS` ใน `.env`
  หรือเรียก `POST /jobs/{id}/shots?max_seconds=8` เพื่อสร้างใหม่จากสตอรี่บอร์ดเดิม

เปิดไฟล์ได้ 3 ทาง:
- บนหน้าเว็บ กด **📄 เปิดไฟล์บทพูด (Word)** / **🎬 เปิดสตอรี่บอร์ด (Word)** / **🎞 พรอมป์ตวิดีโอ 10 วิ (Word)**
- ไปที่ `E:\top10bot\output\<ชื่องาน>\`
- เปิด `shots_README.md` เพื่อดูขั้นตอน gen วิดีโอด้วยเครื่องมือฟรี

`storyboard.json` แต่ละฉากมี:
`scene_id`, `type`, `rank`, `title`, `script_text`, `visual`,
`on_screen_text`, `duration_seconds`, `start_seconds`, `end_seconds`,
`start_timecode`, `end_timecode`, `image_query`

---

## 🔌 API (ถ้าอยากต่อกับ Make / n8n / Telegram)

| Method | Path | คำอธิบาย |
|---|---|---|
| POST | `/jobs` | `{"topic": "...", "minutes": 8}` → คืน `job_id` |
| GET | `/jobs/{job_id}` | ดูสถานะ + ลิงก์ Drive |
| POST | `/jobs/{job_id}/open` | เปิดโฟลเดอร์ผลลัพธ์ใน Explorer |
| POST | `/jobs/{job_id}/open?file=script.docx` | เปิดไฟล์ Word ของงานนั้น |
| POST | `/jobs/{job_id}/shots?max_seconds=10` | แบ่งช็อต + สร้างพรอมป์ตวิดีโอใหม่จากงานเดิม |
| GET | `/jobs` | 50 งานล่าสุด |
| GET | `/config` | ดู provider / โมเดล / สถานะคีย์ |
| POST | `/config` | ตั้ง provider / Gemini key / โมเดล |
| GET | `/health` | เช็กสถานะ |
| — | `/docs` | เอกสาร API อัตโนมัติ |

> 🎯 **ทางแก้ปัญหา Make 5 นาที:** ให้ Make เรียก `POST /jobs` แล้วจบทันที
> (ใช้เวลา <1 วินาที) ส่วนงานหนักไปรันในเครื่องพี่เอง → ไม่ติดลิมิตอีกเลย

---

## ⚠️ ข้อจำกัด

- **ไม่มี GPU** → ใช้ CPU (i7-8700K) ประมวลผลช้ากว่าปกติ 1 นาทีวิดีโอ ≈ 2–5 นาทีประมวลผล
- **DuckDuckGo** ใช้ดึงรูปฟรี ถ้าค้นถี่มากอาจถูกจำกัดชั่วคราว
- **รูปจากอินเทอร์เน็ต** อาจมีลิขสิทธิ์ ถ้าใช้เชิงพาณิชย์ควรเปลี่ยนไปใช้ Unsplash/Pexels
- ถ้าเครื่องรีสตาร์ท งานที่ค้างอยู่จะกลับเข้าคิวให้อัตโนมัติเมื่อเปิดระบบใหม่
