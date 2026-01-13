import cv2
import os
import numpy as np
from ultralytics import YOLO
from deep_sort_realtime.deepsort_tracker import DeepSort
import yaml
import easyocr
import requests
from datetime import datetime

# --- Load config ---
with open(r"C:\\Users\\HP\\Desktop\\parktrack\\major\\plate\\config.yaml", "r") as f:
    cfg = yaml.safe_load(f)

# Flask API endpoint
API_URL = "http://localhost:5000/api"

# --- Helper function to call Flask API ---
def send_vehicle_entry(track_id, vehicle_type, license_plate):
    """Send vehicle entry to Flask API"""
    try:
        response = requests.post(f"{API_URL}/vehicle/entry", json={
            'track_id': track_id,
            'vehicle_type': vehicle_type,
            'license_plate': license_plate
        })
        if response.status_code == 200:
            print(f"✅ Entry recorded: Track {track_id} ({vehicle_type})")
        return response.json()
    except Exception as e:
        print(f"❌ Error recording entry: {e}")
        return None

def send_vehicle_exit(track_id):
    """Send vehicle exit to Flask API"""
    try:
        response = requests.post(f"{API_URL}/vehicle/exit", json={
            'track_id': track_id
        })
        if response.status_code == 200:
            data = response.json()
            print(f"💰 Exit recorded: Track {track_id}")
            print(f"   Duration: {data.get('total_hours', 0):.2f} hours")
            print(f"   Fee: Rs. {data.get('parking_fee', 0):.2f}")
        return response.json()
    except Exception as e:
        print(f"❌ Error recording exit: {e}")
        return None

# --- 1. Load YOLOv8 models ---
vehicle_model = YOLO(cfg["vehicle_model_path"]).to("cuda")
license_model = YOLO(cfg["license_model_path"]).to("cuda")

# --- 2. Initialize DeepSORT tracker ---
tracker = DeepSort(max_age=5, n_init=3, max_iou_distance=0.7)

# --- 3. Define tracked classes and colors ---
tracked_classes = {int(k): v for k, v in cfg["tracked_classes"].items()}
class_colors = {
    0: (255,0,0),
    2: (0,255,0),
    3: (0,255,255),
    6: (255,0,0),
    8: (0,0,255),
}

# --- 4. Setup counters and storage ---
os.makedirs(cfg["plate_output_dir"], exist_ok=True)
point1 = tuple(cfg["entry_line"][0])
point2 = tuple(cfg["entry_line"][1])

# Line equation parameters
x1_line, y1_line = point1
x2_line, y2_line = point2
if x2_line - x1_line != 0:
    m = (y2_line - y1_line) / (x2_line - x1_line)
    b = y1_line - m * x1_line
else:
    m = float('inf')  # vertical line
    b = None

in_counts = {name:0 for name in tracked_classes.values()}

first_bottom_center = {}
crossed_lines = {}
db_recorded = {}  # Track which vehicles have been recorded in DB

# --- Video setup ---
cap = cv2.VideoCapture(cfg["video_input_path"])
if not cap.isOpened():
    print("Error opening video!")
    exit()

width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
fps = int(cap.get(cv2.CAP_PROP_FPS))

cv2.namedWindow("Tracking + License Plate", cv2.WINDOW_NORMAL)
cv2.resizeWindow("Tracking + License Plate", width, height)

fourcc = cv2.VideoWriter_fourcc(*"mp4v")
out = cv2.VideoWriter(cfg["video_output_path"], fourcc, fps, (width, height))

frame_id = 0
lp_checked = {}
best_lp_per_track = {}
lp_numbers_per_track = {}

# --- EasyOCR reader ---
reader = easyocr.Reader(['en'])

print("🚀 Starting vehicle tracking with database integration...")
print(f"📡 Connected to Flask API at {API_URL}")

# --- Main loop ---
while True:
    ret, frame = cap.read()
    if not ret:
        break

    # --- Vehicle detection ---
    results = vehicle_model(frame, conf=cfg["confidence_threshold"], imgsz=cfg["imgsz"])[0]

    detections = []
    for box in results.boxes:
        cls_id = int(box.cls[0])
        if cls_id in tracked_classes:
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            w, h = x2 - x1, y2 - y1
            conf = float(box.conf[0])
            detections.append(([x1, y1, w, h], conf, cls_id))

    # --- Update tracks ---
    tracks = tracker.update_tracks(detections, frame=frame)
    counts = {name:0 for name in tracked_classes.values()}

    for track in tracks:
        if not track.is_confirmed():
            continue

        tid = track.track_id
        x1, y1, x2, y2 = map(int, track.to_ltrb())
        cls_id = track.get_det_class()
        c_name = tracked_classes[cls_id]
        counts[c_name] += 1

        col = class_colors.get(cls_id, (255,255,255))
        cv2.rectangle(frame, (x1,y1), (x2,y2), col, 2)
        cv2.putText(frame, f"{c_name} ID:{tid}", (x1,y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, col,2)

        # --- Bottom-center of vehicle ---
        cx, cy = (x1 + x2)//2, y2

        # Initialize previous point
        if tid not in first_bottom_center:
            first_bottom_center[tid] = (cx, cy)
            crossed_lines[tid] = False
            continue

        prev_cx, prev_cy = first_bottom_center[tid]

        # --- Check crossing ---
        if m != float('inf'):
            y_on_line = m * cx + b
            if prev_cy < y_on_line <= cy and not crossed_lines[tid]:
                in_counts[c_name] += 1
                crossed_lines[tid] = True
                
                # Record entry in database
                if tid not in db_recorded:
                    license_plate = lp_numbers_per_track.get(tid, 'Detecting...')
                    send_vehicle_entry(tid, c_name, license_plate)
                    db_recorded[tid] = True
        else:  # vertical line
            if prev_cx < x1_line <= cx and not crossed_lines[tid]:
                in_counts[c_name] += 1
                crossed_lines[tid] = True
                
                # Record entry in database
                if tid not in db_recorded:
                    license_plate = lp_numbers_per_track.get(tid, 'Detecting...')
                    send_vehicle_entry(tid, c_name, license_plate)
                    db_recorded[tid] = True

        first_bottom_center[tid] = (cx, cy)

        # --- Draw track line ---
        cv2.line(frame, (prev_cx, prev_cy), (cx, cy), col, 2)

        # --- License Plate Detection ---
        if cls_id in [2,3,6,8]:
            if tid not in lp_checked or frame_id - lp_checked[tid] > 15:
                lp_checked[tid] = frame_id
                car_roi = frame[y1:y2, x1:x2]
                if car_roi.size==0:
                    continue
                car_roi_rgb = cv2.cvtColor(car_roi, cv2.COLOR_BGR2RGB)
                lp_res = license_model(car_roi_rgb)[0]

                for lp_box in lp_res.boxes:
                    conf = float(lp_box.conf[0]) if hasattr(lp_box, 'conf') else 1.0
                    if conf < 0.3:
                        continue
                    lx1, ly1, lx2, ly2 = map(int, lp_box.xyxy[0])
                    ax1 = max(0, lx1 + x1)
                    ay1 = max(0, ly1 + y1)
                    ax2 = min(width-1, lx2 + x1)
                    ay2 = min(height-1, ly2 + y1)
                    if ax2-ax1<20 or ay2-ay1<10:
                        continue

                    lp_crop = frame[ay1:ay2, ax1:ax2]
                    area = (ax2-ax1)*(ay2-ay1)

                    # --- Keep only the largest LP per track ---
                    if tid not in best_lp_per_track or area > best_lp_per_track[tid]["area"]:
                        best_lp_per_track[tid] = {"area": area, "image": lp_crop.copy()}

                        # --- Run OCR on this largest crop ---
                        lp_crop_rgb = cv2.cvtColor(lp_crop, cv2.COLOR_BGR2RGB)
                        ocr_result = reader.readtext(lp_crop_rgb)
                        lp_text = ''
                        if ocr_result:
                            lp_text = max(ocr_result, key=lambda x: (x[0][1][0]-x[0][0][0])*(x[0][2][1]-x[0][1][1]))[1]
                            lp_text = ''.join(filter(str.isalnum, lp_text))
                        lp_numbers_per_track[tid] = lp_text

                    cv2.rectangle(frame, (ax1, ay1), (ax2, ay2), (255,255,0),2)
                    cv2.putText(frame, lp_text, (ax1, ay1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,255,0),2)

    # --- Draw line and counts ---
    if cfg.get("draw_lines", True):
        cv2.line(frame, point1, point2, (0,0,255), 2)
        cv2.putText(frame, "Entry Line", (point1[0], point1[1]-10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,0,255), 2)

        # Current counts
        y_off = 30
        for name, cnt in counts.items():
            cv2.putText(frame, f"{name}s: {cnt}", (10, y_off), cv2.FONT_HERSHEY_SIMPLEX,0.6,(0,255,255),2)
            y_off += 25

        # Total IN counts
        x_off = width - 200
        y_off = 30
        for name in tracked_classes.values():
            tin = f"{name} IN: {in_counts[name]}"
            tiw, _ = cv2.getTextSize(tin, cv2.FONT_HERSHEY_SIMPLEX,0.6,2)[0]
            cv2.rectangle(frame, (x_off-10, y_off-20), (x_off+tiw+10, y_off+5), (0,0,0),-1)
            cv2.putText(frame, tin, (x_off, y_off), cv2.FONT_HERSHEY_SIMPLEX,0.6,(0,255,0),2)
            y_off += 30

    cv2.imshow("Tracking + License Plate", frame)
    out.write(frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

    frame_id += 1

cap.release()
out.release()
cv2.destroyAllWindows()

# Save license plate images
for tid, crop in best_lp_per_track.items():
    lp_img = crop["image"]
    if lp_img.size > 0:
        cv2.imwrite(f"{cfg['plate_output_dir']}/car{tid}.jpg", lp_img)

# --- Save LP numbers to file ---
with open(f"{cfg['plate_output_dir']}/lp_numbers.txt", "w") as f:
    for tid, lp_num in lp_numbers_per_track.items():
        f.write(f"Track {tid}: {lp_num}\n")

print("\n✅ Processing complete!")
print(f"📊 Total vehicles tracked: {len(db_recorded)}")
print(f"🔢 License plates detected: {len(lp_numbers_per_track)}")