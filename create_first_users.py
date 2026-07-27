# create_first_users.py - One-time setup script to create initial admin and student user accounts

import hashlib

from database import create_tables, get_connection


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def main():
    create_tables()
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM students LIMIT 1")
    student_row = cursor.fetchone()
    student_id = student_row[0] if student_row else None

    try:
        cursor.execute(
            "INSERT INTO users (username, password, role, student_id) VALUES (?, ?, ?, ?)",
            ("admin", hash_password("admin123"), "admin", None),
        )
        print("Created admin user (username: admin, password: admin123)")
    except Exception:
        print("Admin user already exists, skipping.")

    if student_id:
        try:
            cursor.execute(
                "INSERT INTO users (username, password, role, student_id) VALUES (?, ?, ?, ?)",
                ("student", hash_password("student123"), "student", student_id),
            )
            print(f"Created student user (username: student, password: student123, linked to student_id={student_id})")
        except Exception:
            print("Student user already exists, skipping.")
    else:
        print("No students enrolled yet. Enroll a student first, then run this script again to create their login.")

    conn.commit()
    conn.close()


if __name__ == "__main__":
    main()
