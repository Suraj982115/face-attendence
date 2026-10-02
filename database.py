# database.py - Database models and operations for student records and attendance logs

import os           # for file path construction
import sqlite3      # for SQLite database operations

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "attendance.db")  # path to SQLite database file


def get_connection():
    try:
        conn = sqlite3.connect(DB_PATH)     # open (or create) the SQLite database
        conn.execute("PRAGMA foreign_keys = ON")  # enable foreign key enforcement
        return conn
    except sqlite3.Error as e:
        print(f"Database connection error: {e}")
        raise


def create_tables():
    conn = get_connection()                 # open database connection
    try:
        cursor = conn.cursor()              # create cursor

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                roll_number TEXT NOT NULL UNIQUE,
                photo_path TEXT
            )
        """)  # students table: stores student identity and photo location

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                time TEXT NOT NULL,
                status TEXT NOT NULL,
                FOREIGN KEY (student_id) REFERENCES students(id)
            )
        """)  # attendance table: stores daily attendance records linked to students

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL,
                role TEXT NOT NULL,
                student_id INTEGER,
                FOREIGN KEY (student_id) REFERENCES students(id)
            )
        """)  # users table: stores login credentials with role-based access

        conn.commit()                       # commit all table creations
    finally:
        conn.close()                        # close connection


if __name__ == "__main__":
    create_tables()      # ensure tables exist when run directly
    print("Database ready.")

# ============================================================
# Role of the full code (database.py):
#   This module handles all SQLite database connectivity and schema
#   management. It defines three tables:
#   - students: core student information (id, name, roll_number, photo_path)
#   - attendance: daily attendance entries linked to students via foreign key
#   - users: authentication credentials with role (admin/student) and optional
#     link to a student record
#   The module exports get_connection() for obtaining a database connection
#   with foreign keys enabled, and create_tables() for initialising the schema.
