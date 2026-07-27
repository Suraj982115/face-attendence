# live_test.py - Standalone live webcam test for face detection + recognition

import cv2
import face_recognition
import numpy as np
from ultralytics import YOLO
from face_utils import load_known_faces, match_face

YOLO_MODEL_PATH = "models/yolov8n-face.pt"


def main():
    model = YOLO(YOLO_MODEL_PATH)
    known_encodings, known_names = load_known_faces()
    print(f"Loaded {len(known_encodings)} known face(s).")

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Cannot open webcam.")
        return

    print("Press ESC to quit.")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        results = model(frame, verbose=False)

        for box in results[0].boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())

            face_crop = frame[y1:y2, x1:x2]
            if face_crop.size == 0:
                continue

            rgb_crop = cv2.cvtColor(face_crop, cv2.COLOR_BGR2RGB)
            encs = face_recognition.face_encodings(rgb_crop)

            name = "Unknown"
            color = (0, 0, 255)

            if encs:
                matched = match_face(encs[0], known_encodings, known_names)
                if matched:
                    name = matched
                    color = (0, 255, 0)

            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            cv2.putText(frame, name, (x1, y1 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

        cv2.imshow("Live Face Test", frame)
        if cv2.waitKey(1) & 0xFF == 27:
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
