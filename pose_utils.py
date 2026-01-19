import cv2
import mediapipe as mp
import numpy as np

mp_pose = mp.solutions.pose

def detect_pose(image_path):
    image = cv2.imread(image_path)
    h, w, _ = image.shape

    with mp_pose.Pose(static_image_mode=True) as pose:
        results = pose.process(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))

        if not results.pose_landmarks:
            return None

        lm = results.pose_landmarks.landmark

        # Kritik noktalar
        left_shoulder = lm[mp_pose.PoseLandmark.LEFT_SHOULDER]
        right_shoulder = lm[mp_pose.PoseLandmark.RIGHT_SHOULDER]
        left_hip = lm[mp_pose.PoseLandmark.LEFT_HIP]
        right_hip = lm[mp_pose.PoseLandmark.RIGHT_HIP]

        return {
            "shoulder_width": abs(left_shoulder.x - right_shoulder.x) * w,
            "torso_height": abs(left_shoulder.y - left_hip.y) * h,
            "center_x": int((left_shoulder.x + right_shoulder.x) / 2 * w),
            "center_y": int((left_shoulder.y + left_hip.y) / 2 * h),
        }
