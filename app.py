import time
import random
import threading
from flask import Flask, render_template, jsonify, request
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

app = Flask(__name__)

# Global Factory States
state = "STOPPED"  # STOPPED, RUNNING, FAULTED
totals_produced = 0
defects_count = 0
consecutive_defects = 0
temperature = 22.0
lock = threading.Lock()

# Connect to InfluxDB (Docker coordinates)
try:
    client = InfluxDBClient(url="http://influxdb:8086", token="my-super-secret-auth-token", org="srh")
    write_api = client.write_api(write_options=SYNCHRONOUS)
except Exception as e:
    print(f"Database waiting... {e}")

def production_loop():
    global state, totals_produced, defects_count, consecutive_defects, temperature
    while True:
        time.sleep(2)  # Simulate a 2-second machine cycle
        with lock:
            if state != "RUNNING":
                continue
            
            # 1. Simulate environmental temperature fluctuations
            temperature += random.uniform(-0.5, 0.5)
            temperature = max(18.0, min(26.0, temperature))
            
           # 2. Simulate 4-Stage Pencil Assembly Quality Checks
            is_defective = False
            defect_reason = "NONE"
            
            # Roll dice for a failure occurrence
            if random.random() < 0.05:  
                is_defective = True
                # Pick a specific failure criteria matching your 4 stages
                defect_reason = random.choice([
                    "STAGE 1: Graphite core diameter out of bounds (ø > 2.1mm)",
                    "STAGE 2: Wooden body alignment warp detected",
                    "STAGE 3: Eraser missing or seated below depth tolerance",
                    "STAGE 4: Ferrule crimping torque limits exceeded"
                ])

            if is_defective:
                defects_count += 1
                consecutive_defects += 1
                print(f"[ALARM] Defect Rejected! Reason: {defect_reason}") # <--- Logs to Docker console
                if consecutive_defects >= 3:
                    state = "FAULTED"
            else:
                totals_produced += 1
                consecutive_defects = 0
                
            # 3. Stream Telemetry to InfluxDB
            try:
                point = Point("pencil_line") \
                    .field("temperature", float(temperature)) \
                    .field("machine_state", str(state)) \
                    .field("parts_produced", int(totals_produced)) \
                    .field("defects", int(defects_count))
                write_api.write(bucket="pencil_bucket", record=point)
            except Exception as e:
                print(f"Logging error: {e}")

# Start the background simulator thread
threading.Thread(target=production_loop, daemon=True).start()

@app.route('/')
def hmi_dashboard():
    return render_template('index.html')

@app.route('/status', methods=['GET'])
def get_status():
    with lock:
        return jsonify({
            "state": state,
            "produced": totals_produced,
            "defects": defects_count,
            "temperature": round(temperature, 2)
        })

@app.route('/control', methods=['POST'])
def control_factory():
    global state, consecutive_defects
    action = request.json.get("action")
    with lock:
        if action == "START" and state != "FAULTED":
            state = "RUNNING"
        elif action == "STOP":
            state = "STOPPED"
        elif action == "RESET":
            state = "STOPPED"
            consecutive_defects = 0
        return jsonify({"status": "success", "current_state": state})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
