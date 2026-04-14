"""
Main gaze tracking application with configuration interface.
"""
from __future__ import annotations
import time
import cv2
import numpy as np
import pandas as pd
import os
import threading
from datetime import datetime

from eyetrax.calibration import run_lissajous_calibration
from screeninfo import get_monitors
from eyetrax import GazeEstimator
from eyetrax.filters.kalman import KalmanSmoother
from eyetrax.filters.kde import KDESmoother
from eyetrax.filters.noop import NoSmoother
import win32gui
import win32con
import win32api

try:
    import keyboard
    HAS_KEYBOARD = True
except ImportError:
    HAS_KEYBOARD = False
    print("Warning: 'keyboard' library not found. Install it with 'pip install keyboard' for global hotkey support.")

from calibration_module import (
    run_n_point_calibration, 
    get_screen_size,
    wait_for_space_to_start
)
from evaluation import run_evaluation


class GazeTrackerConfig:
    """Configuration class for gaze tracker settings."""
    def __init__(self):
        self.num_points = 25
        self.use_lissajous = False  # Disabled by default
        self.lissajous_duration = 20
        self.lissajous_coverage = 0.45  # Screen coverage (0.4-0.5, default: 0.45 = 90% coverage)
        self.lissajous_speed = 1.0  # Speed factor (default: 1.0 = 0.2 base speed, constant slow)
        self.filter_type = "kalman"  # "kalman", "kde", "none"
        self.camera_index = 0
        self.evaluation_mode = False # Run evaluation sequence


class GazeTracker:
    """Main gaze tracking application."""
    
    def __init__(self, config: GazeTrackerConfig = None):
        self.config = config or GazeTrackerConfig()
        self.screen_w, self.screen_h = get_screen_size()
        self.estimator = GazeEstimator()
        self.smoother = None
        self.gaze_log = []
        self.is_recording = False
        self.show_tracker = True
        self.cap = None
        self.last_valid_gaze = None  # Store last valid gaze position for blink handling
        self.smoothing_alpha = 0.7  # Exponential moving average factor (0.0-1.0, higher = less smoothing)
        self.smoothed_gaze = None  # For additional smoothing layer
        self.global_hotkeys_active = False  # Flag for global hotkey thread
        self.hotkey_thread = None  # Thread for monitoring global hotkeys
        self.should_exit = False  # Flag to signal exit
        
    def apply_noise_reduction(self, x, y):
        """
        Apply exponential moving average for additional noise reduction.
        This works on top of the Kalman filter for extra smoothness.
        """
        if self.smoothed_gaze is None:
            self.smoothed_gaze = (float(x), float(y))
            return int(x), int(y)
        
        # Exponential moving average
        prev_x, prev_y = self.smoothed_gaze
        new_x = self.smoothing_alpha * x + (1 - self.smoothing_alpha) * prev_x
        new_y = self.smoothing_alpha * y + (1 - self.smoothing_alpha) * prev_y
        
        self.smoothed_gaze = (new_x, new_y)
        return int(new_x), int(new_y)
        
    def setup_filter(self):
        """Initialize the selected filter."""
        if self.config.filter_type == "kalman":
            self.smoother = KalmanSmoother()
        elif self.config.filter_type == "kde":
            self.smoother = KDESmoother(self.screen_w, self.screen_h)
        elif self.config.filter_type == "none":
            self.smoother = NoSmoother()
        else:
            self.smoother = KalmanSmoother()  # Default fallback
    
    def setup_camera(self):
        """Initialize the camera."""
        self.cap = cv2.VideoCapture(self.config.camera_index)
        if not self.cap.isOpened():
            print(f"Error: Could not open camera with index {self.config.camera_index}.")
            return False
        return True

    def run_calibration(self):
        """Run the calibration sequence based on configuration."""
        print("\n" + "="*50)
        print("CALIBRATION SEQUENCE")
        print("="*50)
        
        # Wait for user to press SPACE to start
        if not wait_for_space_to_start(self.config.camera_index):
            print("Calibration cancelled.")
            return False
        
        # Step 1: N-point calibration
        print(f"\nStep 1: {self.config.num_points}-Point Calibration")
        print("Stay still and look at the dots as they appear.")
        if not run_n_point_calibration(self.estimator, self.config.num_points):
            return False
        
        # Step 2: Lissajous calibration (if enabled)
        if self.config.use_lissajous:
            print(f"\nStep 2: Lissajous Calibration ({self.config.lissajous_duration}s)")
            print("Follow the green dot as it moves along the curve.")
            if not run_lissajous_calibration(
                self.estimator, 
                self.config.camera_index
                #self.config.lissajous_coverage,
                #self.config.lissajous_speed
            ):
                print("Warning: Lissajous calibration failed, continuing anyway...")
        
        # Step 3: Filter tuning (if Kalman)
        if self.config.filter_type == "kalman" and isinstance(self.smoother, KalmanSmoother):
            print("\nStep 3: Tuning Kalman Filter")
            self.smoother.tune(self.estimator)
        
        print("\n" + "="*50)
        print("CALIBRATION COMPLETE")
        print("="*50 + "\n")
        return True
    
    def setup_overlay_window(self):
        """Create and configure the transparent overlay window."""
        window_name = "GazeOverlay"
        cv2.namedWindow(window_name, cv2.WND_PROP_FULLSCREEN)
        cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
        
        # Wait a moment for window to be created
        time.sleep(0.2)
        
        hwnd = win32gui.FindWindow(None, window_name)
        if hwnd:
            # Set extended window style for transparency and topmost
            style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            win32gui.SetWindowLong(
                hwnd, 
                win32con.GWL_EXSTYLE, 
                style | win32con.WS_EX_LAYERED | win32con.WS_EX_TOPMOST | win32con.WS_EX_TRANSPARENT
            )
            
            # Set layered window attributes for transparency
            win32gui.SetLayeredWindowAttributes(
                hwnd, win32api.RGB(0, 0, 0), 255, win32con.LWA_COLORKEY
            )
            
            # Force window to be topmost using SetWindowPos (more persistent)
            win32gui.SetWindowPos(
                hwnd,
                win32con.HWND_TOPMOST,  # Always on top
                0, 0, 0, 0,
                win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_SHOWWINDOW
            )
        
        return window_name
    
    def keep_window_on_top(self, window_name):
        """Periodically ensure the window stays on top."""
        try:
            hwnd = win32gui.FindWindow(None, window_name)
            if hwnd:
                # Re-apply topmost flag to ensure it stays on top
                win32gui.SetWindowPos(
                    hwnd,
                    win32con.HWND_TOPMOST,
                    0, 0, 0, 0,
                    win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE
                )
        except Exception:
            pass  # Silently fail if window doesn't exist
    
    def setup_global_hotkeys(self):
        """Setup global hotkeys that work even when window doesn't have focus."""
        if not HAS_KEYBOARD:
            print("Note: Global hotkeys require 'keyboard' library. Install with: pip install keyboard")
            return
        
        self.last_key_press_time = {'r': 0, 't': 0}  # Debounce timestamps
        KEY_DEBOUNCE_TIME = 0.2  # 200ms debounce
        
        def on_esc():
            """Handle ESC key press."""
            self.should_exit = True
        
        def on_r():
            """Handle R key press for recording toggle."""
            current_time = time.time()
            if current_time - self.last_key_press_time['r'] > KEY_DEBOUNCE_TIME:
                self.last_key_press_time['r'] = current_time
                self.is_recording = not self.is_recording
                print(f"Recording: {'STARTED' if self.is_recording else 'STOPPED'}")
        
        def on_t():
            """Handle T key press for tracker toggle."""
            current_time = time.time()
            if current_time - self.last_key_press_time['t'] > KEY_DEBOUNCE_TIME:
                self.last_key_press_time['t'] = current_time
                self.show_tracker = not self.show_tracker
                print(f"Tracker display: {'ON' if self.show_tracker else 'OFF'}")
        
        try:
            # Register global hotkeys using add_hotkey (better for global hotkeys)
            keyboard.add_hotkey('esc', on_esc, suppress=False)
            keyboard.add_hotkey('r', on_r, suppress=False)
            keyboard.add_hotkey('t', on_t, suppress=False)
            self.global_hotkeys_active = True
            print("Global hotkeys enabled: ESC, R, T work from anywhere")
        except Exception as e:
            print(f"Warning: Could not register global hotkeys: {e}")
            self.global_hotkeys_active = False
    
    def cleanup_global_hotkeys(self):
        """Clean up global hotkeys."""
        if HAS_KEYBOARD and self.global_hotkeys_active:
            try:
                keyboard.unhook_all_hotkeys()
                self.global_hotkeys_active = False
            except Exception:
                pass
    
    def draw_ui(self, overlay):
        """Draw UI elements on the overlay."""
        # Status text
        status_color = (0, 255, 0) if self.is_recording else (0, 0, 255)
        status_text = "RECORDING" if self.is_recording else "NOT RECORDING"
        cv2.putText(overlay, status_text, (50, 50), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1.5, status_color, 3)
        
        # Instructions
        instructions = [
            "[R] Start/Stop Recording",
            "[T] Toggle Tracker Display",
            "[ESC] Exit and Save"
        ]
        
        y_offset = 100
        for i, instruction in enumerate(instructions):
            cv2.putText(overlay, instruction, (50, y_offset + i * 40),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
    
    def save_gaze_data(self):
        """Save gaze data to CSV with unique filename."""
        if not self.gaze_log:
            print("No gaze data to save.")
            return
        
        # Generate unique filename
        base_filename = "gaze_data"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{base_filename}_{timestamp}.csv"
        counter = 1
        
        # Ensure filename is unique
        while os.path.exists(filename):
            filename = f"{base_filename}_{timestamp}_{counter}.csv"
            counter += 1
        
        df = pd.DataFrame(self.gaze_log, columns=["timestamp", "x", "y"])
        df.to_csv(filename, index=False)
        print(f"\nGaze data saved to: {filename}")
        return filename
    
    def run_tracking(self):
        """Main tracking loop."""
        window_name = self.setup_overlay_window()
        overlay = np.zeros((self.screen_h, self.screen_w, 3), dtype=np.uint8)
        
        print("\n" + "="*50)
        print("GAZE TRACKING ACTIVE")
        print("="*50)
        print("Controls:")
        print("  [R] - Start/Stop Recording")
        print("  [T] - Toggle Tracker Display")
        print("  [ESC] - Exit and Save")
        print("="*50 + "\n")
        
        # Setup global hotkeys
        self.setup_global_hotkeys()
        
        frame_count = 0
        while True:
            ret, frame = self.cap.read()
            if not ret:
                break
            
            # Periodically ensure window stays on top (every 30 frames ~ 1 second at 30fps)
            frame_count += 1
            if frame_count % 30 == 0:
                self.keep_window_on_top(window_name)
            
            overlay.fill(0)

            # --- MEJORA DE ROBUSTEZ: CLAHE ---

            gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            # Using CLAHE to improve bad illumination and contrast
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced_frame = clahe.apply(gray_frame)
            frame = cv2.cvtColor(enhanced_frame, cv2.COLOR_GRAY2BGR)

            features, blink = self.estimator.extract_features(frame)
            
            # Draw UI
            self.draw_ui(overlay)
            
            if not blink and features is not None:

                # Valid gaze data available
                raw_x, raw_y = self.estimator.predict([features])[0]
                
                # Apply smoothing filter
                if self.smoother:
                    smooth_x, smooth_y = self.smoother.step(int(raw_x), int(raw_y))
                else:
                    smooth_x, smooth_y = int(raw_x), int(raw_y)
                
                # Apply additional noise reduction (exponential moving average)
                smooth_x, smooth_y = self.apply_noise_reduction(smooth_x, smooth_y)

                # Update last valid gaze position
                self.last_valid_gaze = (smooth_x, smooth_y)
                
                # Log data if recording
                if self.is_recording:
                    self.gaze_log.append([time.time(), smooth_x, smooth_y])
                
                # Draw gaze dot if tracker is visible
                if self.show_tracker:
                    cv2.circle(overlay, (smooth_x, smooth_y), 15, (255, 255, 255), -1)
                    cv2.circle(overlay, (smooth_x, smooth_y), 8, (0, 0, 255), -1)
            elif self.last_valid_gaze is not None:
                # Blink detected - use last valid position
                smooth_x, smooth_y = self.last_valid_gaze
                
                # Log data if recording (with blink flag in comment or just use last position)
                if self.is_recording:
                    self.gaze_log.append([time.time(), smooth_x, smooth_y])
                
                # Draw gaze dot at last known position (slightly dimmed to indicate blink)
                if self.show_tracker:
                    cv2.circle(overlay, (smooth_x, smooth_y), 15, (128, 128, 128), -1)  # Gray when blinking
                    cv2.circle(overlay, (smooth_x, smooth_y), 8, (0, 0, 128), -1)


            # =========================================================
            # SHOW CAMERA
            # =========================================================

            cam_width, cam_height = 320, 240
            margin = 20

            # 1. Redimensionar el frame real de la webcam
            thumb = cv2.resize(frame, (cam_width, cam_height))

            # 2. Dibujar un borde blanco alrededor
            cv2.rectangle(thumb, (0, 0), (cam_width - 1, cam_height - 1), (255, 255, 255), 2)

            # 3. Pegar la matriz de la cámara sobre la matriz del overlay
            # Usamos índices negativos en NumPy para anclarlo a la esquina inferior derecha
            overlay[-cam_height - margin:-margin, -cam_width - margin:-margin] = thumb
            # =========================================================

            cv2.imshow(window_name, overlay)

            # Check for exit flag (set by global hotkey)
            if self.should_exit:
                break

            # Also check for local key presses (when window has focus)
            key = cv2.waitKey(1) & 0xFF
            if key == 27:  # ESC
                break
            elif key == ord('r') or key == ord('R'):
                self.is_recording = not self.is_recording
                print(f"Recording: {'STARTED' if self.is_recording else 'STOPPED'}")
            elif key == ord('t') or key == ord('T'):
                self.show_tracker = not self.show_tracker
                print(f"Tracker display: {'ON' if self.show_tracker else 'OFF'}")
        
        # Cleanup
        self.cleanup_global_hotkeys()
        if self.cap:
            self.cap.release()
        cv2.destroyAllWindows()

        # Save data
        if self.gaze_log:
            self.save_gaze_data()
    
    def run(self):
        """Run the complete gaze tracking pipeline."""
        # Setup filter and camera
        self.setup_filter()
        if not self.setup_camera():
            return

        # Run calibration
        if not self.run_calibration():
            print("Calibration failed. Exiting.")
            if self.cap:
                self.cap.release()
            return

        # Run tracking or evaluation
        if self.config.evaluation_mode:
            run_evaluation(self)
        else:
            self.run_tracking()

        # Final cleanup
        if self.cap:
            self.cap.release()
        cv2.destroyAllWindows()


def show_config_interface():
    """Display configuration interface and return configuration."""
    print("\n" + "="*60)
    print("GAZE TRACKER CONFIGURATION")
    print("="*60)
    print("\nPress [ENTER] for DEFAULT settings:")
    print("  - 25-point calibration")
    print("  - Kalman filter")
    print("\nPress [C] for CUSTOM settings")
    print("\nPress [E] for EVALUATION mode")
    print("="*60)
    
    choice = input("\nYour choice (ENTER/C/E): ").strip().lower()
    
    config = GazeTrackerConfig()
    
    if choice == 'e' or choice == 'evaluation':
        config.evaluation_mode = True
        print("\n--- EVALUATION MODE SELECTED ---")
        # Keep default calibration settings for evaluation

    elif choice == 'c' or choice == 'custom':
        print("\n--- CUSTOM CONFIGURATION ---")
        
        # Number of calibration points
        while True:
            try:
                num_points = input(f"Number of calibration points (default: {config.num_points}): ").strip()
                if num_points:
                    num_points = int(num_points)
                    # Check if it's a perfect square
                    side = int(np.sqrt(num_points))
                    if side * side != num_points:
                        print(f"Warning: {num_points} is not a perfect square. Using {side*side} instead.")
                        num_points = side * side
                    config.num_points = num_points
                break
            except ValueError:
                print("Invalid input. Please enter a number.")
        
        # Lissajous calibration
        lissajous_choice = input("Use Lissajous calibration? (y/n, default: y): ").strip().lower()
        config.use_lissajous = lissajous_choice != 'n'
        
        if config.use_lissajous:
            while True:
                try:
                    duration = input(f"Lissajous duration in seconds (default: {config.lissajous_duration}): ").strip()
                    if duration:
                        config.lissajous_duration = float(duration)
                    break
                except ValueError:
                    print("Invalid input. Please enter a number.")
            
            while True:
                try:
                    coverage = input(f"Screen coverage (0.4-0.5, default: {config.lissajous_coverage}): ").strip()
                    if coverage:
                        coverage_val = float(coverage)
                        if 0.4 <= coverage_val <= 0.5:
                            config.lissajous_coverage = coverage_val
                        else:
                            print("Coverage must be between 0.4 and 0.5")
                            continue
                    break
                except ValueError:
                    print("Invalid input. Please enter a number.")
            
            while True:
                try:
                    speed = input(f"Speed factor (0.3-1.0, default: {config.lissajous_speed}): ").strip()
                    if speed:
                        speed_val = float(speed)
                        if 0.3 <= speed_val <= 1.0:
                            config.lissajous_speed = speed_val
                        else:
                            print("Speed must be between 0.3 and 1.0")
                            continue
                    break
                except ValueError:
                    print("Invalid input. Please enter a number.")
        
        # Filter selection
        print("\nAvailable filters:")
        print("  1. Kalman (default)")
        print("  2. KDE")
        print("  3. None")
        filter_choice = input("Select filter (1/2/3, default: 1): ").strip()
        if filter_choice == '2':
            config.filter_type = "kde"
        elif filter_choice == '3':
            config.filter_type = "none"
        else:
            config.filter_type = "kalman"
    
    print("\n" + "="*60)
    print("CONFIGURATION SUMMARY")
    print("="*60)
    if config.evaluation_mode:
        print("  Mode: Evaluation")
    else:
        print("  Mode: Tracking")
    print(f"  Calibration points: {config.num_points}")
    print(f"  Lissajous: {'Yes' if config.use_lissajous else 'No'}", end="")
    if config.use_lissajous:
        print(f" ({config.lissajous_duration}s, coverage: {config.lissajous_coverage:.2f}, speed: {config.lissajous_speed:.2f})")
    else:
        print()
    print(f"  Filter: {config.filter_type}")
    print("="*60 + "\n")
    
    return config


if __name__ == "__main__":
    # Show configuration interface
    config = show_config_interface()

    # Create and run tracker
    tracker = GazeTracker(config)
    tracker.run()
