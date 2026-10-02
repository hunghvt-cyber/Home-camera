import os
import json
import subprocess
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path

PROJECT_ROOT = Path(os.environ.get("TAPO_ROOT", Path(__file__).resolve().parent))
RECORDINGS_DIR = Path(os.environ.get("TAPO_RECORDINGS_DIR", PROJECT_ROOT / "recordings"))
METADATA_DIR = Path(os.environ.get("TAPO_METADATA_DIR", PROJECT_ROOT / "metadata"))
LAB_EVENTS_DIR = Path(os.environ.get("TAPO_EVENTS_DIR", PROJECT_ROOT / "events"))
LOCAL_TZ = ZoneInfo('Asia/Ho_Chi_Minh')

def get_file_info(file_path):
    cmd = [
        'ffprobe', '-v', 'error',
        '-show_entries', 'format=duration,size',
        '-of', 'json', str(file_path)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        try:
            return json.loads(result.stdout)['format']
        except (json.JSONDecodeError, KeyError):
            return None
    return None

def build_segment(file_path):
    mtime = os.path.getmtime(file_path)
    if datetime.now().timestamp() - mtime < 360:
        return None
    filename = file_path.name
    if not filename.endswith('.mp4'):
        return None
    parts = filename[:-4].split('-')
    if len(parts) < 3:
        return None
    camera = parts[0]
    date_str = parts[1]
    if len(date_str) != 8 or not date_str.isdigit():
        return None
    info = get_file_info(file_path)
    if not info:
        return None
    timestamp_str = parts[1] + parts[2]
    try:
        start_dt = datetime.strptime(timestamp_str, '%Y%m%d%H%M%S').replace(tzinfo=LOCAL_TZ)
        duration = float(info['duration'])
        end_dt = start_dt + timedelta(seconds=duration)
        size_bytes = int(info['size'])
    except (ValueError, TypeError, KeyError):
        return None
    return {
        'file': filename,
        'relative_path': str(file_path.relative_to(RECORDINGS_DIR)),
        'start': start_dt.isoformat(),
        'duration': duration,
        'end': end_dt.isoformat(),
        'size_bytes': size_bytes,
        'mtime': int(mtime),
    }

EVENT_INDEX_DIR = Path(METADATA_DIR) / 'events'

def _event_index_path(camera, date_iso):
    return EVENT_INDEX_DIR / camera / f'{date_iso}.json'

def _read_event_index(camera, date_iso):
    path = _event_index_path(camera, date_iso)
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if data.get('camera') != camera or data.get('date') != date_iso or not isinstance(data.get('events'), list):
            return None
        return data
    except (OSError, json.JSONDecodeError, TypeError):
        return None

def _write_event_index(camera, date_iso, source_mtime, events):
    path = _event_index_path(camera, date_iso)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {'camera': camera, 'date': date_iso, 'timezone': 'Asia/Ho_Chi_Minh', 'version': 1,
            'source_mtime': int(source_mtime), 'events': events}
    tmp = path.with_suffix('.json.tmp')
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)

def load_events(camera, date_iso):
    event_file = LAB_EVENTS_DIR / f'{camera}-events.jsonl'
    try:
        source_mtime = int(event_file.stat().st_mtime) if event_file.exists() else 0
    except OSError:
        source_mtime = 0
    cached = _read_event_index(camera, date_iso)
    if cached is not None and cached.get('source_mtime') == source_mtime:
        return cached['events']
    events = []
    if event_file.exists():
        with open(event_file, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    record = json.loads(line)
                    if record.get('event_local', '').startswith(date_iso):
                        events.append(record)
                except json.JSONDecodeError:
                    continue
    _write_event_index(camera, date_iso, source_mtime, events)
    return events

def _metadata_path(camera, date):
    return Path(METADATA_DIR) / f'{camera}_{date}.json'

def _read_metadata(camera, date):
    path = _metadata_path(camera, date)
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if data.get('camera') != camera or data.get('date') != date:
            return None
        if not isinstance(data.get('segments'), list):
            return None
        if not isinstance(data.get('events'), list):
            data['events'] = []
        return data
    except (OSError, json.JSONDecodeError, TypeError):
        return None

def write_metadata(camera, date, segments, events=None):
    METADATA_DIR.mkdir(parents=True, exist_ok=True)
    output_file = _metadata_path(camera, date)
    data = {'camera': camera, 'date': date, 'timezone': 'Asia/Ho_Chi_Minh',
            'segments': sorted(segments, key=lambda x: x['file']),
            'events': events or []}
    tmp_file = output_file.with_suffix('.json.tmp')
    with open(tmp_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    os.replace(tmp_file, output_file)

def _candidate_files(camera, date_str):
    for root, dirs, files in os.walk(RECORDINGS_DIR / camera):
        for file in files:
            if not file.endswith('.mp4'):
                continue
            parts = file[:-4].split('-')
            if len(parts) >= 3 and parts[0] == camera and parts[1] == date_str:
                yield Path(root) / file

def index_camera_date(camera, date):
    if camera not in ['cam1', 'cam2']:
        raise ValueError('Invalid camera')
    try:
        target_date = datetime.strptime(date, '%Y-%m-%d')
    except ValueError:
        raise ValueError('Invalid date')
    existing = _read_metadata(camera, date)
    date_str = target_date.strftime('%Y%m%d')
    old_by_file = {str(item.get('relative_path') or item.get('file')): item
                   for item in (existing or {}).get('segments', [])
                   if isinstance(item, dict)}
    segments = dict(old_by_file)
    for file_path in _candidate_files(camera, date_str):
        relative = str(file_path.relative_to(RECORDINGS_DIR))
        try:
            stat = file_path.stat()
        except OSError:
            continue
        old = old_by_file.get(relative)
        if old and old.get('mtime') == int(stat.st_mtime) and old.get('size_bytes') == int(stat.st_size) and old.get('duration') is not None:
            continue
        segment = build_segment(file_path)
        if segment is not None:
            segments[relative] = segment
    events = load_events(camera, date)
    result_segments = sorted(segments.values(), key=lambda x: x['file'])
    write_metadata(camera, date, result_segments, events)
    return {'camera': camera, 'date': date, 'timezone': 'Asia/Ho_Chi_Minh',
            'segments': result_segments, 'events': events}

def index_recordings():
    if not METADATA_DIR.exists():
        METADATA_DIR.mkdir(parents=True)
    index = {}
    for root, dirs, files in os.walk(RECORDINGS_DIR):
        for file in files:
            if not file.endswith('.mp4'):
                continue
            parts = file[:-4].split('-')
            if len(parts) < 3:
                continue
            camera = parts[0]
            date_str = parts[1]
            if len(date_str) != 8 or not date_str.isdigit():
                continue
            formatted_date = f'{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}'
            index.setdefault(camera, {}).setdefault(formatted_date, [])
            segment = build_segment(Path(root) / file)
            if segment is not None:
                index[camera][formatted_date].append(segment)
    for camera in index:
        for date in index[camera]:
            events = load_events(camera, date)
            write_metadata(camera, date, index[camera][date], events)
