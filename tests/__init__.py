import os

# ไม่ให้เทสต์เห็นแอปที่ติดตั้งจริงในเครื่อง (apps.py) · ผลของตัวแปลคำสั่งเหมือนกันทุกเครื่อง
os.environ.setdefault("AIPC_APP_DIRS", "")
