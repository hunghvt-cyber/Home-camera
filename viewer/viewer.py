import http.server
import socketserver
import os
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse, parse_qs

PROJECT_ROOT = Path(os.environ.get("TAPO_ROOT", Path(__file__).resolve().parent.parent))
PORT = int(os.environ.get("TAPO_VIEWER_PORT", "8080"))
BASE_DIR = Path(os.environ.get("TAPO_RECORDINGS_DIR", PROJECT_ROOT / "recordings"))
METADATA_DIR = Path(os.environ.get("TAPO_METADATA_DIR", PROJECT_ROOT / "metadata"))
INDEXER_DIR = str(PROJECT_ROOT)
VIEWER_DIR = Path(__file__).resolve().parent

sys.path.insert(0, INDEXER_DIR)
sys.path.insert(0, str(VIEWER_DIR))

from recording_indexer import index_camera_date, load_events, build_segment
from resolver import resolve_events
from range_utils import parse_range
from archive import archive_mapping, ensure_local_archive

os.chdir(BASE_DIR)

def _valid_request(cam, date):
    return cam in ['cam1', 'cam2'] and re.match(r'^\d{4}-\d{2}-\d{2}$', date or '')

def _decorate_local_availability(data):
    for segment in data.get('segments', []):
        relative = segment.get('relative_path')
        segment['local_available'] = bool(relative and os.path.isfile(os.path.join(BASE_DIR, relative)))
    return data

class Handler(http.server.SimpleHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def _json_response(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def _camera_date(self):
        query = parse_qs(urlparse(self.path).query)
        cam = query.get('cam', ['cam1'])[0]
        date = query.get('date', [''])[0]
        if not _valid_request(cam, date):
            self.send_error(400, 'Invalid camera/date')
            return None, None
        return cam, date

    def _load_resolved_events(self, cam, date, segments, cached_events=None):
        return resolve_events(load_events(cam, date), segments)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path.rstrip('/') == '/api/archive':
            query = parse_qs(parsed.query)
            cam = query.get('cam', [''])[0]
            segment = query.get('segment', [''])[0]
            mapping = archive_mapping(cam, segment)
            if mapping is None:
                self._json_response({'ok': False, 'error': 'Invalid camera/segment'}, 400)
                return
            try:
                local_path = ensure_local_archive(cam, segment)
                segment_data = build_segment(local_path)
                if segment_data is None:
                    raise RuntimeError('downloaded segment could not be indexed')
                segment_data['local_available'] = True
            except Exception as exc:
                self._json_response({'ok': False, 'error': str(exc), 'camera': cam, 'segment': segment}, 502)
                return
            self._json_response({'ok': True, 'camera': cam, 'segment': segment,
                                 'path': '/' + str(local_path.relative_to(BASE_DIR)),
                                 'size_bytes': local_path.stat().st_size, 'metadata': segment_data})
            return
        if parsed.path.rstrip('/') in ('/api/metadata', '/api/events'):
            cam, date = self._camera_date()
            if cam is None:
                return
            try:
                data = index_camera_date(cam, date)
                data = _decorate_local_availability(data)
                events = self._load_resolved_events(cam, date, data['segments'], data.get('events'))
            except Exception as exc:
                self.send_error(500, f'Indexing failed: {exc}')
                return
            if parsed.path.rstrip('/') == '/api/events':
                self._json_response({'camera': cam, 'date': date, 'timezone': 'Asia/Ho_Chi_Minh', 'events': events})
            else:
                data['timezone'] = 'Asia/Ho_Chi_Minh'
                data['events'] = events
                self._json_response(data)
            return
        if parsed.path == '/':
            try:
                with open(VIEWER_DIR / 'index.html', 'rb') as f:
                    body = f.read()
            except OSError as exc:
                self.send_error(500, f'Viewer page unavailable: {exc}')
                return
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if '..' in self.path or not self.path.startswith('/'):
            self.send_error(403)
            return
        super().do_GET()

    def send_head(self):
        path = self.translate_path(self.path)
        if os.path.isdir(path):
            return super().send_head()
        try:
            size = os.path.getsize(path)
            mtime = os.path.getmtime(path)
        except OSError:
            self.send_error(404, 'File not found')
            return None
        range_header = self.headers.get('Range')
        byte_range = parse_range(range_header, size) if range_header else None
        if range_header and byte_range is None:
            self.send_response(416)
            self.send_header('Content-Range', f'bytes */{size}')
            self.send_header('Content-Length', '0')
            self.end_headers()
            return None
        if byte_range is None:
            start, end = 0, size - 1
            status = 200
        else:
            start, end = byte_range
            status = 206
        self.send_response(status)
        self.send_header('Content-Type', self.guess_type(path))
        self.send_header('Accept-Ranges', 'bytes')
        self.send_header('Content-Length', str(end - start + 1))
        if status == 206:
            self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
        self.send_header('Last-Modified', self.date_time_string(mtime))
        self.end_headers()
        try:
            fileobj = open(path, 'rb')
        except OSError:
            self.send_error(404, 'File not found')
            return None
        self._range_start = start
        self._range_remaining = end - start + 1
        return fileobj

    def copyfile(self, source, outputfile):
        remaining = getattr(self, '_range_remaining', None)
        if remaining is None:
            return super().copyfile(source, outputfile)
        source.seek(getattr(self, '_range_start', 0))
        try:
            while remaining:
                chunk = source.read(min(64 * 1024, remaining))
                if not chunk:
                    break
                outputfile.write(chunk)
                remaining -= len(chunk)
        finally:
            source.close()

class ThreadingTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True

with ThreadingTCPServer(('', PORT), Handler) as httpd:
    httpd.serve_forever()
