# บทคัดย่อ

<!-- ร่างโดยผู้ช่วย 2026-10-21 ตาม docs/thesis/draft/_rules.md · Pakon ต้องเรียบเรียงใหม่และตรวจระเบียบคณะเรื่องการใช้ AI · ตัวเลขทุกตัวมาจากไฟล์ที่ระบุในคอมเมนต์ -->

ชื่อโครงงาน: [ต้องเติม: ชื่อโครงงานภาษาไทย]
ผู้จัดทำ: [ต้องเติม: ชื่อ-นามสกุล รหัสนักศึกษา]
อาจารย์ที่ปรึกษา: [ต้องเติม: ชื่ออาจารย์ที่ปรึกษา]
สาขาวิชา / คณะ: [ต้องเติม] · ปีการศึกษา: [ต้องเติม]

โครงงานนี้พัฒนาคอมพิวเตอร์ผู้ช่วย AI ภาษาไทยบน Raspberry Pi 5 (RAM 8 GB) ที่เปิดเครื่องแล้วเข้าสู่หน้าจอของระบบทันที โดยใช้ Raspberry Pi OS ร่วมกับ greetd และ PAM สำหรับเข้าสู่ระบบ หน้าจอพัฒนาด้วย Qt Quick (PySide6) AI ในเครื่องคือ Gemma 4 E2B ที่ทำงานผ่าน llama.cpp และส่งต่อคำถามที่ต้องใช้ข้อมูลสดให้ Claude (ไฮบริด) วัตถุประสงค์มี 4 ข้อ ได้แก่ (1) งานประจำวันทำด้วย AI ภาษาไทยในเครื่อง และข้อมูลออกนอกเครื่องได้เฉพาะทางที่ประกาศและตรวจย้อนหลังได้ (2) ผู้ใช้หลายคนใช้เครื่องเดียวกันโดยแยกข้อมูลที่ระดับระบบปฏิบัติการ (3) งานที่ต้องถูกแน่นอน เช่น วันเวลาและการสั่งงานเครื่อง ใช้โค้ดแทน LLM และ (4) ให้ AI บน Cloud สร้างความสามารถใหม่ในรูปไฟล์สกิลที่ผ่านประตูตรวจ แล้วให้ AI ในเครื่องเลือกใช้ การประเมินผลประกาศเกณฑ์และชุดทดสอบก่อนวัด และบันทึกทุกรอบรวมรอบที่ไม่ผ่าน
<!-- ที่มา: docs/thesis/facts-ch1.md หัวข้อ 1.1–1.3 และ 1.5 · docs/thesis/facts-ch4.md หัวข้อ 4.0 -->

ผลการทดสอบพบว่า AI ในเครื่องได้ 93 คะแนนจากชุดสอบ 100 ข้อ บอกตรงเมื่อไม่มีข้อมูลสด 16/16 ข้อ และถูกห้ามต่อเครือข่ายด้วยกลไกของระบบปฏิบัติการ แต่ระบบไฮบริดได้ 90 คะแนน ต่ำกว่าเกณฑ์ที่ตั้งไว้ การแยกข้อมูลหลายผู้ใช้ผ่านการทดสอบ 14/14 กรณี งานวันเวลาและนัดหมายผ่านชุดทดสอบอิสระทุกชุด (20/20, 15/15 และ 20/20) ขณะที่การสั่งงานเครื่องได้ 93.0% ต่ำกว่าเกณฑ์ 95% ประตูตรวจปฏิเสธสกิลเสีย 15/15 และสกิลที่ Claude สร้างทำตามคำขอ 10/10 แต่ AI ในเครื่องเลือกสกิลถูกเพียง 42/58 และคำสั่งเสียงภาษาไทยชุดอิสระทำถูกประมาณร้อยละ 50 ข้อจำกัดสำคัญคือเครื่องร้อนจนถูกลดความเร็ว การประเมินเสียงใช้เสียงสังเคราะห์เป็นหลัก มีผู้ให้คะแนนภาษาไทยเพียงคนเดียว และยังไม่ได้ทดสอบกับกลุ่มผู้ใช้จริง
<!-- ที่มา: docs/thesis/facts-ch4.md หัวข้อ 4.2, 4.4–4.6 และ 4.9 · docs/thesis/facts-ch5.md หัวข้อ 5.1 · docs/evaluation/results-summary.md หัวข้อ N.1, N.3, N.5 และ 0.1 · docs/benchmarks/2026-10-05-thermal/README.md -->

คำสำคัญ: ผู้ช่วย AI ภาษาไทย / Raspberry Pi 5 / โมเดลภาษาขนาดเล็กในเครื่อง / AI แบบไฮบริด / ระบบหลายผู้ใช้ / สกิลที่ AI สร้าง

# Abstract

Project title: [ต้องเติม: English project title]
Author: [ต้องเติม: name, student ID]
Advisor: [ต้องเติม: advisor name]
Program / Faculty: [ต้องเติม] · Academic year: [ต้องเติม]

This project develops a Thai-language AI assistant computer on a Raspberry Pi 5 (8 GB RAM) that boots directly into the system's own screen. It runs on Raspberry Pi OS with greetd and PAM for login and a Qt Quick (PySide6) user interface. The on-device AI is Gemma 4 E2B served by llama.cpp, and questions that need live information are forwarded to Claude (hybrid mode). The project has four objectives: (1) everyday tasks are handled by an on-device Thai AI, and data leaves the device only through declared channels that the user can audit afterwards; (2) several people can share one machine with their data separated at the operating-system level; (3) tasks that must be exactly correct, such as dates, times and device commands, are handled by code rather than by an LLM; and (4) a cloud AI creates new capabilities as skill files that must pass a validation gate, and the on-device AI selects and uses them. All evaluation criteria and test sets were declared before measurement, and every round, including failed ones, was recorded.
<!-- ที่มา: docs/thesis/facts-ch1.md หัวข้อ 1.1–1.3 และ 1.5 · docs/thesis/facts-ch4.md หัวข้อ 4.0 -->

The on-device AI scored 93 out of 100 on the exam set, correctly said it did not know in 16 of 16 live-information questions, and is blocked from the network by operating-system mechanisms; however, the hybrid mode scored 90, failing its declared criterion. Multi-user separation passed 14 of 14 cases. Date, time and appointment tasks passed every independent test set (20/20, 15/15 and 20/20), while device commands reached 93.0%, below the 95% criterion. The validation gate rejected 15 of 15 faulty skills and Claude-generated skills did what was requested in 10 of 10 cases, but the on-device AI selected the correct skill in only 42 of 58 cases, and Thai voice commands on the independent set were about 50% correct. Key limitations are thermal throttling of the board, voice evaluation that relied mainly on synthetic speech, a single Thai-quality rater, and no study with a group of real users.
<!-- ที่มา: docs/thesis/facts-ch4.md หัวข้อ 4.2, 4.4–4.6 และ 4.9 · docs/thesis/facts-ch5.md หัวข้อ 5.1 · docs/evaluation/results-summary.md หัวข้อ N.1, N.3, N.5 และ 0.1 · docs/benchmarks/2026-10-05-thermal/README.md -->

Keywords: Thai AI assistant / Raspberry Pi 5 / on-device small language model / hybrid AI / multi-user system / AI-generated skills
