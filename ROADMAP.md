# Photosort Roadmap

Development roadmap for photosort.

## Progress Tracking

- `[ ]` Todo
- `[-]` In progress (append start date)
- `[x]` Completed (append completion date)

## High Priority

- [ ] **Test coverage for merge safety fixes**: Add targeted tests for LP basename collision resolution (H2) and full-file hash duplicate detection (C2) — currently only exercised incidentally
- [ ] **LP collision: partial-import edge case**: `_resolve_basename_collision()` checks image-side duplicates to break the loop, but doesn't independently check the video side; a prior partial import (image present, video missing) could cause the video to be skipped

## Medium Priority

- [ ] **Timezone threading for API consumers**: `timestamps.py` reads `Config()` at module import time, locking timezone for the process lifetime; fine for CLI but a latent issue for library/programmatic use
- [ ] **ffmpeg error decoding**: `conversion.py:176` logs `e.stderr` as bytes on `CalledProcessError` — should decode to str for readable error messages

## Low Priority

- [ ] **Incremental hashing for large files**: Full-file SHA-256 (C2 fix) is correct but slow for multi-GB videos; consider chunked early-exit comparison (byte-by-byte divergence detection) as a performance optimization
- [ ] **Phantom file warnings**: Edited versions (`IMG_E*.JPG`) appear in individual file list after originals moved as LP pairs; cosmetic but noisy in logs

## Archive

- [x] **Merge safety audit** — Fixed 8 data-integrity issues (C1-C4, H1-H2, M1, L1) for safe aggregative merges of overlapping photo streams; v2.1.0 (2026-02-07)
- [x] **EXIF date format mismatch** — Broadened `parse_iso8601_datetime()` regex to accept both ISO 8601 and raw EXIF date formats (2026-02-07)
- [x] **Architecture refactor** — Extracted timestamps, constants, livephoto, progress, stats modules; reduced duplication by ~186 lines (2025)
