# face_utils.py - Face detection, encoding, and recognition utility functions

import os
import pickle
import face_recognition

DATASET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dataset")
KNOWN_FACES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "known_faces.pkl")


def build_known_faces():
    encodings = []
    names = []

    if not os.path.exists(DATASET_DIR):
        print("Dataset folder not found.")
        return

    for student_name in sorted(os.listdir(DATASET_DIR)):
        student_dir = os.path.join(DATASET_DIR, student_name)
        if not os.path.isdir(student_dir):
            continue

        IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff"}
        for filename in sorted(os.listdir(student_dir)):
            filepath = os.path.join(student_dir, filename)
            if not os.path.isfile(filepath):
                continue
            if os.path.splitext(filename)[1].lower() not in IMAGE_EXTS:
                continue

            image = face_recognition.load_image_file(filepath)
            face_encs = face_recognition.face_encodings(image)

            if not face_encs:
                print(f"Warning: No face detected in '{filepath}', skipping.")
                continue

            for enc in face_encs:
                encodings.append(enc)
                names.append(student_name)

    with open(KNOWN_FACES_FILE, "wb") as f:
        pickle.dump((encodings, names), f)

    print(f"Saved {len(encodings)} encoding(s) for {len(set(names))} student(s).")


def load_known_faces():
    if not os.path.isfile(KNOWN_FACES_FILE):
        return [], []
    with open(KNOWN_FACES_FILE, "rb") as f:
        encodings, names = pickle.load(f)
    return encodings, names


def match_face(live_encoding, known_encodings, known_names, threshold=0.5):
    if not known_encodings:
        return None

    distances = face_recognition.face_distance(known_encodings, live_encoding)
    best_idx = distances.argmin()

    if distances[best_idx] <= threshold:
        return known_names[best_idx]
    return None


if __name__ == "__main__":
    build_known_faces()
