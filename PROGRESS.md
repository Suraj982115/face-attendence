# Project Progress

## Overview

A face-recognition based student attendance system. Students are enrolled with a photo, face encodings are stored, and a live camera feed auto-marks attendance when a recognized face is detected. Built with Flask + SQLite, using YOLOv8 for face detection and `face_recognition` for face matching.

## Status: In Development

- Git: single initial commit on `main`, with staged and unstaged working-tree changes not yet committed.
- Working system with enrolled student data, login accounts, and live recognition in place.

## What Works

- **Authentication** – Role-based login/logout (admin / student) with SHA-256 password hashing (`app.py`).
- **Student management** – Admin can add, edit, and remove students via the web UI. Enrollment detects a face, saves the photo, creates the DB record + student login, and updates `known_faces.pkl`.
- **Live face recognition** – `/video_feed` streams webcam frames; YOLOv8 detects faces, `face_recognition` matches them, known faces are auto-marked present (once per day), unknowns are logged (`app.py`, `face_utils.py`).
- **Attendance recording** – `mark_attendance()` inserts a record per student per day, preventing duplicates (`backend.py`).
- **Reports** – Monthly attendance register grid (students x days with daily totals) for admins, and a personal dashboard with monthly percentage + register for students (`backend.py`, `templates/attendance_register.html`, `templates/student_dashboard.html`).
- **Dataset tooling** – CLI utilities to add/remove students and photos under `dataset/` (`manage_dataset.py`).
- **Bootstrap script** – `create_first_users.py` seeds the admin account.

## Database (attendance.db)

Schema: `students`, `attendance`, `users` (foreign keys enforced).

Current data:
- 1 student enrolled: suraj bohara (roll 001), photo at `static/photos/009.jpg`
- 2 users: `admin` / `admin123`, and `009` / `student123` (linked to the student)
- 0 attendance records yet (recording starts on first live recognition)

## Tech Stack

- Python + Flask, SQLite
- YOLOv8 face detection (Ultralytics) – `models/yolov8n-face.pt`
- `face_recognition` + OpenCV
- HTML/Jinja2 templates in `templates/`

## Key Files

| File | Purpose |
|------|---------|
| `app.py` | Flask routes: auth, dashboards, live feed, register view |
| `backend.py` | Business logic: enrollment, updates, removal, attendance, reports |
| `database.py` | SQLite schema + connection helpers |
| `face_utils.py` | Face encoding build/load/match, `known_faces.pkl` |
| `manage_dataset.py` | Dataset folder management |
| `create_first_users.py` | One-time user seeding |
| `live_test.py` | Standalone live recognition test |

## Recent Work

- Refactored `app.py`, `backend.py`, `face_utils.py` into cleaner role-separated modules.
- Added admin attendance register page with monthly grid and per-day totals.
- Reworked the student dashboard with a monthly register and attendance percentage.
- Added student `009` photo and rebuilt `known_faces.pkl`.

## Next Steps (Suggested)

- Commit the pending staged/unstaged changes.
- Run live test to verify recognition + auto-attendance end-to-end.
- Add marking options (absent, late, manual entry) and an admin analytics view.
- Improve face matching threshold tuning and multi-photo enrollment per student.
- Replace the hardcoded Flask secret key and default passwords with env-based config.
