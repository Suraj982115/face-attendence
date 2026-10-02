# app.py - Flask web application for the student attendance system

import calendar
import hashlib
import os
import tempfile
from functools import wraps

from datetime import datetime

import cv2
import face_recognition

from flask import Flask, Response, jsonify, redirect, render_template, request, session, url_for

from backend import enroll_student, get_attendance_register, get_monthly_percentage, mark_attendance, remove_student_by_id, update_student
from database import create_tables, get_connection
from face_utils import load_known_faces, match_face

app = Flask(__name__)
app.secret_key = "replace-this-with-a-real-secret-key"

YOLO_MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "yolov8n-face.pt")
yolo_model = None

detection_log = []
detection_set = set()
detection_lock = False


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def login_required(role):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if "user_id" not in session:
                return redirect(url_for("login"))
            if session.get("role") != role:
                return redirect(url_for("login"))
            return f(*args, **kwargs)
        return wrapper
    return decorator


@app.route("/")
def index():
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, role, student_id FROM users WHERE username = ? AND password = ?",
                (username, hash_password(password)),
            )
            user = cursor.fetchone()
            conn.close()
        except Exception as e:
            return render_template("login.html", error="Database error. Please try again later.")

        if user:
            session["user_id"] = user[0]
            session["role"] = user[1]
            session["student_id"] = user[2]
            if user[1] == "admin":
                return redirect(url_for("admin"))
            return redirect(url_for("student"))

        return render_template("login.html", error="Invalid username or password")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/admin")
@login_required("admin")
def admin():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, roll_number, photo_path FROM students ORDER BY id")
        students = cursor.fetchall()
        conn.close()
    except Exception as e:
        return render_template("admin_dashboard.html", students=[], error="Database error loading students.")

    student_list = []
    for s in students:
        photo_url = None
        if s[3] and os.path.isfile(s[3]):
            photo_url = "/" + s[3].replace("\\", "/")
            static_idx = photo_url.find("/static/")
            if static_idx != -1:
                photo_url = photo_url[static_idx:]
        student_list.append({"id": s[0], "name": s[1], "roll_number": s[2], "photo_url": photo_url})

    return render_template("admin_dashboard.html", students=student_list)


@app.route("/admin/add", methods=["GET", "POST"])
@login_required("admin")
def admin_add():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        roll_number = request.form.get("roll_number", "").strip()
        photo = request.files.get("photo")

        if not name or not roll_number or not photo or photo.filename == "":
            return render_template("admin_add.html", error="All fields are required.")

        tmp = None
        try:
            ext = os.path.splitext(photo.filename)[1]
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
            photo.save(tmp.name)
            tmp.close()

            student_id = enroll_student(name, roll_number, tmp.name)
        except Exception as e:
            return render_template("admin_add.html", error=f"Error enrolling student: {e}")
        finally:
            if tmp and os.path.isfile(tmp.name):
                os.unlink(tmp.name)

        if student_id:
            return redirect(url_for("admin"))

        return render_template("admin_add.html", error="No face detected in photo. Try a different image.")

    return render_template("admin_add.html")


@app.route("/admin/edit/<int:student_id>", methods=["GET", "POST"])
@login_required("admin")
def admin_edit(student_id):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, roll_number, photo_path FROM students WHERE id = ?", (student_id,))
        student = cursor.fetchone()
        conn.close()
    except Exception as e:
        return redirect(url_for("admin"))

    if not student:
        return redirect(url_for("admin"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        roll_number = request.form.get("roll_number", "").strip()
        photo = request.files.get("photo")

        if not name or not roll_number:
            return render_template("admin_edit.html", student=student, error="Name and roll number are required.")

        source_photo_path = None
        tmp = None
        try:
            if photo and photo.filename:
                ext = os.path.splitext(photo.filename)[1]
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
                photo.save(tmp.name)
                tmp.close()
                source_photo_path = tmp.name

            result = update_student(student_id, name=name, roll_number=roll_number, source_photo_path=source_photo_path)
        except Exception as e:
            return render_template("admin_edit.html", student=student, error=f"Error updating student: {e}")
        finally:
            if tmp and os.path.isfile(tmp.name):
                os.unlink(tmp.name)

        if result:
            return redirect(url_for("admin"))

        return render_template("admin_edit.html", student=student, error="No face detected in the new photo. Try a different image.")

    return render_template("admin_edit.html", student=student)


@app.route("/admin/remove/<int:student_id>", methods=["POST"])
@login_required("admin")
def admin_remove(student_id):
    remove_student_by_id(student_id)
    return redirect(url_for("admin"))


@app.route("/admin/attendance-register")
@login_required("admin")
def attendance_register():
    now = datetime.now()
    view_year = request.args.get("year", now.year, type=int)
    view_month = request.args.get("month", now.month, type=int)

    if view_month < 1 or view_month > 12:
        view_month = now.month
    if view_year < 2000 or view_year > 2100:
        view_year = now.year

    days_in_month = calendar.monthrange(view_year, view_month)[1]

    students, grid, day_totals = get_attendance_register(view_year, view_month)

    return render_template(
        "attendance_register.html",
        students=students,
        grid=grid,
        day_totals=day_totals,
        days_in_month=days_in_month,
        view_year=view_year,
        view_month=view_month,
        now=now,
    )


@app.route("/student")
@login_required("student")
def student():
    student_id = session.get("student_id")

    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, roll_number, photo_path FROM students WHERE id = ?", (student_id,))
        info = cursor.fetchone()
        conn.close()
    except Exception as e:
        return render_template("login.html", error="Database error. Please log in again.")

    if not info:
        return redirect(url_for("login"))

    photo_url = None
    if info[3] and os.path.isfile(info[3]):
        photo_url = "/" + info[3].replace("\\", "/")
        static_idx = photo_url.find("/static/")
        if static_idx != -1:
            photo_url = photo_url[static_idx:]

    now = datetime.now()
    view_year = request.args.get("year", now.year, type=int)
    view_month = request.args.get("month", now.month, type=int)

    if view_month < 1 or view_month > 12:
        view_month = now.month
    if view_year < 2000 or view_year > 2100:
        view_year = now.year

    percentage = get_monthly_percentage(student_id, view_year, view_month)

    month_str = f"{view_year}-{view_month:02d}-%"
    records = []
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT date, time, status FROM attendance WHERE student_id = ? AND date LIKE ? ORDER BY date",
            (student_id, month_str),
        )
        records = cursor.fetchall()
        conn.close()
    except Exception as e:
        pass

    days_in_month = calendar.monthrange(view_year, view_month)[1]
    student_register = [0] * days_in_month
    for rec in records:
        day = int(rec[0].split("-")[2])
        if 1 <= day <= days_in_month and rec[2] == "present":
            student_register[day - 1] = 1

    return render_template(
        "student_dashboard.html",
        student={"id": info[0], "name": info[1], "roll_number": info[2], "photo_url": photo_url},
        percentage=percentage,
        records=records,
        view_year=view_year,
        view_month=view_month,
        now=now,
        register=student_register,
        days_in_month=days_in_month,
    )


@app.route("/admin/live")
@login_required("admin")
def admin_live():
    return render_template("live_dashboard.html")


@app.route("/live_status")
@login_required("admin")
def live_status():
    return jsonify(detection_log)


@app.route("/video_feed")
@login_required("admin")
def video_feed():
    global yolo_model, detection_log, detection_set, detection_lock

    if yolo_model is None:
        try:
            from ultralytics import YOLO
            yolo_model = YOLO(YOLO_MODEL_PATH)
        except Exception as e:
            def error_frame():
                yield b""
            return Response(error_frame(), mimetype="multipart/x-mixed-replace; boundary=frame")

    known_encodings, known_names = load_known_faces()

    name_to_id = {}
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name FROM students")
        for row in cursor.fetchall():
            name_to_id[row[1]] = row[0]
    except Exception as e:
        pass
    finally:
        if conn:
            conn.close()

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        def error_frame():
            yield b""
        return Response(error_frame(), mimetype="multipart/x-mixed-replace; boundary=frame")

    def generate():
        global detection_log, detection_set, detection_lock

        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                results = yolo_model(frame, verbose=False)

                for box in results[0].boxes:
                    x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                    face_crop = frame[y1:y2, x1:x2]
                    if face_crop.size == 0:
                        continue

                    rgb_crop = cv2.cvtColor(face_crop, cv2.COLOR_BGR2RGB)
                    encs = face_recognition.face_encodings(rgb_crop)

                    name = "Unknown"
                    color = (0, 0, 255)

                    if encs:
                        matched = match_face(encs[0], known_encodings, known_names)
                        if matched:
                            name = matched
                            color = (0, 255, 0)

                            if not detection_lock:
                                detection_lock = True
                                try:
                                    if name not in detection_set:
                                        sid = name_to_id.get(name)
                                        if sid:
                                            marked = mark_attendance(sid)
                                            detection_log.append({
                                                "name": name,
                                                "marked": marked,
                                            })
                                        else:
                                            detection_log.append({
                                                "name": name,
                                                "marked": False,
                                            })
                                        detection_set.add(name)
                                finally:
                                    detection_lock = False
                        else:
                            if not detection_lock:
                                detection_lock = True
                                try:
                                    if f"unknown_{x1}_{y1}" not in detection_set:
                                        detection_log.append({
                                            "name": "Unknown",
                                            "marked": False,
                                        })
                                        detection_set.add(f"unknown_{x1}_{y1}")
                                finally:
                                    detection_lock = False

                    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                    cv2.putText(frame, name, (x1, y1 - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

                _, jpeg = cv2.imencode(".jpg", frame)
                yield (b"--frame\r\n"
                       b"Content-Type: image/jpeg\r\n\r\n" + jpeg.tobytes() + b"\r\n")
        finally:
            cap.release()

    return Response(generate(), mimetype="multipart/x-mixed-replace; boundary=frame")


if __name__ == "__main__":
    create_tables()
    app.run(debug=True)
