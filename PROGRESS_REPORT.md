# Progress Report

## Face Recognition Based Student Attendance System

**Student:** Suraj Bohora

**Date:** 10 August 2026

---

## 1. Introduction

This project develops a student attendance system that automatically records attendance using facial recognition technology. Instead of the traditional manual method of calling out names or signing registers, the system uses a live webcam to detect students' faces, match them against a pre-registered database of student faces, and mark their attendance automatically.

The system is being built as a web application so that it can be accessed from any device on the network, making it practical for real classroom use.

## 2. Objectives

The main objectives of this project are:

1. To register students by capturing and storing their facial data and personal information.
2. To automatically detect and recognize students using a live camera feed.
3. To mark attendance for recognized students once per day, avoiding duplicate entries.
4. To provide a monthly attendance report for teachers and a personal attendance view for students.
5. To provide an easy-to-use web interface for administrators to manage students.

## 3. Technology Used

| Component | Technology |
|-----------|------------|
| Programming Language | Python |
| Web Framework | Flask |
| Face Detection | YOLOv8 (Ultralytics) |
| Face Recognition | `face_recognition` library (dlib-based) |
| Image Processing | OpenCV |
| Database | SQLite |
| Frontend | HTML / CSS / JavaScript (Jinja2 templates) |

## 4. Work Completed So Far

### 4.1 Project Structure

The project has been organised into clearly separated modules:

- **`app.py`** – the Flask web application containing all routes (login, admin dashboard, student dashboard, live video feed).
- **`backend.py`** – the core business logic for enrolling, updating and removing students, marking attendance, and generating monthly reports.
- **`database.py`** – manages the SQLite database schema and connections.
- **`face_utils.py`** – handles face encoding, storing known faces, and matching live faces.
- **`manage_dataset.py`** – utility scripts for managing the photo dataset.
- **`create_first_users.py`** – a one-time setup script that creates the admin and student login accounts.

### 4.2 Database Design

Three database tables have been created:

- **`students`** – stores student ID, name, roll number, and photo path.
- **`users`** – stores login credentials (username and password) with roles (admin or student).
- **`attendance`** – stores daily attendance records linked to each student, including date, time, and status.

### 4.3 Features Implemented

1. **Login System** – Users log in with a username and password. Access is controlled by role: administrators manage the system, students only view their own attendance.

2. **Student Management** – Administrators can add new students by entering their name and roll number and uploading a photo. The system checks that a face is present in the photo, saves the photo, creates a student login account, and stores the face data. Students can also be edited or removed.

3. **Live Face Recognition** – A webcam feed streams through the web application. YOLOv8 detects faces in each frame, and the `face_recognition` library compares each face against the stored known faces. Recognized students are shown with a green box and their name; unrecognized faces are shown with a red box labelled "Unknown".

4. **Automatic Attendance Marking** – When a recognized student appears in the camera feed, their attendance is automatically recorded for the day. The system ensures each student is marked only once per day, preventing duplicate entries.

5. **Attendance Register (Admin)** – Teachers can view a monthly attendance register showing all students as rows and the days of the month as columns, with daily presence totals.

6. **Student Dashboard** – Students can log in and view their own monthly attendance percentage and a day-by-day register of their presence.

### 4.4 Testing

A standalone test script (`live_test.py`) has been created to test the face detection and recognition pipeline directly with the webcam, independent of the web application. A sample student has been enrolled and their face data has been stored for testing.

## 5. Current Status

- The core system is functional: login, student enrollment, and attendance recording are working.
- One test student has been enrolled, and admin and student login accounts have been created.
- The monthly attendance register and student dashboard are implemented.
- Live recognition with automatic attendance marking has been implemented and is ready for end-to-end testing.

## 6. Challenges

- **Face Recognition Accuracy** – Matching accuracy depends on lighting, camera angle, and face size. The matching threshold needs to be tuned for reliable recognition in a classroom environment.
- **Model Size and Speed** – The YOLOv8 face detection model needs to run in real time alongside face recognition, which requires a balance between accuracy and processing speed.
- **Hardcoded Configuration** – The secret key and default passwords are currently hardcoded and should be moved to environment configuration for better security.

## 7. Next Steps

1. Perform a full end-to-end test of the live attendance marking and verify accuracy.
2. Enroll all students of the class and create individual login accounts.
3. Add support for marking other statuses (e.g., absent, late) and manual attendance entry.
4. Add an admin analytics view showing overall attendance trends.
5. Improve face matching by storing multiple photos per student.
6. Move configuration values (secret key, passwords) to environment variables.

## 8. Conclusion

A significant portion of the project has been completed. The system successfully registers students, recognizes their faces from a live camera feed, and records their attendance automatically. The remaining work focuses on testing with real students, expanding features, and improving recognition accuracy.

---
