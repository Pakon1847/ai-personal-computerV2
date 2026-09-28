"""ให้ PAM ของ Linux ตรวจรหัสผ่าน (การ์ด 0012) · standard library อย่างเดียว.

PAM คือระบบตรวจรหัสผ่านกลางของ Linux ตัวเดียวกับที่ใช้ตอน login · โค้ดเราไม่อ่าน /etc/shadow เอง
ctypes = วิธีเรียกฟังก์ชันภาษา C ของระบบจาก Python โดยไม่ต้องติดตั้งไลบรารีเพิ่ม

ขั้นตอนของ PAM: pam_start (บอกว่าจะตรวจใคร ด้วยกฎชุดไหน) → pam_authenticate (PAM ถามรหัสผ่าน
ผ่าน "ฟังก์ชันสนทนา" ที่เราให้ไว้ เราตอบด้วยรหัสที่ได้รับมา) → pam_acct_mgmt (บัญชียังใช้ได้ไหม
เช่น ไม่หมดอายุ ไม่ถูกล็อก) → pam_end · ใช้ได้บน Linux เท่านั้น
"""

from __future__ import annotations

import ctypes
import ctypes.util

PAM_SUCCESS = 0
PAM_BUF_ERR = 5
PAM_PROMPT_ECHO_OFF = 1  # PAM ถามแบบไม่แสดงตัวอักษร = ถามรหัสผ่าน
PAM_PROMPT_ECHO_ON = 2  # PAM ถามแบบแสดงตัวอักษร = ถามชื่อผู้ใช้


class _Message(ctypes.Structure):
    _fields_ = [("msg_style", ctypes.c_int), ("msg", ctypes.c_char_p)]


class _Response(ctypes.Structure):
    _fields_ = [("resp", ctypes.c_void_p), ("resp_retcode", ctypes.c_int)]


_CONV = ctypes.CFUNCTYPE(
    ctypes.c_int,
    ctypes.c_int,
    ctypes.POINTER(ctypes.POINTER(_Message)),
    ctypes.POINTER(ctypes.POINTER(_Response)),
    ctypes.c_void_p,
)


class _Conv(ctypes.Structure):
    _fields_ = [("conv", _CONV), ("appdata_ptr", ctypes.c_void_p)]


def authenticate(service: str, user: str, password: str) -> bool:
    """True = PAM ยืนยันว่ารหัสผ่านถูกและบัญชียังใช้ได้ · อย่างอื่นทั้งหมด = False."""
    libpam = ctypes.CDLL(ctypes.util.find_library("pam"))
    libc = ctypes.CDLL(ctypes.util.find_library("c"))
    # คำตอบต้องจองด้วย malloc ของ C เพราะ PAM เป็นคนคืนหน่วยความจำ (free) เอง
    libc.calloc.restype, libc.calloc.argtypes = ctypes.c_void_p, [ctypes.c_size_t, ctypes.c_size_t]
    libc.strdup.restype, libc.strdup.argtypes = ctypes.c_void_p, [ctypes.c_char_p]
    libpam.pam_start.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.POINTER(_Conv),
                                 ctypes.POINTER(ctypes.c_void_p)]  # fmt: skip
    for name in ("pam_authenticate", "pam_acct_mgmt", "pam_end"):
        getattr(libpam, name).argtypes = [ctypes.c_void_p, ctypes.c_int]
    answers = {PAM_PROMPT_ECHO_OFF: password.encode(), PAM_PROMPT_ECHO_ON: user.encode()}

    @_CONV
    def conversation(n, messages, responses, _data):
        arr = libc.calloc(n, ctypes.sizeof(_Response))
        if not arr:
            return PAM_BUF_ERR
        responses[0] = ctypes.cast(arr, ctypes.POINTER(_Response))
        for i in range(n):
            answer = answers.get(messages[i].contents.msg_style)
            if answer is not None:
                responses[0][i].resp = libc.strdup(answer)
        return PAM_SUCCESS

    conv = _Conv(conversation, None)  # ต้องเก็บตัวแปรไว้ ไม่งั้น Python เก็บกวาดทิ้งระหว่าง PAM ยังเรียกอยู่
    handle = ctypes.c_void_p()
    rc = libpam.pam_start(service.encode(), user.encode(), ctypes.byref(conv), ctypes.byref(handle))
    if rc != PAM_SUCCESS:
        return False
    try:
        rc = libpam.pam_authenticate(handle, 0)
        if rc == PAM_SUCCESS:
            rc = libpam.pam_acct_mgmt(handle, 0)
        return rc == PAM_SUCCESS
    finally:
        libpam.pam_end(handle, rc)
