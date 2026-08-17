#!/usr/bin/env python3
"""Consent-controlled HTTP relay for the macOS built-in camera.

The process can listen for control requests without opening the camera. The
camera is opened only by an authenticated POST to /start and is released by
POST /stop. Frames are kept in memory and exposed one at a time as JPEG.
"""

from __future__ import annotations

import argparse
import json
import secrets
import signal
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import cv2


class CameraRelay:
    """Own the camera lifecycle and the latest in-memory JPEG frame."""

    def __init__(self, camera_index: int, width: int, height: int) -> None:
        self._camera_index = camera_index
        self._width = width
        self._height = height
        self._lock = threading.Lock()
        self._capture = None
        self._frame: bytes | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._error = ''

    @property
    def active(self) -> bool:
        with self._lock:
            return self._capture is not None

    @property
    def error(self) -> str:
        with self._lock:
            return self._error

    def start(self) -> tuple[bool, str]:
        with self._lock:
            if self._capture is not None:
                return True, 'camera already active'
        backend = getattr(cv2, 'CAP_AVFOUNDATION', cv2.CAP_ANY)
        capture = cv2.VideoCapture(self._camera_index, backend)
        if not capture.isOpened():
            capture.release()
            with self._lock:
                self._error = (
                    'camera could not be opened; check macOS camera '
                    'permission for Terminal or Python')
            return False, self.error
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, self._width)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self._height)
        with self._lock:
            self._capture = capture
            self._frame = None
            self._error = ''
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._capture_loop,
            name='mac-camera-capture',
            daemon=True,
        )
        self._thread.start()
        return True, 'camera opened after consent'

    def stop(self) -> None:
        self._stop.set()
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=2.0)
        with self._lock:
            capture = self._capture
            self._capture = None
            self._frame = None
            self._thread = None
        if capture is not None:
            capture.release()

    def frame(self) -> bytes | None:
        with self._lock:
            return self._frame

    def _capture_loop(self) -> None:
        while not self._stop.is_set():
            with self._lock:
                capture = self._capture
            if capture is None:
                return
            ok, image = capture.read()
            if not ok:
                with self._lock:
                    self._error = 'camera stopped returning frames'
                break
            encoded, jpeg = cv2.imencode(
                '.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, 82])
            if encoded:
                with self._lock:
                    self._frame = jpeg.tobytes()
            time.sleep(0.01)
        self.stop()


def make_handler(relay: CameraRelay, token: str):
    """Create a request handler bound to one relay and bearer token."""

    class RelayHandler(BaseHTTPRequestHandler):

        server_version = 'ConsentCameraRelay/1.0'

        def log_message(self, message, *args) -> None:
            print(f'[camera-relay] {self.address_string()} '
                  f'{message % args}', flush=True)

        def _authorized(self) -> bool:
            return self.headers.get('Authorization') == f'Bearer {token}'

        def _reject_unauthorized(self) -> None:
            self.send_error(HTTPStatus.UNAUTHORIZED, 'invalid relay token')

        def _json(self, status: HTTPStatus, payload: dict) -> None:
            content = json.dumps(payload).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(content)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(content)

        def do_GET(self) -> None:  # noqa: N802 - HTTP method name
            if not self._authorized():
                self._reject_unauthorized()
                return
            if self.path == '/status':
                self._json(HTTPStatus.OK, {
                    'active': relay.active,
                    'frame_available': relay.frame() is not None,
                    'error': relay.error,
                })
                return
            if self.path != '/frame.jpg':
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            frame = relay.frame()
            if not relay.active or frame is None:
                self.send_error(HTTPStatus.SERVICE_UNAVAILABLE,
                                'camera frame unavailable')
                return
            self.send_response(HTTPStatus.OK)
            self.send_header('Content-Type', 'image/jpeg')
            self.send_header('Content-Length', str(len(frame)))
            self.send_header('Cache-Control', 'no-store, no-cache')
            self.end_headers()
            self.wfile.write(frame)

        def do_POST(self) -> None:  # noqa: N802 - HTTP method name
            if not self._authorized():
                self._reject_unauthorized()
                return
            if self.path == '/start':
                ok, message = relay.start()
                status = HTTPStatus.OK if ok else HTTPStatus.CONFLICT
                self._json(status, {'active': relay.active,
                                    'message': message})
                return
            if self.path == '/stop':
                relay.stop()
                self._json(HTTPStatus.OK, {
                    'active': False,
                    'message': 'camera closed and frame cleared',
                })
                return
            self.send_error(HTTPStatus.NOT_FOUND)

    return RelayHandler


def parse_args():
    parser = argparse.ArgumentParser(
        description='Expose the Mac camera only after authenticated consent')
    parser.add_argument('--bind', default='0.0.0.0')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--token', default='')
    parser.add_argument('--camera-index', type=int, default=0)
    parser.add_argument('--width', type=int, default=640)
    parser.add_argument('--height', type=int, default=480)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    token = args.token or secrets.token_urlsafe(24)
    relay = CameraRelay(args.camera_index, args.width, args.height)
    server = ThreadingHTTPServer(
        (args.bind, args.port), make_handler(relay, token))

    def shutdown(_signum, _frame) -> None:
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    print('Mac camera relay ready; the camera is CLOSED.', flush=True)
    print(f'Relay URL: http://<mac-ip>:{args.port}', flush=True)
    print(f'Relay token: {token}', flush=True)
    print('The camera opens only after an authenticated /start request.',
          flush=True)
    try:
        server.serve_forever(poll_interval=0.25)
    finally:
        relay.stop()
        server.server_close()
        print('Camera relay stopped; camera closed.', flush=True)


if __name__ == '__main__':
    main()
