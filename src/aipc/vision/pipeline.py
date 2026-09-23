"""ต่อทุกขั้นเข้าด้วยกัน: สแกน (1:N หลายเฟรม) และลงทะเบียน (การ์ด 0005 ข้อ 4, 6).

ต่อเฟรม:  ตรวจหน้า → quality gate → PAD → align → embedding   (จับเวลาทุกขั้น)
สแกน:     เก็บเฟรมที่ผ่านจนได้ 3–5 เฟรม → เลือกดีสุด → เฉลี่ย → จับคู่ (threshold + margin)
ลงทะเบียน: ต้องได้ทั้งหน้าตรง หันซ้าย และหันขวาเล็กน้อย ครบก่อน → รวมเป็นแม่แบบเดียว

PAD ไม่ผ่านแม้เฟรมเดียว = ปฏิเสธทั้งการสแกนทันที (ข้อกำหนดที่ Pakon ส่งมา) · ไม่รอเฟรมถัดไปเผื่อผ่าน
ตัวตรวจหน้า/PAD/embedding ส่งเข้ามาจากข้างนอก → เทสต์ด้วยตัวปลอมได้ ไม่ต้องมีกล้องหรือโมเดล
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Iterable
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
POSE_NAMES = {"front": "หน้าตรง", "left": "หันซ้ายเล็กน้อย", "right": "หันขวาเล็กน้อย"}
SECOND_FACE_RATIO = 0.6  # หน้าที่สองใหญ่ ≥ 60% ของหน้าแรก = มีอีกคนอยู่ใกล้ ๆ จริง ไม่ใช่คนเดินผ่านไกล ๆ
POSE_SPLIT_DEG = 8.0  # |yaw| ≤ 8° = หน้าตรง · เกินกว่านั้นนับเป็นหันซ้าย/ขวา (ยังต้องไม่เกิน max_yaw_deg)


@dataclass
class FrameResult:
    ok: bool
    reason: str = ""  # ว่าง = ผ่าน
    quality: quality.Quality | None = None
    live: float | None = None
    embedding: np.ndarray | None = None
    timings_ms: dict = field(default_factory=dict)

    @property
    def advice(self) -> str:
        if self.quality is not None and not self.quality.ok:
            return self.quality.advice
        return ADVICE.get(self.reason, "")


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

    @property
    def advice(self) -> str:
        return "" if self.account else (ADVICE.get(self.reason) or self.last_advice)


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
        if not q.ok:
            return FrameResult(False, q.reasons[0], q, timings_ms=t)

        live = self.liveness.score(frame, face.box)
        lap("liveness")
        if live < self.cfg.liveness_threshold:
            return FrameResult(False, "spoof", q, live, timings_ms=t)

        aligned = align.crop(frame, face.landmarks)
        lap("align")
        emb = matching.l2_normalize(self.embedder.embed(aligned))
        lap("embed")
        return FrameResult(True, "", q, live, emb, t)

    # ---------- สแกน 1:N ----------
    def scan(self, frames: Iterable[np.ndarray], templates: dict[str, np.ndarray]) -> ScanResult:
        """อ่านเฟรมไปเรื่อย ๆ จนได้เฟรมดีครบ max_frames หรือเฟรมหมด."""
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
                if len(good) >= self.cfg.max_frames:
                    break
            else:
                advice = r.advice
        best = matching.select_best(good, lambda r: r.quality.score, self.cfg.min_frames,
                                    self.cfg.max_frames)  # fmt: skip
        if not best:
            res = ScanResult(None, "not_enough_frames", frames_used=len(good), frames_seen=seen,
                             timings_ms=sums, last_advice=advice)  # fmt: skip
            return self._done(res, t0)
        start = self._clock()
        m = matching.match(matching.average([r.embedding for r in best]), templates,
                           self.cfg.match_threshold, self.cfg.match_margin)  # fmt: skip
        sums["match"] = (self._clock() - start) * 1000
        res = ScanResult(m.account, m.reason, m.score, m.second, len(best), seen, sums)
        return self._done(res, t0)

    def _done(self, res: ScanResult, t0: float) -> ScanResult:
        res.total_ms = (self._clock() - t0) * 1000
        return res

    # ---------- ลงทะเบียน ----------
    def enroll(self, frames: Iterable[np.ndarray], per_pose: int = 2) -> Template | Rejected:
        """ต้องได้เฟรมดีท่าละ per_pose เฟรม ครบทั้งหน้าตรง/ซ้าย/ขวา · PAD ไม่ผ่าน = ยกเลิกทันที.

        ผู้เรียก (หน้าจอลงทะเบียน) ต้องยืนยันตัวตนแล้วเท่านั้น (BRIEF 5.1 ข้อ 6) — ฟังก์ชันนี้ไม่ตรวจสิทธิ์
        """
        bins: dict[str, list[FrameResult]] = {"front": [], "left": [], "right": []}
        reasons: list[str] = []
        for frame in frames:
            r = self.process(frame)
            if r.reason == "spoof":
                return Rejected(("spoof",), ADVICE["spoof"])
            if not r.ok:
                reasons.append(r.reason)
                continue
            yaw = r.quality.yaw
            pose = "front" if abs(yaw) <= POSE_SPLIT_DEG else ("right" if yaw > 0 else "left")
            bins[pose].append(r)
            if all(len(v) >= per_pose for v in bins.values()):
                break
        missing = [p for p, v in bins.items() if len(v) < per_pose]
        if missing:
            names = ", ".join(POSE_NAMES[p] for p in missing)
            common = max(set(reasons), key=reasons.count) if reasons else ""
            hint = quality.ADVICE.get(common) or ADVICE.get(common, "")
            return Rejected(tuple(missing), ADVICE["missing_pose"].format(names) + hint)
        # ท่าละ per_pose เฟรมที่คุณภาพดีสุด → ทุกท่ามีน้ำหนักเท่ากันในแม่แบบ
        chosen = [r for v in bins.values()
                  for r in sorted(v, key=lambda r: r.quality.score)[-per_pose:]]  # fmt: skip
        vec = matching.average([r.embedding for r in chosen])
        return Template(vec, len(chosen), datetime.now().astimezone().isoformat(timespec="seconds"))


@dataclass(frozen=True)
class Template:
    vector: np.ndarray
    frames: int
    created: str


@dataclass(frozen=True)
class Rejected:
    reasons: tuple[str, ...]
    advice: str


class ScanLog:
    """log ทุกการสแกน 1 บรรทัด JSON · **ไม่มีภาพ ไม่มี embedding** (การ์ด 0005 ข้อ 5, H3).

    มีแค่: เวลา, ผล, คะแนน, เหตุผล, จำนวนเฟรม, เวลาต่อขั้น · ชื่อบัญชีบันทึกเฉพาะเมื่อจับคู่ได้
    """

    FIELDS = ("time", "result", "account", "score", "second", "reason", "frames_used",
              "frames_seen", "total_ms", "timings_ms")  # fmt: skip

    def __init__(self, path: Path):
        self.path = path

    def write(self, res: ScanResult) -> dict:
        entry = {
            "time": datetime.now().astimezone().isoformat(timespec="seconds"),
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
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(entry, ensure_ascii=False) + "\n"
        # เปิดแบบต่อท้าย + เขียนทีเดียวต่อบรรทัด · ไฟล์ของผู้ใช้เท่านั้นอ่านได้ (0600)
        fd = os.open(self.path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        try:
            os.write(fd, line.encode("utf-8"))
        finally:
            os.close(fd)
        return entry
