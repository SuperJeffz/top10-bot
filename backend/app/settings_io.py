"""อ่าน/เขียนค่าในไฟล์ .env แบบง่าย (ใช้เมื่อเปลี่ยนค่าจากหน้าเว็บ)"""

import os
import re

ENV_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"
)


def update_env(updates: dict):
    content = ""
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH, encoding="utf-8") as f:
            content = f.read()

    for key, value in updates.items():
        if value is None:
            continue
        value = str(value)
        pattern = re.compile(rf"^{re.escape(key)}=.*$", re.M)
        if pattern.search(content):
            content = pattern.sub(f"{key}={value}", content)
        else:
            if content and not content.endswith("\n"):
                content += "\n"
            content += f"{key}={value}\n"
        os.environ[key] = value

    with open(ENV_PATH, "w", encoding="utf-8") as f:
        f.write(content)
