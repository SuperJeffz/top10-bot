"""ขอ Refresh Token ของ Google Drive แบบอัตโนมัติ (รันครั้งเดียว)

วิธีใช้:
  1) สร้าง OAuth client ID ชนิด "Desktop app" ใน Google Cloud Console
     (เปิดใช้ Google Drive API ในโปรเจกต์เดียวกันด้วย)
  2) ใส่ GOOGLE_DRIVE_CLIENT_ID / GOOGLE_DRIVE_CLIENT_SECRET ในไฟล์ backend/.env
  3) รัน:
         E:\\top10bot\\venv\\Scripts\\python.exe backend\\get_drive_token.py
  4) เบราว์เซอร์จะเปิดขึ้น -> ล็อกอิน -> กด Allow
  5) สคริปต์จะเขียน GOOGLE_DRIVE_REFRESH_TOKEN ลง backend/.env ให้เอง
"""

import os
import re
import sys
import json
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

from dotenv import load_dotenv

HERE = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(HERE, ".env")
load_dotenv(ENV_PATH)

SCOPE = "https://www.googleapis.com/auth/drive.file"
REDIRECT_PORT = 8010
REDIRECT_URI = f"http://localhost:{REDIRECT_PORT}/"

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"

_auth_code = {"value": None}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        qs = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(qs)
        if "code" in params:
            _auth_code["value"] = params["code"][0]
            body = "<h2>สำเร็จ! กลับไปดูหน้าต่าง Command Prompt ได้เลย</h2>"
            self.send_response(200)
        else:
            body = f"<h2>ไม่ได้ code: {params.get('error', ['?'])[0]}</h2>"
            self.send_response(400)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def log_message(self, *args):
        pass


def main():
    client_id = os.getenv("GOOGLE_DRIVE_CLIENT_ID", "").strip()
    client_secret = os.getenv("GOOGLE_DRIVE_CLIENT_SECRET", "").strip()

    if not client_id or not client_secret:
        print("❌ ยังไม่ได้ใส่ GOOGLE_DRIVE_CLIENT_ID / CLIENT_SECRET ใน backend/.env")
        sys.exit(1)

    params = {
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPE,
        "access_type": "offline",
        "prompt": "consent",
    }
    url = f"{AUTH_URL}?{urllib.parse.urlencode(params)}"
    print("เปิดเบราว์เซอร์เพื่ออนุญาตสิทธิ์...")
    print(url)
    webbrowser.open(url)

    server = HTTPServer(("localhost", REDIRECT_PORT), Handler)
    while _auth_code["value"] is None:
        server.handle_request()
    server.server_close()

    import requests

    resp = requests.post(
        TOKEN_URL,
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "code": _auth_code["value"],
            "grant_type": "authorization_code",
            "redirect_uri": REDIRECT_URI,
        },
        timeout=30,
    )
    data = resp.json()
    if "refresh_token" not in data:
        print("❌ ไม่ได้รับ refresh_token:", json.dumps(data, indent=2))
        sys.exit(1)

    token = data["refresh_token"]
    with open(ENV_PATH, encoding="utf-8") as f:
        content = f.read()
    if re.search(r"^GOOGLE_DRIVE_REFRESH_TOKEN=.*$", content, re.M):
        content = re.sub(
            r"^GOOGLE_DRIVE_REFRESH_TOKEN=.*$",
            f"GOOGLE_DRIVE_REFRESH_TOKEN={token}",
            content,
            flags=re.M,
        )
    else:
        content += f"\nGOOGLE_DRIVE_REFRESH_TOKEN={token}\n"
    with open(ENV_PATH, "w", encoding="utf-8") as f:
        f.write(content)

    print("✅ บันทึก refresh token ลง backend/.env แล้ว")
    print("   ปิดหน้าต่าง backend แล้วเปิดใหม่ (หรือรัน start.bat) เพื่อให้ค่าใหม่มีผล")


if __name__ == "__main__":
    main()
