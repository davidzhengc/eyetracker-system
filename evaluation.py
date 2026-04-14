"""
Gaze tracking evaluation module.
"""
import cv2
import numpy as np
import time
import pandas as pd
from datetime import datetime
import os



def run_evaluation(tracker):
    """
    Runs an evaluation sequence to measure gaze tracking accuracy and precision.
    """
    print("\n" + "="*50)
    print("EVALUATION SEQUENCE")
    print("="*50)
    print("Instructions:")
    print("  - Look at each target as it appears on the screen.")
    print("  - Try to keep your head still.")
    print("  - The evaluation will start in 5 seconds.")
    print("="*50 + "\n")
    time.sleep(5)

    # --- Evaluation Parameters ---
    margin = 100
    w, h = tracker.screen_w, tracker.screen_h

    SCREEN_WIDTH_MM = 527.0  # 23.8" Monitor width in mm
    DISTANCE_TO_SCREEN_MM = 400.0 # Distance from user to screen in mm

    pixel_size_mm = SCREEN_WIDTH_MM / w

    def px_to_degrees(px_distance):
        """Converts distance from pixels to degrees"""
        dist_mm = px_distance * pixel_size_mm

        angle_rad = 2 * np.arctan(dist_mm / (2 * DISTANCE_TO_SCREEN_MM))
        return np.degrees(angle_rad)

    evaluation_points = [
        (margin, margin), (w // 2, margin), (w - margin, margin),
        (margin, h // 2), (w // 2, h // 2), (w - margin, h // 2),
        (margin, h - margin), (w // 2, h - margin), (w - margin, h - margin)
    ]
    
    fixation_duration = 3
    settle_time = 1.5

    all_results = []
    
    window_name = "EvaluationOverlay"
    cv2.namedWindow(window_name, cv2.WND_PROP_FULLSCREEN)
    cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    
    if not tracker.cap or not tracker.cap.isOpened():
        print("Error: Camera is not open. Cannot run evaluation.")
        return

    for i, target_pos in enumerate(evaluation_points):
        print(f"Target {i+1}/{len(evaluation_points)}: {target_pos}")
        
        start_settle = time.time()
        while time.time() - start_settle < settle_time:
            overlay = np.zeros((h, w, 3), dtype=np.uint8)
            cv2.circle(overlay, target_pos, 20, (0, 255, 0), -1)
            cv2.circle(overlay, target_pos, 10, (0, 0, 0), -1)
            cv2.imshow(window_name, overlay)
            if cv2.waitKey(1) & 0xFF == 27:
                cv2.destroyAllWindows()
                return

        point_gaze_data = []
        start_fixation = time.time()
        while time.time() - start_fixation < fixation_duration:
            ret, frame = tracker.cap.read()
            if not ret:
                break

            gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced_frame = clahe.apply(gray_frame)
            final_frame = cv2.cvtColor(enhanced_frame, cv2.COLOR_GRAY2BGR)
            
            features, blink = tracker.estimator.extract_features(final_frame)
            
            gaze_x, gaze_y = None, None
            if not blink and features is not None:
                raw_x, raw_y = tracker.estimator.predict([features])[0]
                if tracker.smoother:
                    smooth_x, smooth_y = tracker.smoother.step(int(raw_x), int(raw_y))
                else:
                    smooth_x, smooth_y = int(raw_x), int(raw_y)
                
                smooth_x, smooth_y = tracker.apply_noise_reduction(smooth_x, smooth_y)
                gaze_x, gaze_y = smooth_x, smooth_y
                tracker.last_valid_gaze = (gaze_x, gaze_y)
            elif tracker.last_valid_gaze is not None:
                gaze_x, gaze_y = tracker.last_valid_gaze

            if gaze_x is not None:
                point_gaze_data.append((gaze_x, gaze_y))

            overlay = np.zeros((h, w, 3), dtype=np.uint8)
            cv2.circle(overlay, target_pos, 20, (0, 255, 0), -1)
            cv2.circle(overlay, target_pos, 10, (0, 0, 0), -1)
            if gaze_x is not None:
                cv2.circle(overlay, (gaze_x, gaze_y), 10, (0, 0, 255), -1)
            cv2.imshow(window_name, overlay)
            if cv2.waitKey(1) & 0xFF == 27:
                break
        
        if not point_gaze_data:
            print(f"  - No gaze data collected for this target.")
            continue

        gaze_points = np.array(point_gaze_data)
        mean_gaze = np.mean(gaze_points, axis=0)
        
        accuracy_px = np.linalg.norm(mean_gaze - np.array(target_pos))
        distances_from_mean = np.linalg.norm(gaze_points - mean_gaze, axis=1)
        precision_px = np.std(distances_from_mean)

        #Conversion to degrees
        accuracy_deg = px_to_degrees(accuracy_px)
        precision_deg = px_to_degrees(precision_px)

        print(f"  - Accuracy (error): {accuracy_deg:.2f}° ({accuracy_px:.2f} px)")
        print(f"  - Precision (jitter): {precision_deg:.2f}° ({precision_px:.2f} px)")

        all_results.append({
            "target_x": target_pos[0],
            "target_y": target_pos[1],
            "mean_gaze_x": mean_gaze[0],
            "mean_gaze_y": mean_gaze[1],
            "accuracy_px": accuracy_px,
            "precision_px": precision_px,
            "accuracy_deg": accuracy_deg,
            "precision_deg": precision_deg,
            "n_samples": len(point_gaze_data)
        })
    cv2.destroyAllWindows()
    
    if not all_results:
        print("Evaluation incomplete. No data was collected.")
        return

    df = pd.DataFrame(all_results)
    
    overall_accuracy = df["accuracy_px"].mean()
    overall_precision = df["precision_px"].mean()

    print("\n" + "="*50)
    print("EVALUATION SUMMARY")
    print("="*50)
    print(f"  Overall Accuracy (Mean Error): {overall_accuracy:.2f} pixels")
    print(f"  Overall Precision (Mean Jitter): {overall_precision:.2f} pixels")
    print("="*50)

    results_dir = "results"
    os.makedirs(results_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_filename = f"evaluation_results_{timestamp}"
    filename = os.path.join(results_dir, f"{base_filename}.csv")
    counter = 1
    while os.path.exists(filename):
        filename = os.path.join(results_dir, f"{base_filename}_{counter}.csv")
        counter += 1
    
    df.to_csv(filename, index=False)
    print(f"\nEvaluation results saved to: {filename}")
