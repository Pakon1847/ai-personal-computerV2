---
name: tdd
description: Test-driven development. Use when the user wants to build features or fix bugs test-first, mentions "red-green-refactor", or wants integration tests.
---

> **หมายเหตุของโปรเจกต์ AI Personal Computer V2** (ผู้ช่วยเพิ่ม 2026-10-26 · **กฎใน CLAUDE.md มาก่อนเสมอ**)
>
> - ฟีเจอร์ใหม่ต้องมีการ์ดที่ Pakon อนุมัติก่อนเขียนเทสต์หรือโค้ด · seam ที่จะเทสต์ให้ยึดเกณฑ์ผ่านในการ์ด (`docs/design/`) แล้วถาม Pakon ตามข้อ "confirm them with the user"
> - โปรเจกต์ใช้ `unittest` ไม่ใช่ Jest/pytest (ตัวอย่างด้านล่างเป็น TypeScript) · รัน: `./.venv/Scripts/python.exe -m unittest tests.<ไฟล์> -v` · ทั้งชุดต้องผ่านก่อน commit
> - ห้ามเพิ่ม dependency เพื่อเทสต์โดยไม่ถาม (กฎเหล็กข้อ 5) · ห้ามแก้ `tests/data/` ให้ผ่าน และห้ามใช้ชุดทดสอบ held-out ปรับโค้ด/prompt (H9)
> - โปรเจกต์ไม่มี `GLOSSARY.md` → ใช้คำตาม `docs/BRIEF.md` หัวข้อ 4 · ADR อยู่ที่ `docs/adr/` · ไม่มี skill `codebase-design` (ข้ามได้)
> - งานภาษาของ LLM (ผลไม่แน่นอน) ไม่ใช่ที่ของ unit test → วัดด้วย skill `measure-h9` · unit test ใช้กับงานที่ต้องถูกแน่นอน (H6)
> - อธิบายเทสต์แต่ละตัวให้ Pakon เข้าใจว่าจับอะไรได้และพลาดอะไร (docs/ROLE.md)

# Test-Driven Development

TDD is the red → green loop. This skill is the reference that makes that loop produce tests worth keeping: what a good test is, where tests go, the anti-patterns, and the rules of the loop. Every section applies on every cycle: consult them before and during the loop, not after.

When exploring the codebase, read `GLOSSARY.md` (if it exists) so test names and interface vocabulary match the project's domain language, and respect ADRs in the area you're touching.

## What a good test is

Tests verify behavior through public interfaces, not implementation details. Code can change entirely; tests shouldn't. A good test reads like a specification: "user can checkout with valid cart" tells you exactly what capability exists, and it survives refactors because it doesn't care about internal structure.

See [tests.md](tests.md) for examples and [mocking.md](mocking.md) for mocking guidelines.

## Seams: where tests go

A **seam** is the public boundary you test at: the interface where you observe behavior without reaching inside. Tests live at seams, never against internals.

**Test only at pre-agreed seams.** Before writing any test, write down the seams under test and confirm them with the user. No test is written at an unconfirmed seam. You can't test everything, so agreeing the seams up front is how testing effort lands on the critical paths and complex logic instead of every edge case.

Ask: "What's the public interface, and which seams should we test?" Give each proposed seam a one-line note on what it catches and what it misses.

When the shape of that interface is itself in question (how deep the module is, where the seam belongs, what the interface should expose), call the Skill tool with "codebase-design" for the vocabulary. It is the shared source of the module, interface, depth, seam, adapter, leverage and locality terms, and it is a reference to consult, not a session to run.

## Anti-patterns

- **Implementation-coupled**: mocks internal collaborators, tests private methods, or verifies through a side channel (querying the database instead of using the interface). The tell: the test breaks when you refactor but behavior hasn't changed.
- **Tautological**: the assertion recomputes the expected value the way the code does (`expect(add(a, b)).toBe(a + b)`, a snapshot derived by hand the same way, a constant asserted equal to itself), so it passes by construction and can never disagree with the code. Expected values must come from an independent source of truth: a known-good literal, a worked example, the spec.
- **Horizontal slicing**: writing all tests first, then all implementation. Bulk tests verify _imagined_ behavior: you test the _shape_ of things rather than user-facing behavior, the tests go insensitive to real changes, and you commit to test structure before understanding the implementation. Work in **vertical slices** instead: one test → one implementation → repeat, each test a **tracer bullet** that responds to what the last cycle taught you.

## Rules of the loop

- **Red before green.** Write the failing test first, then only enough code to pass it. Don't anticipate future tests or add speculative features.
- **One slice at a time.** One seam, one test, one minimal implementation per cycle.
- **Refactoring is not part of the loop.** It belongs to the review stage (see the `code-review` skill), not the red → green implementation cycle.
