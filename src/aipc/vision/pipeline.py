"""ต่อทุกขั้นเข้าด้วยกัน: สแกน (1:N หลายเฟรม) และลงทะเบียน (การ์ด 0005 ข้อ 4, 6).

ต่อเฟรม:  ตรวจหน้า → quality gate → PAD → align → embedding   (จับเวลาทุกขั้น)
สแกน:     เก็บเฟรมที่ผ่านจนได้ 3–5 เฟรม → เลือกดีสุด → เฉลี่ย → จับคู่ (threshold + margin)
ลงทะเบียน: ให้ทำ 5 ท่า (ตรง ซ้าย ขวา เงย ก้ม · การ์ด 0010) · แม่แบบใช้เฉพาะท่าใน cfg.template_poses
           (ค่าเริ่มต้น ตรง/ซ้าย/ขวา) → ท่าที่ไม่ได้ใช้ในแม่แบบ ขาดได้ ไม่ทำให้ลงทะเบียนไม่สำเร็จ

PAD ไม่ผ่านแม้เฟรมเดียว = ปฏิเสธทั้งการสแกนทันที (ข้อกำหนดที่ Pakon ส่งมา) · ไม่รอเฟรมถัดไปเผื่อผ่าน
ตัวตรวจหน้า/PAD/embedding ส่งเข้ามาจากข้างนอก → เทสต์ด้วยตัวปลอมได้ ไม่ต้องมีกล้องหรือโมเดล
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import numpy as np

from aipc.vision import align, matching, quality
from aipc.vision.config import FaceConfig
from aipc.vision.quality import Face

# ข้อความถึงผู้ใช้ของเหตุผลที่ไม่ได้มาจาก quality gate
ADVICE = {
    "multiple_faces": "มีหลายคนในภาพ · ให้เหลือคนเดียวหน้ากล้อง",
    "spoof": "ยืนยันไม่ได้ว่าเป็นใบหน้าจริง · ใช้รหัสผ่านแทน",
    "not_enough_frames": "ยังได้ภาพที่ชัดไม่พอ · ลองอีกครั้ง",
    "below_threshold": "ไม่พบบัญชีที่ตรงกับใบหน้านี้",
    "ambiguous": "ไม่แน่ใจว่าเป็นบัญชีไหน · พิมพ์ชื่อผู้ใช้แทน",
    "no_templates": "ยังไม่มีใครลงทะเบียนใบหน้า",
    "missing_pose": "ต้องการภาพเพิ่ม: {} ",
}
POSE_NAMES = {
    "front": "หน้าตรง",
    "left": "หันซ้ายเล็กน้อย",
    "right": "หันขวาเล็กน้อย",
    "up": "เงยหน้าเล็กน้อย",
    "down": "ก้มหน้าเล็กน้อย",
}
ENROLL_POSES = tuple(POSE_NAMES)  # ลำดับที่หน้าจอบอกผู้ใช้
SECOND_FACE_RATIO = 0.6  # หน้าที่สองใหญ่ ≥ 60% ของหน้าแรก = มีอีกคนอยู่ใกล้ ๆ จริง ไม่ใช่คนเดินผ่านไกล ๆ
POSE_SPLIT_DEG = 8.0  # มุม ≤ 8° = หน้าตรง · เกินกว่านั้นนับเป็นหัน/ก้มเงย (ยังต้องไม่เกิน max_*_deg)


def pose_of(q: quality.Quality) -> str | None:
    """แบ่งท่าจากมุมที่ประมาณได้ · หันและก้มเงยพร้อมกัน = ท่ากำกวม ไม่นับ (None).

    yaw > 0 = ขวา (ตามภาพจากกล้อง ไม่กลับด้าน) · pitch > 0 = จมูกต่ำลง = ก้ม · pitch < 0 = เงย
    """
    turned, tilted = abs(q.yaw) > POSE_SPLIT_DEG, abs(q.pitch) > POSE_SPLIT_DEG
    if turned and tilted:
        return None
    if turned:
        return "right" if q.yaw > 0 else "left"
    if tilted:
        return "down" if q.pitch > 0 else "up"
    return "front"


@dataclass
class FrameResult:
    ok: bool
    reason: str = ""  # ว่าง = ผ่าน
    quality: quality.Quality | None = None
    live: float | None = None
    embedding: np.ndarray | None = None
    timings_ms: dict = field(default_factory=dict)
    box: tuple | None = None  # กรอบหน้า (x, y, w, h) px ในภาพ · ใช้วาดกรอบบนภาพสด (การ์ด 0010)

    @property
    def advice(self) -> str:
        if self.quality is not None and not self.quality.ok:
            return self.quality.advice
        # เหตุผลของ quality gate อาจมาโดยไม่มีผล quality แนบ (เช่น no_face) → หาจากทั้งสองตาราง
        return quality.ADVICE.get(self.reason) or ADVICE.get(self.reason, "")


@dataclass
class ScanResult:
    account: str | None
    reason: str  # matched | spoof | not_enough_frames | below_threshold | ambiguous | no_templates
    score: float = -1.0
    second: float = -1.0
    frames_used: int = 0
    frames_seen: int = 0
    timings_ms: dict = field(default_factory=dict)  # รวมทุกเฟรม ต่อขั้น
    total_ms: float = 0.0
    last_advice: str = ""
    # เวกเตอร์เฉลี่ยของการสแกนนี้ · อยู่ในหน่วยความจำเท่านั้น (ScanLog ไม่เขียน) · ใช้เทียบแม่แบบหลายแบบ
    # กับการสแกนครั้งเดียวกัน (การ์ด 0010 ข้อ 8)
    probe: np.ndarray | None = field(default=None, repr=False)

    @property
    def advice(self) -> str:
        if self.account:
            return ""
        general = ADVICE.get(self.reason, "")
        # "ภาพไม่พอ" อย่างเดียวผู้ใช้ทำอะไรต่อไม่ได้ → ต่อท้ายเหตุผลของ quality gate เฟรมล่าสุด
        if self.reason == "not_enough_frames" and self.last_advice:
            return f"{general} · {self.last_advice}"
        return general or self.last_advice


class FaceScanner:
    def __init__(self, detector, liveness, embedder, cfg: FaceConfig, clock=time.perf_counter):
        self.detector, self.liveness, self.embedder, self.cfg = detector, liveness, embedder, cfg
        self._clock = clock

    # ---------- ต่อเฟรม ----------
    def process(self, frame: np.ndarray) -> FrameResult:
        t = {}
        start = self._clock()

        def lap(name):
            nonlocal start
            now = self._clock()
            t[name] = (now - start) * 1000
            start = now

        rows = [r for r in self.detector.detect(frame) if float(r[14]) >= self.cfg.min_detect_score]
        lap("detect")
        faces = [Face.from_yunet(r) for r in rows]
        face = faces[0] if faces else None
        if len(faces) > 1:
            first = faces[0].box[2] * faces[0].box[3]
            if faces[1].box[2] * faces[1].box[3] >= SECOND_FACE_RATIO * first:
                return FrameResult(False, "multiple_faces", timings_ms=t)

        q = quality.check(frame, face, self.cfg)
        lap("quality")
        box = tuple(face.box) if face is not None else None
        if not q.ok:
            return FrameResult(False, q.reasons[0], q, timings_ms=t, box=box)

        live = self.liveness.score(frame, face.box)
        lap("liveness")
        if live < self.cfg.liveness_threshold:
            return FrameResult(False, "spoof", q, live, timings_ms=t, box=box)

        aligned = align.crop(frame, face.landmarks)
        lap("align")
        emb = matching.l2_normalize(self.embedder.embed(aligned))
        lap("embed")
        return FrameResult(True, "", q, live, emb, t, box)

    # ---------- สแกน 1:N ----------
    def scan(
        self,
        frames: Iterable[np.ndarray],
        templates: dict[str, np.ndarray],
        progress: Callable[[FrameResult, dict], None] | None = None,
    ) -> ScanResult:
        """อ่านเฟรมไปเรื่อย ๆ จนได้เฟรมดีครบ max_frames หรือเฟรมหมด.

        progress(ผลเฟรม, {"good": จำนวนเฟรมที่ผ่าน}) ถูกเรียกทุกเฟรม · ให้หน้าจอแสดงคำแนะนำสด
        """
        t0 = self._clock()
        good: list[FrameResult] = []
        seen, sums, advice = 0, {}, ""
        for frame in frames:
            seen += 1
            r = self.process(frame)
            for k, v in r.timings_ms.items():
                sums[k] = sums.get(k, 0.0) + v
            if r.reason == "spoof":
                return self._done(ScanResult(None, "spoof", frames_seen=seen, timings_ms=sums), t0)
            if r.ok:
                good.append(r)
            else:
                advice = r.advice
            if progress:
                progress(r, {"good": len(good)})
            if len(good) >= self.cfg.max_frames:
                break
        best = matching.select_best(good, lambda r: r.quality.score, self.cfg.min_frames,
                                    self.cfg.max_frames)  # fmt: skip
        if not best:
            res = ScanResult(None, "not_enough_frames", frames_used=len(good), frames_seen=seen,
                             timings_ms=sums, last_advice=advice)  # fmt: skip
            return self._done(res, t0)
        start = self._clock()
        probe = matching.average([r.embedding for r in best])
        m = matching.match(probe, templates, self.cfg.match_threshold, self.cfg.match_margin)
        sums["match"] = (self._clock() - start) * 1000
        res = ScanResult(m.account, m.reason, m.score, m.second, len(best), seen, sums, probe=probe)
        return self._done(res, t0)

    def _done(self, res: ScanResult, t0: float) -> ScanResult:
        res.total_ms = (self._clock() - t0) * 1000
        return res

    # ---------- ลงทะเบียน ----------
    def enroll(
        self,
        frames: Iterable[np.ndarray],
        per_pose: int = 2,
        progress: Callable[[FrameResult, dict], None] | None = None,
    ) -> Template | Rejected:
        """ให้ทำครบ 5 ท่า ท่าละ per_pose เฟรม · แม่แบบใช้เฉพาะ cfg.template_poses · PAD ไม่ผ่าน = ยกเลิกทันที.

        progress(ผลเฟรม, {ท่า: จำนวน}) ถูกเรียกทุกเฟรม (หน้าจอบอกว่าท่าไหนได้แล้ว)
        เฟรมหมดก่อนครบ: ท่าในแม่แบบครบ = สำเร็จ (ท่าที่ขาดอยู่ใน Template.missing) · ไม่ครบ = Rejected

        ผู้เรียก (หน้าจอลงทะเบียน) ต้องยืนยันตัวตนแล้วเท่านั้น (BRIEF 5.1 ข้อ 6) — ฟังก์ชันนี้ไม่ตรวจสิทธิ์
        """
        needed = tuple(self.cfg.template_poses)
        bins: dict[str, list[FrameResult]] = {p: [] for p in ENROLL_POSES}
        reasons: list[str] = []
        for frame in frames:
            r = self.process(frame)
            if r.reason == "spoof":
                return Rejected(("spoof",), ADVICE["spoof"], "spoof")
            pose = pose_of(r.quality) if r.ok else None
            if pose is not None:
                bins[pose].append(r)
            elif not r.ok:
                reasons.append(r.reason)
            if progress:
                progress(r, {p: len(v) for p, v in bins.items()})
            if all(len(v) >= per_pose for v in bins.values()):
                break
        common = max(set(reasons), key=reasons.count) if reasons else ""
        missing = tuple(p for p in ENROLL_POSES if len(bins[p]) < per_pose)
        lacking = tuple(p for p in needed if p in missing)
        if lacking:
            names = ", ".join(POSE_NAMES[p] for p in lacking)
            hint = quality.ADVICE.get(common) or ADVICE.get(common, "")
            return Rejected(lacking, ADVICE["missing_pose"].format(names) + hint, common)
        # ท่าละ per_pose เฟรมที่คุณภาพดีสุด → ทุกท่ามีน้ำหนักเท่ากันในแม่แบบ
        best = {p: sorted(v, key=lambda r: r.quality.score)[-per_pose:] for p, v in bins.items()}
        chosen = [r for p in needed for r in best[p]]
        return Template(
            matching.average([r.embedding for r in chosen]),
            len(chosen),
            datetime.now().astimezone().isoformat(timespec="seconds"),
            missing=missing,
            # อยู่ในหน่วยความจำเท่านั้น ใช้เทียบแม่แบบ 3 ท่ากับ 5 ท่า (การ์ด 0010 ข้อ 8) · ไม่ลงดิสก์
            by_pose={p: [r.embedding for r in v] for p, v in best.items() if v},
        )


@dataclass(frozen=True)
class Template:
    vector: np.ndarray
    frames: int
    created: str
    missing: tuple[str, ...] = ()  # ท่าที่ทำไม่ครบแต่ไม่ได้ใช้ในแม่แบบ
    by_pose: dict = field(default_factory=dict, repr=False)


@dataclass(frozen=True)
class Rejected:
    reasons: tuple[str, ...]
    advice: str
    common: str = ""  # เหตุผลของเฟรมที่ไม่ผ่านที่พบบ่อยสุด (ใช้ใน log การลงทะเบียน)


def _append_line(path: Path, entry: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(entry, ensure_ascii=False) + "\n"
    # เปิดแบบต่อท้าย + เขียนทีเดียวต่อบรรทัด · ไฟล์ของผู้ใช้เท่านั้นอ่านได้ (0600)
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    try:
        os.write(fd, line.encode("utf-8"))
    finally:
        os.close(fd)


class EnrollLog:
    """log การลงทะเบียน 1 บรรทัด JSON · แยกไฟล์จาก ScanLog.

    (report.py อ่าน ScanLog โดยถือว่าทุกบรรทัดเป็นการสแกน จึงเขียนลงไฟล์เดียวกันไม่ได้)

    ไม่มีภาพ ไม่มี embedding · มีแค่ผล ท่าที่ขาด เหตุผลที่พบบ่อย และเวลา (การ์ด 0010 ข้อ 5)
    """

    FIELDS = ("time", "result", "missing", "common_reason", "seconds", "frames")

    def __init__(self, path: Path):
        self.path = path

    def write(self, res, seconds: float, result: str = "") -> dict:
        """res = Template | Rejected | None · result ว่าง = ตัดสินจาก res (ส่งเองได้ เช่น "cancelled")."""
        ok = isinstance(res, Template)
        if res is None:
            missing = []
        else:
            missing = list(res.missing if ok else res.reasons)
        entry = {
            "time": datetime.now().astimezone().isoformat(timespec="seconds"),
            "result": result or ("enrolled" if ok else "rejected"),
            "missing": missing,
            "common_reason": res.common if isinstance(res, Rejected) else "",
            "seconds": round(seconds, 1),
            "frames": res.frames if ok else 0,
        }
        _append_line(self.path, entry)
        return entry


class ScanLog:
    """log ทุกการสแกน 1 บรรทัด JSON · **ไม่มีภาพ ไม่มี embedding** (การ์ด 0005 ข้อ 5, H3).

    มีแค่: เวลา, ผล, คะแนน, เหตุผล, จำนวนเฟรม, เวลาต่อขั้น · ชื่อบัญชีบันทึกเฉพาะเมื่อจับคู่ได้
    """

    FIELDS = ("time", "subject", "result", "account", "score", "second", "reason", "frames_used",
              "frames_seen", "total_ms", "timings_ms")  # fmt: skip

    def __init__(self, path: Path):
        self.path = path

    def write(self, res: ScanResult, subject: str | None = None) -> dict:
        """subject = รหัสผู้ที่กำลังสแกนจริง (เฉพาะตอนทดสอบ เช่น P01) · ใช้หา FRR/จับผิดคน."""
        entry = {
            "time": datetime.now().astimezone().isoformat(timespec="seconds"),
            "subject": subject,
            "result": "matched" if res.account else "rejected",
            "account": res.account,
            "score": round(res.score, 4),
            "second": round(res.second, 4),
            "reason": res.reason,
            "frames_used": res.frames_used,
            "frames_seen": res.frames_seen,
            "total_ms": round(res.total_ms, 1),
            "timings_ms": {k: round(v, 1) for k, v in res.timings_ms.items()},
        }
        _append_line(self.path, entry)
        return entry
