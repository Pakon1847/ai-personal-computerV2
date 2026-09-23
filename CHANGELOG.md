# Changelog

## ยังไม่ออกเวอร์ชัน

- เฟส 0.1: โครง repo ตาม BRIEF หัวข้อ 10 · แยก threat model และ ADR ออกจาก brief · ตัดสิน ADR-014 (ใช้ในงานศึกษาเท่านั้น)
- เฟส 0.2: เครื่องมือวัดผล `python -m aipc.bench` บังคับ warm-up ≥1, วัด ≥5 รอบ, เก็บอุณหภูมิ/get_throttled ทุกรอบ, ตัดสินระดับหลักฐานเอง, ไม่เขียนทับผลเก่า
- เฟส 0.3: ตัวตรวจฮาร์ดแวร์ `python -m aipc.doctor` แบบอ่านอย่างเดียว (บอร์ด, RAM, ไฟเลี้ยง, พัดลม, RTC, OS, glibc, ที่เก็บ, fscrypt, กล้อง, เสียง) · อ่านไม่ได้ = "ไม่รู้" ไม่ใช่ "ผ่าน"
- เฟส 0.4: ตัวตรวจช่องโหว่ image `python -m aipc.doctor --audit` (sudo ไม่ใส่รหัส, กลุ่ม sudo/adm/video, บริการเข้าถึงระยะไกล, พอร์ตที่เปิดรับจากนอกเครื่อง, สิทธิ์โหนดกล้อง, สิทธิ์ home, KillUserProcesses/linger, swap บนดิสก์)
- เฟส 0.7 (เครื่องมือ): `python -m aipc.spikes.llm` ห่อ llama-bench วัด pp/tg tok/s แยกกัน, เวลา prefill 200 token เทียบเกณฑ์ BRIEF 5.4, RAM สูงสุด และโหมด soak · runner รองรับค่าที่โปรแกรมรายงานเอง (metrics) · runbook สำหรับรันบน Pi
