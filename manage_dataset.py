# manage_dataset.py - Scripts for adding, removing, and managing student photo datasets

import os           # for file and path operations
import shutil       # for copying and removing files/directories

DATASET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dataset")  # root directory for student photo datasets


def add_student(student_name):
    student_dir = os.path.join(DATASET_DIR, student_name)  # build path for new student folder
    if os.path.exists(student_dir):                        # folder already exists
        print(f"Student '{student_name}' folder already exists.")
        return student_dir
    os.makedirs(student_dir)                               # create the folder
    print(f"Created folder for student '{student_name}'.")
    return student_dir


def add_photo(student_name, source_photo_path):
    student_dir = os.path.join(DATASET_DIR, student_name)  # path to student folder
    if not os.path.exists(student_dir):                    # student folder does not exist
        print(f"Student '{student_name}' not found. Create the student first.")
        return False
    if not os.path.isfile(source_photo_path):               # source photo file missing
        print(f"Source photo '{source_photo_path}' not found.")
        return False
    filename = os.path.basename(source_photo_path)          # extract filename from path
    dest = os.path.join(student_dir, filename)              # destination path
    shutil.copy2(source_photo_path, dest)                   # copy photo into student folder
    print(f"Added '{filename}' to '{student_name}'.")
    return True


def remove_photo(student_name, photo_filename):
    student_dir = os.path.join(DATASET_DIR, student_name)  # path to student folder
    if not os.path.exists(student_dir):                    # student folder not found
        print(f"Student '{student_name}' not found.")
        return False
    photo_path = os.path.join(student_dir, photo_filename)  # full path to photo
    if not os.path.isfile(photo_path):                      # photo file not found
        print(f"Photo '{photo_filename}' not found for '{student_name}'.")
        return False
    os.remove(photo_path)                                   # delete the photo file
    print(f"Removed '{photo_filename}' from '{student_name}'.")
    return True


def remove_student(student_name):
    student_dir = os.path.join(DATASET_DIR, student_name)  # path to student folder
    if not os.path.exists(student_dir):                    # student folder not found
        print(f"Student '{student_name}' not found.")
        return False
    shutil.rmtree(student_dir)                              # delete entire folder and contents
    print(f"Removed student '{student_name}' and all their photos.")
    return True


def list_students():
    if not os.path.exists(DATASET_DIR):                     # dataset folder does not exist
        print("Dataset folder does not exist.")
        return
    entries = sorted(os.listdir(DATASET_DIR))               # list all entries in dataset dir
    students = [e for e in entries if os.path.isdir(os.path.join(DATASET_DIR, e))]  # filter only directories
    if not students:                                        # no student folders found
        print("No students found.")
        return
    print(f"{'Student':<30} {'Photos':>6}")                 # print table header
    print("-" * 37)                                         # print separator
    for name in students:
        count = len([                                        # count photo files in student folder
            f for f in os.listdir(os.path.join(DATASET_DIR, name))
            if os.path.isfile(os.path.join(DATASET_DIR, name, f))
        ])
        print(f"{name:<30} {count:>6}")                     # print student name and photo count


if __name__ == "__main__":
    add_student("suraj_bohora")                              # create student folder for suraj_bohora

    placeholder = os.path.join(DATASET_DIR, "_placeholder.txt")  # path for a placeholder file
    if not os.path.exists(placeholder):                     # placeholder does not exist yet
        os.makedirs(DATASET_DIR, exist_ok=True)             # ensure dataset dir exists
        with open(placeholder, "w") as f:
            f.write("temporary placeholder for testing")     # write placeholder content
    add_photo("suraj_bohora", placeholder)                  # add placeholder as a 'photo'
    os.remove(placeholder)                                   # clean up placeholder file

    list_students()                                          # display all students and their photo counts

# ============================================================
# Role of the full code (manage_dataset.py):
#   This module provides utility functions for managing the local dataset/
#   directory structure where student photos are stored. Each student has a
#   subfolder named after them. The module supports:
#   - add_student(): creating a new student folder
#   - add_photo(): copying a photo into a student's folder
#   - remove_photo(): deleting a specific photo from a student's folder
#   - remove_student(): deleting an entire student folder and all its photos
#   - list_students(): printing a table of all students with photo counts
#   When run as a standalone script it creates an example student entry and
#   displays the listing to demonstrate functionality.
