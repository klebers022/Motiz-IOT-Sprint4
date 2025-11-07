# moto_server.py
import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

import time, threading, json
from collections import deque, defaultdict
from typing import Dict, Any, List
import numpy as np
import cv2

from ultralytics import YOLO
import supervision as sv

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# ----------------- CONFIG -----------------
VIDEO_SOURCE = "test.mp4"                 # "0" webcam ou caminho .mp4
YOLO_MODEL  = "yolov8n.pt"
CONF        = 0.35
TRACE_LEN   = 20                   # trilhas desenhadas
YARD_GEOFENCE = (0.02, 0.02, 0.96, 0.96)  # xmin,ymin,xmax,ymax em coords normalizadas
SPEED_HIST  = 5                    # quantos frames para média de velocidade
MOV_THRESH  = 0.005                # velocidade (em fração da diagonal) para considerar "em_uso"
STILL_SECS  = 30                   # parado > Xs -> alerta de ociosidade
FRAME_TARGET_FPS = 8               # quantas atualizações por segundo enviar ao dashboard
# ------------------------------------------

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_headers=["*"], allow_methods=["*"])

clients: List[WebSocket] = []
state_lock = threading.Lock()
shared_snapshot: Dict[str, Any] = {
    "motos": [],
    "alerts": [],
    "totals": {"em_uso": 0, "parada": 0, "manutencao": 0, "fora_da_area": 0, "total": 0},
    "zones": [{"x":0.05,"y":0.05,"w":0.9,"h":0.9}],  # só para desenhar o pátio
}

# sobrescrever manualmente uma moto como "manutencao" (exemplo)
manual_status: Dict[int, str] = {}

def broadcast_loop():
    global shared_snapshot
    period = 1.0 / FRAME_TARGET_FPS
    while True:
        payload = None
        with state_lock:
            payload = json.dumps({"type":"snapshot","payload":shared_snapshot})
        stale = []
        for ws in list(clients):
            try:
                import asyncio
                asyncio.run(ws.send_text(payload))
            except Exception:
                stale.append(ws)
        for ws in stale:
            try: clients.remove(ws)
            except: pass
        time.sleep(period)

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    clients.append(ws)
    try:
        while True:
            # opcional: receber comandos do front (ex. marcar manutenção)
            _ = await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        if ws in clients:
            clients.remove(ws)

def compute_status(track_id:int, center_hist:deque, last_move_ts:Dict[int,float], now:float, conf:float, bbox, yard_box):
    # velocidade média (pixels normalizados)
    speed = 0.0
    if len(center_hist) >= 2:
        dists = [np.hypot(cx2-cx1, cy2-cy1) for (cx1,cy1),(cx2,cy2) in zip(center_hist, list(center_hist)[1:])]
        speed = float(np.mean(dists)) if dists else 0.0

    x1,y1,x2,y2 = bbox
    cx = (x1+x2)/2.0
    cy = (y1+y2)/2.0
    area = max(0.0, (x2-x1)*(y2-y1))

    xmin,ymin,xmax,ymax = yard_box
    inside = (xmin <= cx <= xmax) and (ymin <= cy <= ymax)

    # estado base
    status = "em_uso" if speed >= MOV_THRESH else "parada"

    # override manual
    if track_id in manual_status:
        status = manual_status[track_id]

    # fora da área
    if not inside:
        status = "fora_da_area"

    note = None
    # idle alert
    if status == "parada":
        if track_id not in last_move_ts:
            last_move_ts[track_id] = now
        # se moveu neste frame, zera contador
        if speed >= MOV_THRESH:
            last_move_ts[track_id] = now
        elif now - last_move_ts.get(track_id, now) >= STILL_SECS:
            note = f"Parada há {int(now - last_move_ts[track_id])}s"

    # confiança baixa
    alert_low_conf = conf < 0.25

    return status, cx, cy, area, inside, speed, note, alert_low_conf

def tracker_thread():
    global shared_snapshot
    source = 0 if str(VIDEO_SOURCE).strip() == "0" else VIDEO_SOURCE
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        raise RuntimeError(f"Não foi possível abrir a fonte: {VIDEO_SOURCE}")

    fps_src = cap.get(cv2.CAP_PROP_FPS) or 25.0
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)

    model = YOLO(YOLO_MODEL)
    tracker = sv.ByteTrack()
    trace_annotator = sv.TraceAnnotator(thickness=2, trace_length=TRACE_LEN)

    names = model.model.names if hasattr(model.model, "names") else model.names
    motorcycle_ids = [i for i, n in names.items() if n.lower() in ("motorcycle", "motorbike")]
    if not motorcycle_ids:
        raise RuntimeError("Classe 'motorcycle' não encontrada no modelo escolhido.")

    center_history: Dict[int, deque] = defaultdict(lambda: deque(maxlen=SPEED_HIST))
    last_move_ts: Dict[int, float] = {}
    seen_ids = set()
    recent_alerts: deque = deque(maxlen=200)

    window_title = "Rastreamento Motos (Servidor)"
    fps_smooth = None
    last_time = time.time()

    while True:
        ok, frame = cap.read()
        if not ok:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            continue

        result = model(frame, conf=CONF, verbose=False)[0]
        detections = sv.Detections.from_ultralytics(result)

        if detections.class_id is not None and len(detections) > 0:
            mask = np.isin(detections.class_id, motorcycle_ids)
            detections = detections[mask]

        detections = tracker.update_with_detections(detections)

        # normalização para 0..1
        def norm_bbox(xyxy):
            x1,y1,x2,y2 = xyxy
            return (x1/w, y1/h, x2/w, y2/h)

        now = time.time()
        motos = []
        totals = {"em_uso":0, "parada":0, "manutencao":0, "fora_da_area":0}

        for i in range(len(detections)):
            tid = int(detections.tracker_id[i]) if detections.tracker_id is not None and detections.tracker_id[i] is not None else None
            conf = float(detections.confidence[i]) if detections.confidence is not None else 0.0
            x1,y1,x2,y2 = map(int, detections.xyxy[i])
            nb = norm_bbox((x1,y1,x2,y2))

            if tid is None:
                tid = -1_000_000 + i  # fallback

            # histórico de centro
            cx = (nb[0]+nb[2])/2.0
            cy = (nb[1]+nb[3])/2.0
            center_history[tid].append((cx,cy))

            status, cx, cy, area, inside, speed, note, low_conf = compute_status(
                tid, center_history[tid], last_move_ts, now, conf, nb, YARD_GEOFENCE
            )

            totals[status] = totals.get(status, 0) + 1
            seen_ids.add(tid)

            if low_conf:
                recent_alerts.append({
                    "level":"medium",
                    "title": f"Confiança baixa em #{tid}",
                    "desc": f"conf={conf:.2f}",
                    "ts": int(now*1000)
                })

            if not inside:
                recent_alerts.append({
                    "level":"high",
                    "title": f"Moto #{tid} fora da área",
                    "desc": f"Posição {cx:.2f},{cy:.2f}",
                    "ts": int(now*1000)
                })

            if note:
                recent_alerts.append({
                    "level":"medium",
                    "title": f"Moto #{tid} ociosa",
                    "desc": note,
                    "ts": int(now*1000)
                })

            motos.append({
                "id": tid,
                "status": status,
                "conf": conf,
                "cx": cx, "cy": cy,
                "area": area,
                "note": note or ""
            })

        # FPS opcional para debug
        inst = 1.0/max(1e-6, time.time()-last_time)
        fps_smooth = 0.9*(fps_smooth or inst)+0.1*inst
        last_time = time.time()
        cv2.putText(frame, f"FPS {fps_smooth:.1f}", (12,24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,255,0), 2)

        # (opcional) mostrar vídeo com caixas
        # for det in detections: pass
        cv2.imshow(window_title, frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

        with state_lock:
            shared_snapshot["motos"] = motos
            shared_snapshot["alerts"] = list(reversed(list(recent_alerts)))[:50]
            shared_snapshot["totals"] = {
                **totals,
                "total": len(motos)
            }

    cap.release()
    cv2.destroyAllWindows()

def run():
    # servidor web (thread)
    t = threading.Thread(target=lambda: uvicorn.run(app, host="0.0.0.0", port=8000, log_level="warning"), daemon=True)
    t.start()
    # broadcaster (thread)
    tb = threading.Thread(target=broadcast_loop, daemon=True)
    tb.start()
    # tracker principal (thread atual)
    tracker_thread()

if __name__ == "__main__":
    run()
