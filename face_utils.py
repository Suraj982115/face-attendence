# face_utils.py - Face detection, encoding, and recognition utility functions

import os            # for file and path operations
import pickle        # for serialising face encodings to disk
import face_recognition  # for face detection and encoding

DATASET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dataset")  # directory with student photo subfolders
KNOWN_FACES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "known_faces.pkl")  # file to store serialised face encodings


def build_known_faces():
    encodings = []   # list to accumulate face encodings
    names = []       # list to accumulate corresponding names

    if not os.path.exists(DATASET_DIR):      # dataset directory missing
        print("Dataset folder not found.")
        return

    for student_name in sorted(os.listdir(DATASET_DIR)):  # iterate over student folders
        student_dir = os.path.join(DATASET_DIR, student_name)
        if not os.path.isdir(student_dir):    # skip non-directory entries
            continue

        IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff"}  # allowed image extensions
        for filename in sorted(os.listdir(student_dir)):  # iterate over photos in folder
            filepath = os.path.join(student_dir, filename)
            if not os.path.isfile(filepath):  # skip non-files
                continue
            if os.path.splitext(filename)[1].lower() not in IMAGE_EXTS:  # skip non-image files
                continue

            image = face_recognition.load_image_file(filepath)  # load image
            face_encs = face_recognition.face_encodings(image)  # compute face encodings

            if not face_encs:                 # no face detected in this image
                print(f"Warning: No face detected in '{filepath}', skipping.")
                continue

            for enc in face_encs:
                encodings.append(enc)         # add encoding to list
                names.append(student_name)    # associate with student name

    with open(KNOWN_FACES_FILE, "wb") as f:
        pickle.dump((encodings, names), f)    # serialise encodings to disk

    print(f"Saved {len(encodings)} encoding(s) for {len(set(names))} student(s).")


def load_known_faces():
    if not os.path.isfile(KNOWN_FACES_FILE):  # no known faces file yet
        return [], []
    with open(KNOWN_FACES_FILE, "rb") as f:
        encodings, names = pickle.load(f)     # deserialise encodings from disk
    return encodings, names


def match_face(live_encoding, known_encodings, known_names, threshold=0.5):
    if not known_encodings:                   # no known faces to match against
        return None

    distances = face_recognition.face_distance(known_encodings, live_encoding)  # compute distances to all known faces
    best_idx = distances.argmin()             # index of closest match

    if distances[best_idx] <= threshold:      # closest match is within threshold
        return known_names[best_idx]          # return the corresponding name
    return None                               # no reliable match


if __name__ == "__main__":
    build_known_faces()    # rebuild known faces when run directly

# ============================================================
# Role of the full code (face_utils.py):
#   This module provides all face-related utility functions:
#   - build_known_faces(): scans the dataset/ directory (with per-student
#     subfolders of photos), computes face encodings using face_recognition,
#     and serialises them to known_faces.pkl via pickle.
#   - load_known_faces(): deserialises and returns the stored encodings + names.
#   - match_face(): compares a live face encoding against known encodings using
#     face_distance and a configurable threshold; returns the matched name or None.
#   These functions are used by both the web app and standalone test scripts.
