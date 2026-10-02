#!/usr/bin/env python3
import asyncio
import datetime as dt
import json
import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from zoneinfo import ZoneInfo
from aiohttp import web
from onvif import ONVIFCamera

CAMERA_HOST=os.environ["TAPO_CAMERA_HOST"]
CAMERA_NAME=os.environ.get("TAPO_CAMERA_NAME","cam1")
CAMERA_PORT=int(os.environ.get("TAPO_CAMERA_PORT","2020"))
RECEIVER_HOST=os.environ.get("TAPO_EVENT_RECEIVER_HOST","0.0.0.0")
RECEIVER_PORT=int(os.environ.get("TAPO_EVENT_RECEIVER_PORT","9191"))
SUBSCRIBE_URL=os.environ["TAPO_EVENT_RECEIVER_URL"]
EVENTS_DIR=Path(os.environ.get("TAPO_EVENTS_DIR","./events"))
RECORDINGS_DIR=Path(os.environ.get("TAPO_RECORDINGS_DIR","./recordings"))/CAMERA_NAME
SEGMENT_SECONDS=int(os.environ.get("TAPO_SEGMENT_SECONDS","300"))
LOCAL_TZ=ZoneInfo(os.environ.get("TAPO_TIMEZONE","Asia/Ho_Chi_Minh"))
USER=os.environ["TAPO_USER"]; PASSWORD=os.environ["TAPO_PASSWORD"]
WSNT_NS="http://docs.oasis-open.org/wsn/b-2"; TT_NS="http://www.onvif.org/ver10/schema"
MOTION_TOPIC="tns1:RuleEngine/CellMotionDetector/Motion"
SEGMENT_RE=re.compile(rf"^{re.escape(CAMERA_NAME)}-(\d{{8}})-(\d{{6}})\.mp4$")

def parse_segment_start(path):
    m=SEGMENT_RE.match(path.name)
    if not m:return None
    return dt.datetime.strptime("".join(m.groups()),"%Y%m%d%H%M%S").replace(tzinfo=LOCAL_TZ)

def resolve_segment(received_utc):
    local=received_utc.astimezone(LOCAL_TZ)
    for p in RECORDINGS_DIR.glob(f"{CAMERA_NAME}-*.mp4"):
        s=parse_segment_start(p)
        if s and s<=local<s+dt.timedelta(seconds=SEGMENT_SECONDS): return p.name
    return None

def parse_motion_events(body):
    root=ET.fromstring(body); out=[]
    for n in root.findall(f".//{{{WSNT_NS}}}NotificationMessage"):
        topic=n.find(f"{{{WSNT_NS}}}Topic")
        if (topic.text or "").strip()!=MOTION_TOPIC: continue
        msg=n.find(f"{{{WSNT_NS}}}Message/{{{TT_NS}}}Message")
        if msg is None: continue
        motion=next((x.get("Value") for x in msg.findall(f"./{{{TT_NS}}}Data/{{{TT_NS}}}SimpleItem") if x.get("Name")=="IsMotion"),None)
        if msg.get("PropertyOperation")=="Changed" and motion=="true":
            out.append({"camera_utc":msg.get("UtcTime")})
    return out

def append_event(event, received_utc):
    EVENTS_DIR.mkdir(parents=True,exist_ok=True)
    record={"camera":CAMERA_NAME,"type":"motion","camera_utc":event["camera_utc"],
            "received_utc":received_utc.isoformat(),
            "event_local":received_utc.astimezone(LOCAL_TZ).isoformat(),
            "segment":resolve_segment(received_utc)}
    with (EVENTS_DIR/f"{CAMERA_NAME}-events.jsonl").open("a",encoding="utf-8") as f:
        f.write(json.dumps(record,ensure_ascii=False)+"\n"); f.flush()
    return record

async def notify_handler(request):
    body=await request.read(); received=dt.datetime.now(dt.timezone.utc)
    try: events=parse_motion_events(body)
    except ET.ParseError: return web.Response(status=400,text="Invalid XML")
    for event in events: append_event(event,received)
    return web.Response(text="",content_type="application/soap+xml")

async def main():
    EVENTS_DIR.mkdir(parents=True,exist_ok=True)
    app=web.Application(); app.router.add_post("/n",notify_handler)
    runner=web.AppRunner(app); await runner.setup()
    await web.TCPSite(runner,RECEIVER_HOST,RECEIVER_PORT).start()
    cam=ONVIFCamera(CAMERA_HOST,CAMERA_PORT,USER,PASSWORD); await cam.update_xaddrs()
    manager=await cam.create_notification_manager(SUBSCRIBE_URL,dt.timedelta(minutes=10),lambda: print("[SUBSCRIPTION] lost",flush=True))
    print(f"[EVENT LOGGER] {CAMERA_NAME} listening on {RECEIVER_HOST}:{RECEIVER_PORT}/n",flush=True)
    try: await asyncio.Event().wait()
    finally:
        try: await manager.stop()
        finally: await cam.close(); await runner.cleanup()

if __name__=="__main__": asyncio.run(main())
