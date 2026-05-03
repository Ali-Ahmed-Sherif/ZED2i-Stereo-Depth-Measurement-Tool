#!/usr/bin/env python3
# ZED SDK 3.8 compatible - Enhanced Version
# Supports clicking on BOTH LEFT (RGB) and DEPTH panels
# SVO recording (p = start/stop) and snapshots (s = save)
# Python 3.6+

import cv2
import numpy as np
import pyzed.sl as sl
import argparse
import socket
import sys
import os
from datetime import datetime

AVG_WIN = 5
MIN_SAMPLES = 5

# ---------------- HELPERS ----------------
def ts_now() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S_%f")

def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)

# ---------------- ARGPARSE ----------------
def parse_args():
    parser = argparse.ArgumentParser(description="ZED local / stream distance tool")
    parser.add_argument(
        "--stream",
        type=str,
        #default="192.168.33.1:30000",
        help="Receive ZED stream in format ip:port (example: 192.168.1.50:30000)"
    )
    parser.add_argument('--input_svo_file', type=str, help='Path to an .svo file', default='')
    # Add this line:
    parser.add_argument('--start_frame', type=int, help='Starting frame index for SVO playback', default=0)
    return parser.parse_args()

def parse_ip_port(value):
    try:
        ip, port = value.split(":")
        socket.inet_aton(ip)
        return ip, int(port)
    except Exception:
        raise argparse.ArgumentTypeError("Stream must be in format ip:port")

# ---------------- GLOBAL STATE ----------------
clicks_xy = []      # (x, y, panel) where panel = 'left' or 'depth'
clicks_xyz = []     # 3D coordinates
dist_cm = None
msg = "LIVE | Click 2 points on either panel | f=freeze | c=clear | q=quit"
left_w = 0
panel_h = 0
frozen = False
recording = False
L = None
Dvis = None
pc = None

# ---------------- HELPER FUNCTIONS ----------------
def xyz_avg(pc_mat, x, y, win=5):
    """
    Average 3D coordinates in a window around (x, y)
    Returns None if insufficient valid points
    """
    h, w = pc_mat.get_height(), pc_mat.get_width()
    if h == 0 or w == 0:
        return None

    half = win // 2
    pts = []

    for yy in range(max(0, y-half), min(h, y+half+1)):
        for xx in range(max(0, x-half), min(w, x+half+1)):
            err, val = pc_mat.get_value(xx, yy)
            if err != sl.ERROR_CODE.SUCCESS:
                continue

            X, Y, Z = float(val[0]), float(val[1]), float(val[2])
            if not (np.isfinite(X) and np.isfinite(Y) and np.isfinite(Z)):
                continue
            if Z <= 0:
                continue

            pts.append([X, Y, Z])

    if len(pts) < MIN_SAMPLES:
        return None

    return np.mean(np.array(pts, dtype=np.float32), axis=0)

def on_mouse(event, x, y, flags, param):
    """
    Enhanced mouse callback - works on BOTH panels
    """
    global dist_cm, msg, left_w, panel_h, clicks_xy, clicks_xyz

    if event != cv2.EVENT_LBUTTONDOWN:
        return

    # Validate y coordinate
    if panel_h <= 0 or y < 0 or y >= panel_h:
        msg = "Click inside the image area"
        return

    # Check if already have 2 points
    if len(clicks_xy) >= 2:
        msg = "Already 2 points. Press 'c' to clear."
        return

    # Determine which panel was clicked and get coordinates
    if x < left_w:
        # LEFT PANEL (RGB image)
        panel = 'left'
        img_x, img_y = x, y
        display_x = x
    else:
        # DEPTH PANEL
        panel = 'depth'
        img_x = x - left_w
        img_y = y
        display_x = x

        if img_x < 0:
            msg = "Click inside the image area"
            return

    # Get 3D coordinates from point cloud
    p = xyz_avg(pc, img_x, img_y, AVG_WIN)
    if p is None:
        msg = f"Invalid depth at this point on {panel.upper()} panel (try textured area)"
        return

    # Store the click
    clicks_xy.append((display_x, img_y, panel))
    clicks_xyz.append(np.array(p, dtype=np.float32))

    # Update message
    if len(clicks_xyz) == 1:
        panel_name = "LEFT" if panel == 'left' else "DEPTH"
        msg = (f"FROZEN | Point 1 on {panel_name} | click Point 2 on any panel"
               if frozen else f"LIVE | Point 1 on {panel_name} | click Point 2 on any panel")

    # Calculate distance if we have 2 points
    if len(clicks_xyz) == 2:
        dist_cm = float(np.linalg.norm(clicks_xyz[1] - clicks_xyz[0]) * 100.0)
        p1_panel = "LEFT" if clicks_xy[0][2] == 'left' else "DEPTH"
        p2_panel = "LEFT" if clicks_xy[1][2] == 'left' else "DEPTH"
        msg = (f"FROZEN | Distance = {dist_cm:.2f} cm ({p1_panel} → {p2_panel}) | r=resume | c=clear"
               if frozen else f"LIVE | Distance = {dist_cm:.2f} cm ({p1_panel} → {p2_panel}) | f=freeze | c=clear")

# ---------------- MAIN PROGRAM ----------------
args = parse_args()

# Prepare output directories
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SCREENSHOTS_DIR = os.path.join(SCRIPT_DIR, "screenshots")
SVO_DIR = os.path.join(SCRIPT_DIR, "svo_recording")
ensure_dir(SCREENSHOTS_DIR)
ensure_dir(SVO_DIR)

# Initialize ZED Camera
zed = sl.Camera()
init = sl.InitParameters()
init.coordinate_units = sl.UNIT.METER
init.depth_mode = sl.DEPTH_MODE.NEURAL_PLUS
#init.optional_opencv_calibration_file = r"C:\Users\Ali Ahmed\OneDrive - Alexandria National University\Desktop\Mate2026\vision_2026_Tasks\All\calib\calibration6_underwater.yaml"

# Recommended when you want to rely only on your custom underwater calibration
#init.camera_disable_self_calib = True

# Set source (stream, SVO file, or local camera)
if args.stream:
    ip, port = parse_ip_port(args.stream)
    print(f"[Receiver] Connecting to ZED stream {ip}:{port}")
    init.set_from_stream(ip, port)
elif args.input_svo_file:
    print(f"[SVO] Opening SVO file {args.input_svo_file}")
    init.set_from_svo_file(args.input_svo_file)
    init.svo_real_time_mode = False
else:
    print("[Local] Opening local ZED camera")
    init.camera_resolution = sl.RESOLUTION.HD1080
    init.camera_fps = 30

# Open camera
status = zed.open(init)
if status != sl.ERROR_CODE.SUCCESS:
    print(f"ZED open failed: {status.name}")
    sys.exit(1)
# --- ADD THIS SECTION HERE ---
if args.input_svo_file and args.start_frame > 0:
    print(f"[SVO] Seeking to frame: {args.start_frame}")
    zed.set_svo_position(args.start_frame)
# Runtime parameters
runtime = sl.RuntimeParameters(confidence_threshold=95)

# Data containers
img_left = sl.Mat()
depth_vis = sl.Mat()
pc = sl.Mat()

# Setup window
cv2.namedWindow("LEFT | DEPTH", cv2.WINDOW_NORMAL)
cv2.resizeWindow("LEFT | DEPTH", 1280, 720)
cv2.setMouseCallback("LEFT | DEPTH", on_mouse)

print("\n" + "="*60)
print("CONTROLS:")
print("  Click anywhere on LEFT or DEPTH panel to place points")
print("  'f' = Freeze display")
print("  'r' = Resume (when frozen)")
print("  'c' = Clear distance points")
print("  'p' = Start / Stop SVO recording  →  svo_recording/")
print("  's' = Snapshot of LEFT frame      →  screenshots/")
print("  'q' = Quit")
print("="*60 + "\n")

# Main loop
while True:
    # ------------------------------------------------------------------ #
    #  Grab logic:                                                         #
    #   - When live (not frozen): always grab to update display + record   #
    #   - When frozen + recording: still grab so SVO keeps writing frames  #
    #     but do NOT update L / Dvis / pc (display stays frozen)           #
    #   - When frozen + not recording: skip grab entirely                  #
    # ------------------------------------------------------------------ #
    should_grab = (not frozen) or recording

    if should_grab:
        err = zed.grab(runtime)

        if err == sl.ERROR_CODE.END_OF_SVOFILE_REACHED:
            print("End of SVO file reached. Exiting...")
            break

        if err == sl.ERROR_CODE.SUCCESS:
            if not frozen:
                # Update display frames only when not frozen
                zed.retrieve_image(img_left, sl.VIEW.LEFT)
                zed.retrieve_image(depth_vis, sl.VIEW.DEPTH)
                zed.retrieve_measure(pc, sl.MEASURE.XYZRGBA)

                L = img_left.get_data()
                Dvis = depth_vis.get_data()

                if L is None or Dvis is None or L.size == 0 or Dvis.size == 0:
                    pass  # keep last valid frames
                else:
                    L = cv2.cvtColor(L, cv2.COLOR_BGRA2BGR)
                    Dvis = cv2.cvtColor(Dvis, cv2.COLOR_BGRA2BGR)

                    if L.shape[0] != Dvis.shape[0]:
                        Dvis = cv2.resize(Dvis, (L.shape[1], L.shape[0]),
                                          interpolation=cv2.INTER_NEAREST)

                    left_w = L.shape[1]
                    panel_h = L.shape[0]
            # When frozen + recording: grab() was called (SVO writes the frame),
            # but we intentionally skip retrieve_image / retrieve_measure
            # so the display and point cloud stay frozen.

    if L is None or Dvis is None:
        continue

    # ------------------------------------------------------------------ #
    #  Build display                                                       #
    # ------------------------------------------------------------------ #
    L_show = L.copy()
    D_show = Dvis.copy()

    # Draw distance points on appropriate panels
    for i, (display_x, img_y, panel) in enumerate(clicks_xy):
        if panel == 'left':
            cv2.circle(L_show, (display_x, img_y), 2, (0, 255, 0), -1)
            cv2.putText(L_show, f"P{i+1}", (display_x + 8, img_y - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        else:
            depth_x = display_x - left_w
            cv2.circle(D_show, (depth_x, img_y), 2, (0, 255, 0), -1)
            cv2.putText(D_show, f"P{i+1}", (depth_x + 8, img_y - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

    # Draw line and distance label if we have 2 points
    if len(clicks_xy) == 2 and dist_cm is not None:
        (x1, y1, p1), (x2, y2, p2) = clicks_xy

        both_temp = np.hstack([L_show, D_show])
        cv2.line(both_temp, (x1, y1), (x2, y2), (0, 255, 0), 2)

        mx, my = (x1 + x2) // 2, (y1 + y2) // 2
        text = f"{dist_cm:.2f} cm"
        cv2.putText(both_temp, text, (mx + 10, my),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 255), 2)

        L_show = both_temp[:, :left_w]
        D_show = both_temp[:, left_w:]

    # Combine panels side by side
    both = np.hstack([L_show, D_show])

    # Separator line
    cv2.line(both, (left_w, 0), (left_w, both.shape[0] - 1), (0, 255, 0), 2)

    # Panel labels
    cv2.rectangle(both, (10, 5), (150, 35), (0, 0, 0), -1)
    cv2.putText(both, "Left (RGB)", (15, 25),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    cv2.rectangle(both, (left_w + 10, 5), (left_w + 150, 35), (0, 0, 0), -1)
    cv2.putText(both, "DEPTH", (left_w + 15, 25),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

    # Recording indicator (top-right, red)
    if recording:
        h, w = both.shape[:2]
        cv2.circle(both, (w - 30, 20), 12, (0, 0, 200), -1)
        cv2.putText(both, "REC", (w - 80, 27),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

    # Freeze indicator
    if frozen:
        cv2.putText(both, "FROZEN", (both.shape[1] // 2 - 60, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 165, 255), 2)

    # Status / help text
    if frozen:
        help_line = "FROZEN | r=resume | s=snapshot | p=rec toggle | c=clear | q=quit"
    else:
        help_line = "LIVE | f=freeze | s=snapshot | p=rec toggle | c=clear | q=quit"

    cv2.putText(both, help_line, (20, 60),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    cv2.putText(both, msg, (20, 85),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

    cv2.imshow("LEFT | DEPTH", both)

    # ------------------------------------------------------------------ #
    #  Keyboard handling                                                   #
    # ------------------------------------------------------------------ #
    k = cv2.waitKey(1) & 0xFF

    # --- q: Quit ---
    if k == ord('q'):
        print("Quitting...")
        break

    # --- c: Clear distance points ---
    if k == ord('c'):
        clicks_xy.clear()
        clicks_xyz.clear()
        dist_cm = None
        msg = ("FROZEN | Cleared. Click 2 points on any panel"
               if frozen else "LIVE | Cleared. Click 2 points on any panel")

    # --- f: Freeze display ---
    if k == ord('f') and not frozen:
        frozen = True
        msg = "FROZEN | Frame captured. Click 2 points on any panel | r=resume"

    # --- r: Resume (clears points) ---
    if k == ord('r') and frozen:
        frozen = False
        clicks_xy.clear()
        clicks_xyz.clear()
        dist_cm = None
        msg = "LIVE | Resumed. Click 2 points on any panel | f=freeze | c=clear"

    # --- p: Toggle SVO recording ---
    # Recording continues even when display is frozen (grab() still runs)
    if k == ord('p'):
        if not recording:
            svo_name = f"recording_{ts_now()}.svo"
            svo_path = os.path.join(SVO_DIR, svo_name)
            rec_param = sl.RecordingParameters(svo_path, sl.SVO_COMPRESSION_MODE.H264)
            rec_err = zed.enable_recording(rec_param)
            if rec_err == sl.ERROR_CODE.SUCCESS:
                recording = True
                print(f"[REC] Started: {svo_path}")
                msg = f"Recording started → {svo_name}"
            else:
                print(f"[REC] Failed to start recording: {rec_err.name}")
                msg = "Recording FAILED to start (see console)"
        else:
            zed.disable_recording()
            recording = False
            print("[REC] Stopped.")
            msg = "Recording stopped"

    # --- s: Snapshot of LEFT frame ---
    # Works whether frozen or live — always uses the current L buffer
    if k == ord('s'):
        if L is not None:
            snap_name = f"snapshot_{ts_now()}.jpg"
            snap_path = os.path.join(SCREENSHOTS_DIR, snap_name)
            ok = cv2.imwrite(snap_path, L, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
            if ok:
                print(f"[SNAP] Saved: {snap_path}")
                msg = f"Snapshot saved → {snap_name}"
            else:
                print(f"[SNAP] FAILED: {snap_path}")
                msg = "Snapshot FAILED (see console)"
        else:
            msg = "No frame available for snapshot yet"

# ------------------------------------------------------------------ #
#  Cleanup                                                            #
# ------------------------------------------------------------------ #
if recording:
    zed.disable_recording()
    print("[REC] Recording stopped on exit.")

cv2.destroyAllWindows()
zed.close()
print("Program ended.")