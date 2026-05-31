from flask import Flask, request, jsonify, render_template_string
import serial
import time
import json
import threading

SERIAL_PORT = "COM3"
BAUD_RATE = 115200
JOG_SPEED = 160

ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.1)
time.sleep(2)

app = Flask(__name__)
teach_points = []
serial_lock = threading.Lock()


def send_cmd(cmd, read_reply=False, wait=0.03):
    print("[SEND]", cmd)

    with serial_lock:
        ser.write((cmd + "\n").encode())
        time.sleep(wait)

        lines = []
        if read_reply:
            while ser.in_waiting:
                line = ser.readline().decode(errors="ignore").strip()
                if line:
                    print("[ARDUINO]", line)
                    lines.append(line)

        return lines


def get_position():
    with serial_lock:
        ser.reset_input_buffer()
        ser.write(b"POS\n")
        time.sleep(0.05)

        while ser.in_waiting:
            line = ser.readline().decode(errors="ignore").strip()
            print("[ARDUINO]", line)

            if line.startswith("POS"):
                try:
                    return int(line.split()[1])
                except:
                    return None

    return None


@app.route("/")
def index():
    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>超长臂一轴示教</title>

<style>
html, body, * {
    user-select:none !important;
    -webkit-user-select:none !important;
    -webkit-touch-callout:none !important;
}

body {
    text-align:center;
    font-family:Arial;
    background:#f2f2f2;
}

button {
    width:160px;
    height:70px;
    font-size:24px;
    margin:10px;
    border-radius:12px;
    touch-action:none;
    -webkit-user-select:none;
}

.small {
    width:140px;
    height:55px;
    font-size:18px;
}

#pos {
    font-size:28px;
    margin:20px;
    color:blue;
}

#points {
    background:white;
    padding:10px;
    margin:10px;
}
</style>
</head>

<body>

<h2>超长臂一轴示教</h2>

<div id="pos">当前位置：--</div>

<div>
<button onpointerdown="jogStart('FWD')" 
        onpointerup="jogStop()" 
        onpointercancel="jogStop()">
    <span style="pointer-events:none;">前进</span>
</button>

<button onpointerdown="jogStart('REV')" 
        onpointerup="jogStop()" 
        onpointercancel="jogStop()">
    <span style="pointer-events:none;">后退</span>
</button>
</div>

<div>
<button class="small" onclick="forceStop()">急停</button>
<button class="small" onclick="zeroPos()">清零</button>
</div>

<div>
<button class="small" onclick="recordPoint()">记录点</button>
<button class="small" onclick="clearPoints()">清空</button>
</div>

<div>
<button class="small" onclick="savePoints()">保存</button>
<button class="small" onclick="replayPath()">回放</button>
</div>

<div id="points">路径点：[]</div>

<script>
let isJogging = false;
let pollingEnabled = true;

function jogStart(dir) {
    if (isJogging) return;

    isJogging = true;
    pollingEnabled = false;

    fetch('/jog_start', {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({dir:dir})
    });
}

function jogStop() {
    if (!isJogging) return;

    isJogging = false;

    fetch('/jog_stop', {method:'POST'})
    .then(() => {
        pollingEnabled = true;
        setTimeout(updatePos, 200);
    });
}

function forceStop() {
    isJogging = false;
    pollingEnabled = true;
    fetch('/jog_stop', {method:'POST'})
    .then(() => updatePos());
}

function updatePos() {
    if (!pollingEnabled) return;

    fetch('/pos')
    .then(r=>r.json())
    .then(d=>{
        document.getElementById('pos').innerHTML =
            "当前位置：" + d.pos + " pulse";
    });
}

function zeroPos() {
    fetch('/zero',{method:'POST'})
    .then(()=>updatePos());
}

function recordPoint() {
    fetch('/record',{method:'POST'})
    .then(r=>r.json())
    .then(d=>{
        document.getElementById('points').innerHTML =
            "路径点：" + JSON.stringify(d.points);
    });
}

function clearPoints() {
    fetch('/clear',{method:'POST'})
    .then(r=>r.json())
    .then(d=>{
        document.getElementById('points').innerHTML = "路径点：[]";
    });
}

function savePoints() {
    fetch('/save',{method:'POST'})
    .then(r=>r.json())
    .then(d=>alert(d.msg));
}

function replayPath() {
    if(confirm("确认开始回放路径？")) {
        pollingEnabled = false;

        fetch('/replay',{method:'POST'})
        .then(r=>r.json())
        .then(d=>{
            alert(d.msg);
            pollingEnabled = true;
            updatePos();
        });
    }
}

setInterval(updatePos, 3000);
updatePos();
</script>

</body>
</html>
""")


@app.route("/jog_start", methods=["POST"])
def jog_start():
    data = request.json
    direction = data.get("dir", "FWD")

    if direction == "FWD":
        send_cmd(f"FWD {JOG_SPEED}")
    else:
        send_cmd(f"REV {JOG_SPEED}")

    return jsonify({"ok": 1})


@app.route("/jog_stop", methods=["POST"])
def jog_stop():
    send_cmd("STOP")
    return jsonify({"ok": 1})


@app.route("/pos")
def pos():
    p = get_position()
    return jsonify({"pos": p if p is not None else "未知"})


@app.route("/zero", methods=["POST"])
def zero():
    send_cmd("ZERO")
    teach_points.clear()
    return jsonify({"ok": 1})


@app.route("/record", methods=["POST"])
def record():
    p = get_position()
    if p is not None:
        teach_points.append(p)
        print("[RECORD]", p)

    return jsonify({"points": teach_points})


@app.route("/clear", methods=["POST"])
def clear():
    teach_points.clear()
    return jsonify({"points": teach_points})


@app.route("/save", methods=["POST"])
def save():
    with open("teach_path.json", "w") as f:
        json.dump(teach_points, f, indent=2)

    return jsonify({"msg": "路径已保存到 teach_path.json"})


@app.route("/replay", methods=["POST"])
def replay():
    if not teach_points:
        return jsonify({"msg": "没有路径点，请先记录点"})

    for i, target in enumerate(teach_points):
        print(f"[MOVE] 第{i+1}点，目标={target}")

        send_cmd(f"MOVE {target} {JOG_SPEED}")

        timeout = time.time() + 40

        while time.time() < timeout:
            pos = get_position()

            if pos is not None and abs(pos - target) <= 8:
                send_cmd("STOP")
                time.sleep(0.2)
                break

            time.sleep(0.08)

        else:
            send_cmd("STOP")
            return jsonify({
                "msg": f"第{i+1}点超时，目标={target}，当前位置={pos}"
            })

    return jsonify({"msg": "路径回放完成"})


if __name__ == "__main__":
    print("系统已就绪")
    print("手机访问：http://电脑IP:5000")
    app.run(host="0.0.0.0", port=5000, threaded=True, debug=False)
