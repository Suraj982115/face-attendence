# app.py - Flask web application for the student attendance system

import calendar          # for getting days in a month
import hashlib           # for SHA-256 password hashing
import os                # for file path operations
import tempfile          # for creating temporary files for uploaded photos
from functools import wraps  # for preserving decorator metadata

from datetime import datetime  # for current date/time

import cv2               # for camera capture and drawing
import face_recognition  # for face encoding on cropped faces

from flask import Flask, Response, jsonify, redirect, render_template, request, session, url_for  # web framework imports

from backend import RollNumberTakenError, enroll_student, get_attendance_register, get_monthly_percentage, mark_attendance, remove_student_by_id, update_student  # backend operations
from database import create_tables, get_connection  # database helpers
from face_utils import load_known_faces, match_face  # face recognition helpers

app = Flask(__name__)  # create Flask application instance
app.secret_key = "replace-this-with-a-real-secret-key"  # session signing key

YOLO_MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "yolov8n-face.pt")  # path to YOLOv8 face detection model
yolo_model = None  # lazily loaded YOLO model (global singleton)

detection_log = []   # list of detection events for the live status endpoint
detection_set = set()  # set of already-detected names/IDs to avoid duplicate marks
detection_lock = False  # simple mutex to serialise detection processing


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()  # return SHA-256 hex digest of the password


def login_required(role):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if "user_id" not in session:          # user is not logged in at all
                return redirect(url_for("login"))
            if session.get("role") != role:        # user lacks the required role
                return redirect(url_for("login"))
            return f(*args, **kwargs)              # authorised – call the original view
        return wrapper
    return decorator


@app.route("/")
def index():
    return redirect(url_for("login"))  # root redirects to login page


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":                  # form submitted
        username = request.form.get("username", "").strip()  # read username from form
        password = request.form.get("password", "")          # read password from form

        try:
            conn = get_connection()                           # open DB connection
            cursor = conn.cursor()                            # create cursor
            cursor.execute(
                "SELECT id, role, student_id FROM users WHERE username = ? AND password = ?",
                (username, hash_password(password)),          # query user by credentials
            )
            user = cursor.fetchone()                          # fetch matching user row
            conn.close()                                      # close connection
        except Exception as e:
            return render_template("login.html", error="Database error. Please try again later.")

        if user:                                              # credentials matched
            session["user_id"] = user[0]                      # store user ID in session
            session["role"] = user[1]                         # store role in session
            session["student_id"] = user[2]                   # store student_id in session
            if user[1] == "admin":                            # redirect admin
                return redirect(url_for("admin"))
            return redirect(url_for("student"))               # redirect student

        return render_template("login.html", error="Invalid username or password")  # login failed

    return render_template("login.html")                      # GET request – show login form


@app.route("/logout")
def logout():
    session.clear()        # clear session data
    return redirect(url_for("login"))  # redirect to login


@app.route("/admin")
@login_required("admin")
def admin():
    try:
        conn = get_connection()                                 # open DB connection
        cursor = conn.cursor()                                  # create cursor
        cursor.execute("SELECT id, name, roll_number, photo_path FROM students ORDER BY id")  # fetch all students
        students = cursor.fetchall()                            # fetch all rows
        conn.close()                                            # close connection
    except Exception as e:
        return render_template("admin_dashboard.html", students=[], error="Database error loading students.")

    student_list = []                                           # build list of student dicts
    for s in students:
        photo_url = None                                        # default: no photo
        if s[3] and os.path.isfile(s[3]):                       # photo file exists on disk
            photo_url = "/" + s[3].replace("\\", "/")           # convert path to URL
            static_idx = photo_url.find("/static/")             # find /static/ prefix
            if static_idx != -1:
                photo_url = photo_url[static_idx:]              # strip everything before /static/
        student_list.append({"id": s[0], "name": s[1], "roll_number": s[2], "photo_url": photo_url})  # add student dict

    return render_template("admin_dashboard.html", students=student_list)  # render admin dashboard


@app.route("/admin/add", methods=["GET", "POST"])
@login_required("admin")
def admin_add():
    if request.method == "POST":                               # form submitted
        name = request.form.get("name", "").strip()            # read student name
        roll_number = request.form.get("roll_number", "").strip()  # read roll number
        photo = request.files.get("photo")                     # read uploaded photo file

        if not name or not roll_number or not photo or photo.filename == "":  # validate required fields
            return render_template("admin_add.html", error="All fields are required.")

        tmp = None
        try:
            ext = os.path.splitext(photo.filename)[1]          # get file extension
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=ext)  # create temp file
            photo.save(tmp.name)                               # save uploaded photo to temp file
            tmp.close()                                        # close temp file handle

            student_id = enroll_student(name, roll_number, tmp.name)  # enroll the student
        except Exception as e:
            return render_template("admin_add.html", error=f"Error enrolling student: {e}")
        finally:
            if tmp and os.path.isfile(tmp.name):
                os.unlink(tmp.name)                            # clean up temp file

        if student_id:                                         # enrollment succeeded
            return redirect(url_for("admin"))

        return render_template("admin_add.html", error="No face detected in photo. Try a different image.")

    return render_template("admin_add.html")                   # GET request – show add form


@app.route("/admin/edit/<int:student_id>", methods=["GET", "POST"])
@login_required("admin")
def admin_edit(student_id):
    try:
        conn = get_connection()                                # open DB connection
        cursor = conn.cursor()                                 # create cursor
        cursor.execute("SELECT id, name, roll_number, photo_path FROM students WHERE id = ?", (student_id,))  # fetch student by ID
        student = cursor.fetchone()                            # fetch row
        conn.close()                                           # close connection
    except Exception as e:
        return redirect(url_for("admin"))

    if not student:                                            # student not found
        return redirect(url_for("admin"))

    if request.method == "POST":                               # form submitted
        name = request.form.get("name", "").strip()            # read new name
        roll_number = request.form.get("roll_number", "").strip()  # read new roll number
        photo = request.files.get("photo")                     # read optional new photo

        if not name or not roll_number:
            return render_template("admin_edit.html", student=student, error="Name and roll number are required.")

        source_photo_path = None
        tmp = None
        try:
            if photo and photo.filename:                       # a new photo was uploaded
                ext = os.path.splitext(photo.filename)[1]      # get file extension
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=ext)  # create temp file
                photo.save(tmp.name)                           # save uploaded photo
                tmp.close()                                    # close temp file
                source_photo_path = tmp.name                   # set source path for backend

            result = update_student(student_id, name=name, roll_number=roll_number, source_photo_path=source_photo_path)  # update student
        except RollNumberTakenError as e:
            return render_template("admin_edit.html", student=student, error=str(e))
        except Exception as e:
            return render_template("admin_edit.html", student=student, error=f"Error updating student: {e}")
        finally:
            if tmp and os.path.isfile(tmp.name):
                os.unlink(tmp.name)                            # clean up temp file

        if result:                                             # update succeeded
            return redirect(url_for("admin"))

        return render_template("admin_edit.html", student=student, error="No face detected in the new photo. Try a different image.")

    return render_template("admin_edit.html", student=student)  # GET request – show edit form


@app.route("/admin/remove/<int:student_id>", methods=["POST"])
@login_required("admin")
def admin_remove(student_id):
    remove_student_by_id(student_id)  # remove student from DB and face data
    return redirect(url_for("admin"))  # redirect back to admin dashboard


@app.route("/admin/attendance-register")
@login_required("admin")
def attendance_register():
    now = datetime.now()                                   # current date/time
    view_year = request.args.get("year", now.year, type=int)   # year from query string (default current)
    view_month = request.args.get("month", now.month, type=int)  # month from query string (default current)

    if view_month < 1 or view_month > 12:                  # clamp invalid month
        view_month = now.month
    if view_year < 2000 or view_year > 2100:               # clamp invalid year
        view_year = now.year

    days_in_month = calendar.monthrange(view_year, view_month)[1]  # number of days in selected month

    students, grid, day_totals = get_attendance_register(view_year, view_month)  # fetch register data

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
    student_id = session.get("student_id")                 # get student_id from session

    try:
        conn = get_connection()                            # open DB connection
        cursor = conn.cursor()                             # create cursor
        cursor.execute("SELECT id, name, roll_number, photo_path FROM students WHERE id = ?", (student_id,))  # fetch student info
        info = cursor.fetchone()                           # fetch row
        conn.close()                                       # close connection
    except Exception as e:
        return render_template("login.html", error="Database error. Please log in again.")

    if not info:                                           # student not found
        return redirect(url_for("login"))

    photo_url = None
    if info[3] and os.path.isfile(info[3]):                # photo file exists
        photo_url = "/" + info[3].replace("\\", "/")       # convert to URL
        static_idx = photo_url.find("/static/")
        if static_idx != -1:
            photo_url = photo_url[static_idx:]             # keep only /static/... portion

    now = datetime.now()                                   # current date/time
    view_year = request.args.get("year", now.year, type=int)   # year from query string
    view_month = request.args.get("month", now.month, type=int)  # month from query string

    if view_month < 1 or view_month > 12:
        view_month = now.month
    if view_year < 2000 or view_year > 2100:
        view_year = now.year

    percentage = get_monthly_percentage(student_id, view_year, view_month)  # calculate attendance %

    month_str = f"{view_year}-{view_month:02d}-%"        # SQL LIKE pattern for the month
    records = []
    try:
        conn = get_connection()                            # open DB connection
        cursor = conn.cursor()                             # create cursor
        cursor.execute(
            "SELECT date, time, status FROM attendance WHERE student_id = ? AND date LIKE ? ORDER BY date",
            (student_id, month_str),                       # fetch attendance records for month
        )
        records = cursor.fetchall()                        # fetch all rows
        conn.close()                                       # close connection
    except Exception as e:
        pass

    days_in_month = calendar.monthrange(view_year, view_month)[1]  # days in selected month
    student_register = [0] * days_in_month                 # initialise attendance register (0 = absent)
    for rec in records:
        day = int(rec[0].split("-")[2])                    # extract day from date string
        if 1 <= day <= days_in_month and rec[2] == "present":
            student_register[day - 1] = 1                  # mark as present (1)

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
    return render_template("live_dashboard.html")  # render the live monitoring page


@app.route("/live_status")
@login_required("admin")
def live_status():
    return jsonify(detection_log)  # return the current detection log as JSON


@app.route("/video_feed")
@login_required("admin")
def video_feed():
    global yolo_model, detection_log, detection_set, detection_lock  # access globals

    if yolo_model is None:                                     # model not loaded yet
        try:
            from ultralytics import YOLO
            yolo_model = YOLO(YOLO_MODEL_PATH)                # load YOLOv8 face detection model
        except Exception as e:
            def error_frame():                                 # return empty response on error
                yield b""
            return Response(error_frame(), mimetype="multipart/x-mixed-replace; boundary=frame")

    known_encodings, known_names = load_known_faces()          # load known face encodings

    name_to_id = {}                                            # map name -> student ID
    conn = None
    try:
        conn = get_connection()                                # open DB connection
        cursor = conn.cursor()                                 # create cursor
        cursor.execute("SELECT id, name FROM students")        # fetch all students
        for row in cursor.fetchall():
            name_to_id[row[1]] = row[0]                        # build name->id mapping
    except Exception as e:
        pass
    finally:
        if conn:
            conn.close()                                       # close connection

    cap = cv2.VideoCapture(0)                                  # open webcam (camera 0)
    if not cap.isOpened():
        def error_frame():
            yield b""
        return Response(error_frame(), mimetype="multipart/x-mixed-replace; boundary=frame")

    def generate():                                            # generator for MJPEG stream
        global detection_log, detection_set, detection_lock

        try:
            while True:                                        # infinite capture loop
                ret, frame = cap.read()                        # read frame from webcam
                if not ret:
                    break

                results = yolo_model(frame, verbose=False)     # run YOLO face detection

                for box in results[0].boxes:                   # iterate over detected faces
                    x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())  # get bounding box coordinates
                    face_crop = frame[y1:y2, x1:x2]            # crop face region
                    if face_crop.size == 0:
                        continue

                    rgb_crop = cv2.cvtColor(face_crop, cv2.COLOR_BGR2RGB)  # convert BGR -> RGB for face_recognition
                    encs = face_recognition.face_encodings(rgb_crop)  # compute face encodings

                    name = "Unknown"                           # default label
                    color = (0, 0, 255)                        # red for unknown

                    if encs:                                   # face encoding succeeded
                        matched = match_face(encs[0], known_encodings, known_names)  # try to match against known faces
                        if matched:
                            name = matched                     # set recognised name
                            color = (0, 255, 0)                # green for known

                            if not detection_lock:             # enter critical section
                                detection_lock = True
                                try:
                                    if name not in detection_set:  # not already detected this session
                                        sid = name_to_id.get(name)  # look up student ID
                                        if sid:
                                            marked = mark_attendance(sid)  # mark attendance
                                            detection_log.append({
                                                "name": name,
                                                "marked": marked,
                                            })
                                        else:
                                            detection_log.append({
                                                "name": name,
                                                "marked": False,
                                            })
                                        detection_set.add(name)  # add to set to avoid duplicates
                                finally:
                                    detection_lock = False     # release lock
                        else:
                            if not detection_lock:
                                detection_lock = True
                                try:
                                    if f"unknown_{x1}_{y1}" not in detection_set:  # unique unknown key
                                        detection_log.append({
                                            "name": "Unknown",
                                            "marked": False,
                                        })
                                        detection_set.add(f"unknown_{x1}_{y1}")  # track unknown occurrence
                                finally:
                                    detection_lock = False

                    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)  # draw bounding box
                    cv2.putText(frame, name, (x1, y1 - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)  # draw label

                _, jpeg = cv2.imencode(".jpg", frame)          # encode frame as JPEG
                yield (b"--frame\r\n"
                       b"Content-Type: image/jpeg\r\n\r\n" + jpeg.tobytes() + b"\r\n")  # yield MJPEG chunk
        finally:
            cap.release()                                      # release webcam on exit

    return Response(generate(), mimetype="multipart/x-mixed-replace; boundary=frame")  # return streaming response


if __name__ == "__main__":
    create_tables()    # ensure DB tables exist
    app.run(debug=True)  # start Flask development server

# ============================================================
# Role of the full code (app.py):
#   This is the Flask web application that serves as the main entry point for the
#   student attendance system. It provides routes for:
#   - Authentication (login/logout) with role-based access (admin/student)
#   - Admin dashboard: view, add, edit, remove students
#   - Attendance register: monthly grid view with per-day presence indicators
#   - Student dashboard: personal attendance percentage and monthly register
#   - Live face recognition: MJPEG video feed with YOLOv8 face detection +
#     face_recognition matching; auto-marks attendance for recognised faces
#   The file ties together the database layer (database.py), backend logic
#   (backend.py), and face utilities (face_utils.py).
