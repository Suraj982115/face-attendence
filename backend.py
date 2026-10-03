# backend.py - Admin and attendance operations tying together database, face, and dataset modules

import calendar            # for month-range calculations in attendance register
import hashlib             # for SHA-256 password hashing
import os                  # for file and path operations
import pickle              # for serialising face encodings to disk
import shutil              # for copying photo files
import sqlite3             # for detecting UNIQUE constraint violations
from datetime import datetime  # for current date/time

import face_recognition    # for face detection and encoding

from database import get_connection  # DB connection helper
from face_utils import KNOWN_FACES_FILE, build_known_faces, load_known_faces  # face data helpers

STATIC_PHOTOS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "photos")  # directory for student photos


class RollNumberTakenError(Exception):
    def __init__(self, roll_number):
        super().__init__(f"Roll number '{roll_number}' is already used as another student's login username. Please choose a different roll number.")
        self.roll_number = roll_number  # remember the conflicting roll number


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()  # return SHA-256 hex digest


def enroll_student(name, roll_number, source_photo_path):
    if not os.path.isfile(source_photo_path):       # source photo does not exist
        print(f"Source photo '{source_photo_path}' not found.")
        return None

    try:
        os.makedirs(STATIC_PHOTOS_DIR, exist_ok=True)   # ensure photos directory exists
        ext = os.path.splitext(source_photo_path)[1]    # get file extension
        dest = os.path.join(STATIC_PHOTOS_DIR, f"{roll_number}{ext}")  # destination path
        shutil.copy2(source_photo_path, dest)           # copy photo to static directory
    except OSError as e:
        print(f"Error saving photo: {e}")
        return None

    try:
        image = face_recognition.load_image_file(dest)  # load copied photo
        face_encs = face_recognition.face_encodings(image)  # compute face encodings
    except Exception as e:
        print(f"Error processing photo for face detection: {e}")
        if os.path.isfile(dest):
            os.remove(dest)                             # clean up copied photo
        return None

    if not face_encs:                                   # no face detected in photo
        if os.path.isfile(dest):
            os.remove(dest)                             # clean up copied photo
        print("Error: No face detected in the photo. Enrolment cancelled.")
        return None

    conn = None
    try:
        conn = get_connection()                         # open DB connection
        cursor = conn.cursor()                          # create cursor
        cursor.execute(
            "INSERT INTO students (name, roll_number, photo_path) VALUES (?, ?, ?)",
            (name, roll_number, dest),                  # insert student record
        )
        conn.commit()                                   # commit transaction
        student_id = cursor.lastrowid                   # get auto-generated student ID

        username = roll_number                          # use roll number as username
        password = hash_password("student123")          # default password for all students
        try:
            cursor.execute(
                "INSERT INTO users (username, password, role, student_id) VALUES (?, ?, ?, ?)",
                (username, password, "student", student_id),  # create student user account
            )
            conn.commit()                               # commit user creation
            print(f"Created login for '{name}' (username: {username}, password: student123)")
        except Exception:
            print(f"Username '{username}' already exists, skipping user creation.")
    except Exception as e:
        print(f"Error inserting student into database: {e}")
        if os.path.isfile(dest):
            os.remove(dest)                             # clean up on failure
        return None
    finally:
        if conn:
            conn.close()                                # close connection

    try:
        encodings, names = load_known_faces()           # load existing face encodings
        encodings.append(face_encs[0])                  # append new encoding
        names.append(name)                              # append student name
        with open(KNOWN_FACES_FILE, "wb") as f:
            pickle.dump((encodings, names), f)          # save updated encodings to disk
    except Exception as e:
        print(f"Error saving face encoding: {e}")
        conn = None
        try:
            conn = get_connection()                     # rollback on encoding failure
            conn.execute("DELETE FROM students WHERE id = ?", (student_id,))
            conn.commit()
        except Exception:
            pass
        finally:
            if conn:
                conn.close()
        return None

    print(f"Enrolled '{name}' (id={student_id}).")
    return student_id                                   # return new student ID


def remove_student_by_id(student_id):
    conn = None
    try:
        conn = get_connection()                         # open DB connection
        cursor = conn.cursor()                          # create cursor
        cursor.execute("SELECT photo_path FROM students WHERE id = ?", (student_id,))  # fetch photo path
        row = cursor.fetchone()                         # fetch row
        if not row:                                     # student not found
            print(f"Student id {student_id} not found.")
            return False

        photo_path = row[0]                             # save photo path before deleting
        cursor.execute("DELETE FROM users WHERE student_id = ?", (student_id,))  # delete user account
        cursor.execute("DELETE FROM attendance WHERE student_id = ?", (student_id,))  # delete attendance records
        cursor.execute("DELETE FROM students WHERE id = ?", (student_id,))  # delete student record
        conn.commit()                                   # commit all deletions
    except Exception as e:
        print(f"Error deleting student from database: {e}")
        return False
    finally:
        if conn:
            conn.close()                                # close connection

    if photo_path and os.path.isfile(photo_path):
        try:
            os.remove(photo_path)                       # delete photo from disk
        except OSError as e:
            print(f"Warning: Could not delete photo '{photo_path}': {e}")

    try:
        build_known_faces()                             # rebuild face encodings from dataset
    except Exception as e:
        print(f"Warning: Could not rebuild face encodings: {e}")

    print(f"Removed student id {student_id}.")
    return True


def update_student(student_id, name=None, roll_number=None, source_photo_path=None):
    conn = None
    try:
        conn = get_connection()                         # open DB connection
        cursor = conn.cursor()                          # create cursor
        cursor.execute("SELECT name, roll_number, photo_path FROM students WHERE id = ?", (student_id,))  # fetch current data
        row = cursor.fetchone()                         # fetch row
        if not row:                                     # student not found
            print(f"Student id {student_id} not found.")
            return False

        old_name, old_roll, old_photo = row             # save old values
        new_name = name if name else old_name           # keep old name if not provided
        new_roll = roll_number if roll_number else old_roll  # keep old roll if not provided
        new_photo_path = old_photo                      # default: keep old photo
    except Exception as e:
        print(f"Error reading student data: {e}")
        return False
    finally:
        if conn:
            conn.close()                                # close connection

    if source_photo_path and os.path.isfile(source_photo_path):  # a new photo was provided
        if old_photo and os.path.isfile(old_photo):
            try:
                os.remove(old_photo)                    # delete old photo file
            except OSError as e:
                print(f"Warning: Could not delete old photo: {e}")

        try:
            ext = os.path.splitext(source_photo_path)[1]  # get extension
            dest = os.path.join(STATIC_PHOTOS_DIR, f"{new_roll}{ext}")  # build destination path
            shutil.copy2(source_photo_path, dest)       # copy new photo
            new_photo_path = dest                       # update photo path

            image = face_recognition.load_image_file(dest)  # load new photo
            face_encs = face_recognition.face_encodings(image)  # compute face encodings
            if not face_encs:                           # no face detected
                os.remove(dest)                         # clean up
                print("Error: No face detected in the new photo. Update cancelled.")
                return False
        except Exception as e:
            print(f"Error processing new photo: {e}")
            return False

        try:
            encodings, names = load_known_faces()       # load existing encodings
            indices_to_keep = [i for i, n in enumerate(names) if n != old_name]  # remove old name entries
            encodings = [encodings[i] for i in indices_to_keep]
            names = [names[i] for i in indices_to_keep]
            encodings.append(face_encs[0])              # add new encoding
            names.append(new_name)                      # add (possibly updated) name
            with open(KNOWN_FACES_FILE, "wb") as f:
                pickle.dump((encodings, names), f)      # save to disk
        except Exception as e:
            print(f"Error updating face encodings: {e}")
            return False

    else:                                               # no new photo – only name may have changed
        if new_name != old_name:                        # name was updated without a new photo
            try:
                encodings, names = load_known_faces()   # load existing encodings
                indices_to_keep = [i for i, n in enumerate(names) if n != old_name]  # remove old name
                encodings = [encodings[i] for i in indices_to_keep]
                names = [names[i] for i in indices_to_keep]

                if old_photo and os.path.isfile(old_photo):
                    image = face_recognition.load_image_file(old_photo)  # re-encode from old photo
                    face_encs = face_recognition.face_encodings(image)
                    if face_encs:
                        encodings.append(face_encs[0])  # add encoding under new name
                        names.append(new_name)
                with open(KNOWN_FACES_FILE, "wb") as f:
                    pickle.dump((encodings, names), f)  # save updated encodings
            except Exception as e:
                print(f"Error updating face encodings for name change: {e}")
                return False

    conn = None
    try:
        conn = get_connection()                         # open DB connection
        cursor = conn.cursor()                          # create cursor
        cursor.execute(
            "UPDATE students SET name = ?, roll_number = ?, photo_path = ? WHERE id = ?",
            (new_name, new_roll, new_photo_path, student_id),  # update student record
        )
        if new_roll != old_roll:                        # roll number changed - keep the login in sync
            cursor.execute(
                "UPDATE users SET username = ? WHERE student_id = ? AND role = 'student'",
                (new_roll, student_id),                 # username tracks the roll number
            )
            if cursor.rowcount == 0:                    # no student login row linked to this student
                print(f"No student login linked to id {student_id}; username left unchanged.")
        conn.commit()                                   # commit update
    except sqlite3.IntegrityError:
        conn.rollback()                                 # discard changes so nothing is half-saved
        print(f"Roll number '{new_roll}' is already used as a login username.")
        raise RollNumberTakenError(new_roll)            # let the caller show an accurate message
    except Exception as e:
        conn.rollback()                                 # discard changes on any other failure
        print(f"Error updating student in database: {e}")
        return False
    finally:
        if conn:
            conn.close()                                # close connection

    print(f"Updated student id {student_id}.")
    return True


def mark_attendance(student_id, status="present"):
    today = datetime.now().strftime("%Y-%m-%d")         # today's date string
    now_time = datetime.now().strftime("%H:%M:%S")      # current time string

    conn = None
    try:
        conn = get_connection()                         # open DB connection
        cursor = conn.cursor()                          # create cursor
        cursor.execute(
            "SELECT id FROM attendance WHERE student_id = ? AND date = ?",
            (student_id, today),                        # check if already marked today
        )
        if cursor.fetchone():                           # already marked today
            print(f"Student id {student_id} already marked present/absent today.")
            return False

        cursor.execute(
            "INSERT INTO attendance (student_id, date, time, status) VALUES (?, ?, ?, ?)",
            (student_id, today, now_time, status),      # insert attendance record
        )
        conn.commit()                                   # commit insertion
        print(f"Attendance marked for student id {student_id}: {status}.")
        return True
    except Exception as e:
        print(f"Error marking attendance: {e}")
        return False
    finally:
        if conn:
            conn.close()                                # close connection


def get_monthly_percentage(student_id, year, month):
    month_str = f"{year}-{month:02d}-%"                 # SQL LIKE pattern for the month
    conn = None
    try:
        conn = get_connection()                         # open DB connection
        cursor = conn.cursor()                          # create cursor
        cursor.execute(
            "SELECT status FROM attendance WHERE student_id = ? AND date LIKE ?",
            (student_id, month_str),                    # fetch all attendance records for month
        )
        rows = cursor.fetchall()                        # fetch all rows
    except Exception as e:
        print(f"Error querying attendance: {e}")
        return 0.0
    finally:
        if conn:
            conn.close()                                # close connection

    if not rows:                                        # no records for this month
        return 0.0

    present_count = sum(1 for r in rows if r[0] == "present")  # count present records
    return round(present_count / len(rows) * 100, 2)    # calculate percentage


def get_attendance_register(year, month):
    days_in_month = calendar.monthrange(year, month)[1]  # number of days in month
    month_prefix = f"{year}-{month:02d}-%"              # SQL LIKE pattern for the month

    conn = None
    try:
        conn = get_connection()                         # open DB connection
        cursor = conn.cursor()                          # create cursor

        cursor.execute("SELECT id, name, roll_number FROM students ORDER BY id")  # fetch all students
        students = cursor.fetchall()                    # fetch rows

        cursor.execute(
            "SELECT student_id, date FROM attendance WHERE date LIKE ? AND status = 'present'",
            (month_prefix,),                            # fetch all present records for the month
        )
        rows = cursor.fetchall()                        # fetch rows
    except Exception as e:
        print(f"Error fetching attendance register: {e}")
        return [], [], []
    finally:
        if conn:
            conn.close()                                # close connection

    register = {}                                       # nested dict: sid -> {name, roll, days: {day: 0/1}}
    for sid, name, roll in students:
        register[sid] = {"name": name, "roll_number": roll, "days": {d: 0 for d in range(1, days_in_month + 1)}}

    for sid, date_str in rows:                          # populate present days
        day = int(date_str.split("-")[2])               # extract day from date string
        if sid in register:
            register[sid]["days"][day] = 1              # mark as present

    student_list = []                                   # build list of student summaries
    for sid in register:
        student_list.append({
            "id": sid,
            "name": register[sid]["name"],
            "roll_number": register[sid]["roll_number"],
        })

    day_totals = {d: 0 for d in range(1, days_in_month + 1)}  # initialise totals per day
    for sid in register:
        for d in range(1, days_in_month + 1):
            day_totals[d] += register[sid]["days"][d]   # sum present count per day

    grid = []                                           # 2D grid: rows=students, cols=days
    for sid in register:
        row = [register[sid]["days"][d] for d in range(1, days_in_month + 1)]
        grid.append(row)

    return student_list, grid, day_totals               # return register data

# ============================================================
# Role of the full code (backend.py):
#   This module contains all the core business logic for the student attendance
#   system. It provides functions for:
#   - Enrolling new students (saving photo, detecting face, creating DB record + user account)
#   - Removing students (cascading deletes from all tables, cleaning up photo + encodings)
#   - Updating student info (name, roll number, photo, with face encoding management)
#   - Marking attendance for a student on a given day (avoiding duplicates)
#   - Calculating monthly attendance percentages
#   - Building a full attendance register grid (students × days) with per-day totals
#   It acts as an intermediary between the Flask routes (app.py) and the
#   database (database.py) and face utilities (face_utils.py).
