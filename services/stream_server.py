import time
import numpy as np
import cv2
import threading
from flask import Flask, Response
from werkzeug.serving import make_server
import logging

logger = logging.getLogger("netra.stream_server")

class StreamServer:
    def __init__(self, host: str, port: int, get_frames_callback):
        self.host = host
        self.port = port
        self.get_frames_callback = get_frames_callback
        self.app = Flask(__name__)
        self.server = None
        self._setup_routes()

    def _generate_frames(self):
        while True:
            frames = self.get_frames_callback()
            if not frames:
                # Fallback empty frame
                f = np.zeros((360, 640, 3), dtype=np.uint8)
                cv2.putText(f, "Waiting for cameras...", (30, 180), cv2.FONT_HERSHEY_SIMPLEX, 0.85, (80, 80, 80), 2)
                frames = [f]

            if len(frames) == 1:
                grid = frames[0]
            else:
                rows = []
                for i in range(0, len(frames), 2):
                    pair = frames[i : i + 2]
                    if len(pair) == 1:
                        pair.append(np.zeros_like(pair[0]))
                    rows.append(np.hstack(pair))
                grid = np.vstack(rows)

            ret, buffer = cv2.imencode('.jpg', grid)
            if ret:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
            time.sleep(0.05)  # Max 20 FPS

    def _setup_routes(self):
        @self.app.route('/video_feed')
        def video_feed():
            return Response(self._generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

        @self.app.route('/shutdown', methods=['POST'])
        def shutdown():
            if self.server is not None:
                threading.Thread(target=self.server.shutdown, daemon=True).start()
            return 'shutting down', 200

    def start(self):
        self.server = make_server(self.host, self.port, self.app, threaded=True)
        logger.info("Live stream available at http://%s:%s/video_feed", self.host, self.port)
        self.server.serve_forever()

    def stop(self):
        if self.server is not None:
            self.server.server_close()
