# create_first_users.py - One-time setup script to create initial admin and student user accounts

import hashlib                     # for SHA-256 password hashing

from database import create_tables, get_connection  # DB helpers


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()  # return SHA-256 hex digest


def main():
    create_tables()                # ensure database tables exist
    conn = get_connection()        # open DB connection
    cursor = conn.cursor()         # create cursor

    cursor.execute("SELECT id FROM students LIMIT 1")  # check if any student exists
    student_row = cursor.fetchone()
    student_id = student_row[0] if student_row else None  # get first student ID or None

    try:
        cursor.execute(
            "INSERT INTO users (username, password, role, student_id) VALUES (?, ?, ?, ?)",
            ("admin", hash_password("admin123"), "admin", None),  # insert admin user
        )
        print("Created admin user (username: admin, password: admin123)")
    except Exception:
        print("Admin user already exists, skipping.")

    if student_id:                 # at least one student exists in the DB
        try:
            cursor.execute(
                "INSERT INTO users (username, password, role, student_id) VALUES (?, ?, ?, ?)",
                ("student", hash_password("student123"), "student", student_id),  # create student login
            )
            print(f"Created student user (username: student, password: student123, linked to student_id={student_id})")
        except Exception:
            print("Student user already exists, skipping.")
    else:
        print("No students enrolled yet. Enroll a student first, then run this script again to create their login.")

    conn.commit()                  # commit all insertions
    conn.close()                   # close connection


if __name__ == "__main__":
    main()                         # run main function when script is executed directly

# ============================================================
# Role of the full code (create_first_users.py):
#   This is a one-time initialisation script that creates the first admin
#   user (admin / admin123) and a generic student user (student / student123)
#   linked to the first student record in the database. It runs automatically
#   when needed to bootstrap the authentication system so that the Flask app
#   has at least one admin account to log in with.
