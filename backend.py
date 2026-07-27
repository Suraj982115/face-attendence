# backend.py - Admin and attendance operations tying together database, face, and dataset modules

import os
import pickle
import shutil
from datetime import datetime

import face_recognition

from database import get_connection
from face_utils import KNOWN_FACES_FILE, build_known_faces, load_known_faces

STATIC_PHOTOS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "photos")


def enroll_student(name, roll_number, source_photo_path):
    if not os.path.isfile(source_photo_path):
        print(f"Source photo '{source_photo_path}' not found.")
        return None

    try:
        os.makedirs(STATIC_PHOTOS_DIR, exist_ok=True)
        ext = os.path.splitext(source_photo_path)[1]
        dest = os.path.join(STATIC_PHOTOS_DIR, f"{roll_number}{ext}")
        shutil.copy2(source_photo_path, dest)
    except OSError as e:
        print(f"Error saving photo: {e}")
        return None

    try:
        image = face_recognition.load_image_file(dest)
        face_encs = face_recognition.face_encodings(image)
    except Exception as e:
        print(f"Error processing photo for face detection: {e}")
        if os.path.isfile(dest):
            os.remove(dest)
        return None

    if not face_encs:
        if os.path.isfile(dest):
            os.remove(dest)
        print("Error: No face detected in the photo. Enrolment cancelled.")
        return None

    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO students (name, roll_number, photo_path) VALUES (?, ?, ?)",
            (name, roll_number, dest),
        )
        conn.commit()
        student_id = cursor.lastrowid
    except Exception as e:
        print(f"Error inserting student into database: {e}")
        if os.path.isfile(dest):
            os.remove(dest)
        return None
    finally:
        if conn:
            conn.close()

    try:
        encodings, names = load_known_faces()
        encodings.append(face_encs[0])
        names.append(name)
        with open(KNOWN_FACES_FILE, "wb") as f:
            pickle.dump((encodings, names), f)
    except Exception as e:
        print(f"Error saving face encoding: {e}")
        conn = None
        try:
            conn = get_connection()
            conn.execute("DELETE FROM students WHERE id = ?", (student_id,))
            conn.commit()
        except Exception:
            pass
        finally:
            if conn:
                conn.close()
        return None

    print(f"Enrolled '{name}' (id={student_id}).")
    return student_id


def remove_student_by_id(student_id):
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT photo_path FROM students WHERE id = ?", (student_id,))
        row = cursor.fetchone()
        if not row:
            print(f"Student id {student_id} not found.")
            return False

        photo_path = row[0]
        cursor.execute("DELETE FROM students WHERE id = ?", (student_id,))
        conn.commit()
    except Exception as e:
        print(f"Error deleting student from database: {e}")
        return False
    finally:
        if conn:
            conn.close()

    if photo_path and os.path.isfile(photo_path):
        try:
            os.remove(photo_path)
        except OSError as e:
            print(f"Warning: Could not delete photo '{photo_path}': {e}")

    try:
        build_known_faces()
    except Exception as e:
        print(f"Warning: Could not rebuild face encodings: {e}")

    print(f"Removed student id {student_id}.")
    return True


def update_student(student_id, name=None, roll_number=None, source_photo_path=None):
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name, roll_number, photo_path FROM students WHERE id = ?", (student_id,))
        row = cursor.fetchone()
        if not row:
            print(f"Student id {student_id} not found.")
            return False

        old_name, old_roll, old_photo = row
        new_name = name if name else old_name
        new_roll = roll_number if roll_number else old_roll
        new_photo_path = old_photo
    except Exception as e:
        print(f"Error reading student data: {e}")
        return False
    finally:
        if conn:
            conn.close()

    if source_photo_path and os.path.isfile(source_photo_path):
        if old_photo and os.path.isfile(old_photo):
            try:
                os.remove(old_photo)
            except OSError as e:
                print(f"Warning: Could not delete old photo: {e}")

        try:
            ext = os.path.splitext(source_photo_path)[1]
            dest = os.path.join(STATIC_PHOTOS_DIR, f"{new_roll}{ext}")
            shutil.copy2(source_photo_path, dest)
            new_photo_path = dest

            image = face_recognition.load_image_file(dest)
            face_encs = face_recognition.face_encodings(image)
            if not face_encs:
                os.remove(dest)
                print("Error: No face detected in the new photo. Update cancelled.")
                return False
        except Exception as e:
            print(f"Error processing new photo: {e}")
            return False

        try:
            encodings, names = load_known_faces()
            indices_to_keep = [i for i, n in enumerate(names) if n != old_name]
            encodings = [encodings[i] for i in indices_to_keep]
            names = [names[i] for i in indices_to_keep]
            encodings.append(face_encs[0])
            names.append(new_name)
            with open(KNOWN_FACES_FILE, "wb") as f:
                pickle.dump((encodings, names), f)
        except Exception as e:
            print(f"Error updating face encodings: {e}")
            return False

    else:
        if new_name != old_name:
            try:
                encodings, names = load_known_faces()
                indices_to_keep = [i for i, n in enumerate(names) if n != old_name]
                encodings = [encodings[i] for i in indices_to_keep]
                names = [names[i] for i in indices_to_keep]

                if old_photo and os.path.isfile(old_photo):
                    image = face_recognition.load_image_file(old_photo)
                    face_encs = face_recognition.face_encodings(image)
                    if face_encs:
                        encodings.append(face_encs[0])
                        names.append(new_name)
                with open(KNOWN_FACES_FILE, "wb") as f:
                    pickle.dump((encodings, names), f)
            except Exception as e:
                print(f"Error updating face encodings for name change: {e}")
                return False

    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE students SET name = ?, roll_number = ?, photo_path = ? WHERE id = ?",
            (new_name, new_roll, new_photo_path, student_id),
        )
        conn.commit()
    except Exception as e:
        print(f"Error updating student in database: {e}")
        return False
    finally:
        if conn:
            conn.close()

    print(f"Updated student id {student_id}.")
    return True


def mark_attendance(student_id, status="present"):
    today = datetime.now().strftime("%Y-%m-%d")
    now_time = datetime.now().strftime("%H:%M:%S")

    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id FROM attendance WHERE student_id = ? AND date = ?",
            (student_id, today),
        )
        if cursor.fetchone():
            print(f"Student id {student_id} already marked present/absent today.")
            return False

        cursor.execute(
            "INSERT INTO attendance (student_id, date, time, status) VALUES (?, ?, ?, ?)",
            (student_id, today, now_time, status),
        )
        conn.commit()
        print(f"Attendance marked for student id {student_id}: {status}.")
        return True
    except Exception as e:
        print(f"Error marking attendance: {e}")
        return False
    finally:
        if conn:
            conn.close()


def get_monthly_percentage(student_id, year, month):
    month_str = f"{year}-{month:02d}-%"
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT status FROM attendance WHERE student_id = ? AND date LIKE ?",
            (student_id, month_str),
        )
        rows = cursor.fetchall()
    except Exception as e:
        print(f"Error querying attendance: {e}")
        return 0.0
    finally:
        if conn:
            conn.close()

    if not rows:
        return 0.0

    present_count = sum(1 for r in rows if r[0] == "present")
    return round(present_count / len(rows) * 100, 2)
