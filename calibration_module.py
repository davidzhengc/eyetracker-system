"""
Calibration module for gaze tracking.
Contains n-point grid calibration and Lissajous curve calibration methods.
"""
from __future__ import annotations
import time
import cv2
import numpy as np
import math
import random
from screeninfo import get_monitors
from eyetrax import GazeEstimator
from eyetrax.calibration.common import (
    wait_for_face_and_countdown,
    _pulse_and_capture,
    compute_grid_points
)

try:
    import win32gui
    import win32con
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False


def get_screen_size():
    """Get screen dimensions."""
    monitor = get_monitors()[0]
    return monitor.width, monitor.height


def bring_window_to_front(window_name: str):
    """Bring a window to the front using Windows API (if available)."""
    if not HAS_WIN32:
        return
    
    try:
        hwnd = win32gui.FindWindow(None, window_name)
        if hwnd:
            # Restore window if minimized
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            # Bring window to front
            # Bring window to front
            win32gui.SetForegroundWindow(hwnd)
            # Set window to topmost temporarily to ensure it's on top
            # Set window to topmost temporarily to ensure it's on top
            win32gui.SetWindowPos(
                hwnd,
                win32con.HWND_TOPMOST,
                0, 0, 0, 0,
                win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_SHOWWINDOW
            )
            # Remove topmost flag after a moment so other windows can come on top later
            # Remove topmost flag after a moment so other windows can come on top later
            time.sleep(0.1)
            win32gui.SetWindowPos(
                hwnd,
                win32con.HWND_NOTOPMOST,
                0, 0, 0, 0,
                win32con.SWP_NOMOVE | win32con.SWP_NOSIZE
            )
    except Exception:
        pass  # Silently fail if Windows API doesn't work


def wait_for_space_to_start(camera_index=0):
    """
    Display a message asking the user to press SPACE when ready to start calibration.

    Args:
        camera_index: Camera device index for displaying camera feed

    Returns:
        bool: True if space was pressed, False if ESC was pressed
    """
    sw, sh = get_screen_size()
    cap = cv2.VideoCapture(camera_index)

    # Create fullscreen window
    cv2.namedWindow("Calibration", cv2.WND_PROP_FULLSCREEN)
    cv2.setWindowProperty("Calibration", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    bring_window_to_front("Calibration")
    
    print("\nPress SPACE when you are ready to start calibration...")
    
    while True:
        ret, frame = cap.read()
        if not ret:
            continue

        # Create canvas
        canvas = np.zeros((sh, sw, 3), dtype=np.uint8)
        
        # Display instruction text
        text = "Press SPACE when ready to start calibration"
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 1.5
        thickness = 3
        color = (255, 255, 255)
        
        # Get text size for centering
        (text_width, text_height), baseline = cv2.getTextSize(text, font, font_scale, thickness)
        text_x = (sw - text_width) // 2
        text_y = (sh + text_height) // 2
        
        # Draw text with outline for better visibility
        cv2.putText(canvas, text, (text_x, text_y), font, font_scale, (0, 0, 0), thickness + 2)
        cv2.putText(canvas, text, (text_x, text_y), font, font_scale, color, thickness)
        
        cv2.imshow("Calibration", canvas)
        
        key = cv2.waitKey(1) & 0xFF
        if key == 32:  # SPACE key
            cap.release()
            return True
        elif key == 27:  # ESC key
            cap.release()
            cv2.destroyAllWindows()
            return False


def run_n_point_calibration(gaze_estimator, num_points=25, camera_index=0):
    """
    Generalized n-point calibration with randomized point order.
    Works exactly like run_9_point_calibration but with configurable number of points.

    Args:
        gaze_estimator: GazeEstimator instance
        num_points: Number of calibration points (should be a perfect square: 9, 16, 25, etc.)
        camera_index: Camera device index

    Returns:
        bool: True if calibration succeeded, False otherwise
    """
    sw, sh = get_screen_size()

    cap = cv2.VideoCapture(camera_index)
    if not wait_for_face_and_countdown(cap, gaze_estimator, sw, sh, 2):
        cap.release()
        cv2.destroyAllWindows()
        return False

    # Generate grid order: (row, col) pairs from (0,0) to (side-1, side-1)
    side = int(math.sqrt(num_points))
    order = [(r, c) for r in range(side) for c in range(side)]

    # Randomize the order
    random.shuffle(order)
    
    # Convert grid indices to screen pixel coordinates using eyetrax function
    pts = compute_grid_points(order, sw, sh)

    res = _pulse_and_capture(gaze_estimator, cap, pts, sw, sh)
    cap.release()
    cv2.destroyAllWindows()
    
    if res is None:
        return False
    
    feats, targs = res
    if feats:
        gaze_estimator.train(np.array(feats), np.array(targs))
        return True
    
    return False


"""
def run_lissajous_calibration(gaze_estimator, duration=20, camera_index=0, 
                               coverage=0.45, speed_factor=0.5):
    
    Moves a calibration point along a Lissajous curve for dense coverage.
    
    How it works:
    - Creates a figure-8 pattern (Lissajous curve) using sine waves
    - The curve is centered on screen and covers a percentage of screen space
    - Uses constant slow speed throughout (around 0.2 base speed)
    - This provides dense, continuous calibration data across the screen
    
    Args:
        gaze_estimator: GazeEstimator instance
        duration: Duration in seconds for the calibration (default: 20)
        camera_index: Camera device index
        coverage: Screen coverage factor (0.0-0.5, default: 0.45)
                  - 0.4 = covers 80% of screen (40% radius from center)
                  - 0.45 = covers 90% of screen (45% radius from center)
                  - 0.5 = covers 100% of screen (50% radius from center, may go off edges)
        speed_factor: Speed multiplier (0.0-1.0, default: 1.0)
                      - Base speed is 0.2, multiplied by this factor
                      - 0.5 = 0.1 speed (very slow)
                      - 1.0 = 0.2 speed (default slow speed)
                      - Higher values increase speed proportionally
    
    Returns:
        bool: True if calibration succeeded, False otherwise
    
    sw, sh = get_screen_size()
    cap = cv2.VideoCapture(camera_index)
    
    # Ensure calibration window is created and brought to front
    cv2.namedWindow("Calibration", cv2.WND_PROP_FULLSCREEN)
    cv2.setWindowProperty("Calibration", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    # Show a blank frame to initialize the window
    blank = np.zeros((sh, sw, 3), dtype=np.uint8)
    cv2.imshow("Calibration", blank)
    cv2.waitKey(1)
    bring_window_to_front("Calibration")
    time.sleep(0.2)  # Give window time to appear
    
    if not wait_for_face_and_countdown(cap, gaze_estimator, sw, sh, 2):
        cap.release()
        cv2.destroyAllWindows()
        return False
    
    # Bring window back to front after face check
    bring_window_to_front("Calibration")
    time.sleep(0.1)

    # Lissajous curve parameters
    # Amplitude: controls how much of the screen is covered
    # coverage=0.45 means the curve covers 90% of screen (45% radius from center)
    A, B = sw * coverage, sh * coverage
    
    # Frequency ratios: a=3, b=2 creates a figure-8 pattern
    # Phase: d=0 means no phase shift
    a, b, d = 3, 2, 0

    def curve(t):
        Generate point on Lissajous curve.
        
        The curve equation:
        x = A * sin(a*t + d) + center_x
        y = B * sin(b*t) + center_y
        
        This creates a figure-8 pattern that covers the screen.
        
        return (A * np.sin(a * t + d) + sw / 2, B * np.sin(b * t) + sh / 2)

    # Calculate frames for the specified duration
    fps = 15
    frames = int(duration * fps)
    feats, targs = [], []
    
    # Constant slow speed: base speed of 0.2, scaled by speed_factor
    # This keeps the movement slow and constant throughout
    constant_speed = 0.2 * speed_factor

    print(f"Starting Lissajous calibration ({duration} seconds)...")
    print(f"Coverage: {coverage*100:.0f}% radius, Constant speed: {constant_speed:.2f}")
    print("Follow the green dot as it moves along the curve.")
    
    # Ensure window is in front before starting
    bring_window_to_front("Calibration")

    # Main calibration loop - use constant speed
    for i in range(frames):
        frac = i / (frames - 1) if frames > 1 else 0
        # Calculate t linearly based on constant speed
        # We want to complete one full cycle (2*pi) over the duration
        t = frac * (2 * np.pi)
        
        ret, frame = cap.read()
        if not ret:
            continue
            
        x, y = curve(t)
        canvas = np.zeros((sh, sw, 3), dtype=np.uint8)
        
        # Draw the calibration point
        cv2.circle(canvas, (int(x), int(y)), 20, (0, 255, 0), -1)
        
        # Show progress
        progress_text = f"Progress: {int(frac * 100)}%"
        cv2.putText(canvas, progress_text, (50, 50), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        
        cv2.imshow("Calibration", canvas)
        
        if cv2.waitKey(1) == 27:  # ESC to cancel
            cap.release()
            cv2.destroyAllWindows()
            return False
            
        # Extract features and collect data
        ft, blink = gaze_estimator.extract_features(frame)
        if ft is not None and not blink:
            feats.append(ft)
            targs.append([x, y])

    cap.release()
    cv2.destroyAllWindows()
    
    if feats:
        gaze_estimator.train(np.array(feats), np.array(targs))
        print("Lissajous calibration complete and model trained.")
        return True
    
    print("Lissajous calibration failed - no valid data collected.")
    return False

"""