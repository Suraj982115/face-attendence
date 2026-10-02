# live_test.py - Standalone live webcam test for face detection + recognition

import cv2                       # for camera capture and image display
import face_recognition          # for face encoding and comparison
import numpy as np               # (imported for potential array ops, indirectly used by cv2)
from ultralytics import YOLO     # YOLOv8 face detection model
from face_utils import load_known_faces, match_face  # face recognition helpers

YOLO_MODEL_PATH = "models/yolov8n-face.pt"  # path to YOLOv8 face detection model


def main():
    model = YOLO(YOLO_MODEL_PATH)                    # load YOLO face detection model
    known_encodings, known_names = load_known_faces()  # load pre-built face encodings
    print(f"Loaded {len(known_encodings)} known face(s).")

    cap = cv2.VideoCapture(0)                        # open webcam (camera 0)
    if not cap.isOpened():                           # webcam could not be opened
        print("Cannot open webcam.")
        return

    print("Press ESC to quit.")

    while True:                                      # infinite capture loop
        ret, frame = cap.read()                      # read a frame from webcam
        if not ret:
            break

        results = model(frame, verbose=False)        # run YOLO face detection on frame

        for box in results[0].boxes:                 # iterate over detected faces
            x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())  # get bounding box coordinates

            face_crop = frame[y1:y2, x1:x2]          # crop the face region
            if face_crop.size == 0:
                continue

            rgb_crop = cv2.cvtColor(face_crop, cv2.COLOR_BGR2RGB)  # convert BGR to RGB for face_recognition
            encs = face_recognition.face_encodings(rgb_crop)  # compute face encoding for the crop

            name = "Unknown"                         # default label
            color = (0, 0, 255)                      # red for unknown

            if encs:                                 # face encoding succeeded
                matched = match_face(encs[0], known_encodings, known_names)  # try to match
                if matched:
                    name = matched                   # set recognised name
                    color = (0, 255, 0)              # green for known

            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)  # draw bounding box
            cv2.putText(frame, name, (x1, y1 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)  # draw label above box

        cv2.imshow("Live Face Test", frame)          # display the frame
        if cv2.waitKey(1) & 0xFF == 27:              # ESC key pressed
            break

    cap.release()                                    # release webcam
    cv2.destroyAllWindows()                          # close display window


if __name__ == "__main__":
    main()                                           # run main when executed directly

# ============================================================
# Role of the full code (live_test.py):
#   This is a standalone script for testing the face detection and recognition
#   pipeline in real-time using the webcam. It loads the YOLOv8 face detection
#   model and the known face encodings, then continuously captures frames,
#   detects faces, matches them against known faces, and displays the results
#   with bounding boxes and labels. It runs independently of the Flask server
#   and is intended for testing face recognition accuracy.
