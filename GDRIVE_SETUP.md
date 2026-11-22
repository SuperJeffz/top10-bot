# วิธีเชื่อม Google Drive (ทำครั้งเดียว ~5 นาที)

ตอนนี้ระบบทำงานได้แล้ว แต่จะเก็บไฟล์ไว้ในเครื่องที่ `E:\top10bot\output`
ถ้าอยากให้อัปโหลดเข้า **Google Drive ของพี่** ทำตามนี้ค่ะ

---

## 1) สร้างโปรเจกต์ + เปิด Drive API

1. เข้า https://console.cloud.google.com/
2. มุมซ้ายบน → **Select a project** → **New project** → ตั้งชื่อ `top10-bot` → Create
3. ไปที่ **APIs & Services → Library** → ค้นหา **Google Drive API** → กด **Enable**
4. ไปที่ **APIs & Services → OAuth consent screen**
   - User type: **External** → Create
   - App name: `top10-bot`, User support email: อีเมลพี่, Developer contact: อีเมลพี่ → Save and continue
   - Scopes: กด Save and continue ผ่านไปได้เลย
   - Test users: กด **Add users** ใส่อีเมล Google ของพี่เอง → Save
   - (สำคัญ) ต้องใส่ตัวเองเป็น Test user ไม่งั้นตอนล็อกอินจะโดนบล็อก

## 2) สร้าง OAuth Client ID

1. ไปที่ **APIs & Services → Credentials**
2. **Create credentials → OAuth client ID**
3. Application type: **Desktop app** ← เลือกอันนี้ (ง่ายที่สุด ไม่ต้องใส่ redirect URI)
4. Name: `top10-desktop` → Create
5. ก๊อป **Client ID** และ **Client secret**

## 3) ใส่ค่าและดึง Refresh Token อัตโนมัติ

เปิดไฟล์ `D:\shell\top10_free_bot\backend\.env` แล้วเติม 2 บรรทัดนี้:

```env
GOOGLE_DRIVE_CLIENT_ID=ก๊อป_client_id_มาวาง
GOOGLE_DRIVE_CLIENT_SECRET=ก๊อป_client_secret_มาวาง
```

จากนั้นเปิด PowerShell รัน:

```powershell
E:\top10bot\venv\Scripts\python.exe D:\shell\top10_free_bot\backend\get_drive_token.py
```

เบราว์เซอร์จะเปิด → ล็อกอิน Google → กด **Continue / Allow**
สคริปต์จะเขียน `GOOGLE_DRIVE_REFRESH_TOKEN` ลง `.env` ให้เองอัตโนมัติ ✅

## 4) รีสตาร์ทระบบ

ปิดหน้าต่าง backend เดิม แล้วรัน `start.bat` ใหม่
จากนี้ไปไฟล์ทุกงานจะถูกอัปโหลดเข้า Google Drive ของพี่ (โฟลเดอร์ชื่อ `10 อันดับ <หัวข้อ> - <นาที> นาที`)

---

## หมายเหตุ

- ระบบขอสิทธิ์แค่ `drive.file` = เห็นเฉพาะไฟล์ที่มันสร้างเอง ไม่เห็นไฟล์อื่นใน Drive ของพี่
- ถ้าเจอ error `invalid_grant` → refresh token หมดอายุ/ถูกเพิกถอน ให้รัน `get_drive_token.py` ใหม่
- ถ้าเจอ `403 access_denied` ตอนล็อกอิน → ยังไม่ได้ใส่อีเมลพี่ใน Test users (ข้อ 1)
