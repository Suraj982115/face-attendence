# manage_dataset.py - Scripts for adding, removing, and managing student photo datasets

import os
import shutil

DATASET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dataset")


def add_student(student_name):
    student_dir = os.path.join(DATASET_DIR, student_name)
    if os.path.exists(student_dir):
        print(f"Student '{student_name}' folder already exists.")
        return student_dir
    os.makedirs(student_dir)
    print(f"Created folder for student '{student_name}'.")
    return student_dir


def add_photo(student_name, source_photo_path):
    student_dir = os.path.join(DATASET_DIR, student_name)
    if not os.path.exists(student_dir):
        print(f"Student '{student_name}' not found. Create the student first.")
        return False
    if not os.path.isfile(source_photo_path):
        print(f"Source photo '{source_photo_path}' not found.")
        return False
    filename = os.path.basename(source_photo_path)
    dest = os.path.join(student_dir, filename)
    shutil.copy2(source_photo_path, dest)
    print(f"Added '{filename}' to '{student_name}'.")
    return True


def remove_photo(student_name, photo_filename):
    student_dir = os.path.join(DATASET_DIR, student_name)
    if not os.path.exists(student_dir):
        print(f"Student '{student_name}' not found.")
        return False
    photo_path = os.path.join(student_dir, photo_filename)
    if not os.path.isfile(photo_path):
        print(f"Photo '{photo_filename}' not found for '{student_name}'.")
        return False
    os.remove(photo_path)
    print(f"Removed '{photo_filename}' from '{student_name}'.")
    return True


def remove_student(student_name):
    student_dir = os.path.join(DATASET_DIR, student_name)
    if not os.path.exists(student_dir):
        print(f"Student '{student_name}' not found.")
        return False
    shutil.rmtree(student_dir)
    print(f"Removed student '{student_name}' and all their photos.")
    return True


def list_students():
    if not os.path.exists(DATASET_DIR):
        print("Dataset folder does not exist.")
        return
    entries = sorted(os.listdir(DATASET_DIR))
    students = [e for e in entries if os.path.isdir(os.path.join(DATASET_DIR, e))]
    if not students:
        print("No students found.")
        return
    print(f"{'Student':<30} {'Photos':>6}")
    print("-" * 37)
    for name in students:
        count = len([
            f for f in os.listdir(os.path.join(DATASET_DIR, name))
            if os.path.isfile(os.path.join(DATASET_DIR, name, f))
        ])
        print(f"{name:<30} {count:>6}")


if __name__ == "__main__":
    add_student("suraj_bohora")

    placeholder = os.path.join(DATASET_DIR, "_placeholder.txt")
    if not os.path.exists(placeholder):
        os.makedirs(DATASET_DIR, exist_ok=True)
        with open(placeholder, "w") as f:
            f.write("temporary placeholder for testing")
    add_photo("suraj_bohora", placeholder)
    os.remove(placeholder)

    list_students()
