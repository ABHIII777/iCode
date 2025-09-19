from PyQt5 import *
from PyQt5.QtCore import *

import json

class LSPReaderThread(QThread):
    messageReceived = pyqtSignal(dict)

    def __init__(self, stdoutPipe, debug=False):
        super().__init__()
        self.stdout = stdoutPipe
        self._running = True
        self._buffer = bytearray()
        self.debug = debug

    def run(self):
        try:
            while self._running and not self.isInterruptionRequested():
                try:
                    chunk = self.stdout.read(4096)
                except Exception as e:
                    if self.debug:
                        print("LSPReader read error:", e)
                    break

                if not chunk:
                    break

                self._buffer.extend(chunk)

                while True:
                    sep = b"\r\n\r\n"
                    idx = self._buffer.find(sep)
                    if idx == -1:
                        break

                    header_bytes = bytes(self._buffer[:idx])
                    del self._buffer[:idx + len(sep)]

                    try:
                        header_text = header_bytes.decode("utf-8", errors="ignore")
                    except Exception:
                        header_text = ""

                    content_length = 0
                    for line in header_text.split("\r\n"):
                        parts = line.split(":", 1)
                        if len(parts) == 2 and parts[0].strip().lower() == "content-length":
                            try:
                                content_length = int(parts[1].strip())
                            except Exception:
                                content_length = 0
                            break

                    if content_length <= 0:
                        if self.debug:
                            print("LSPReader: invalid content-length in header:", header_text)
                        continue

                    while len(self._buffer) < content_length:
                        try:
                            more = self.stdout.read(4096)
                        except Exception:
                            more = b""
                        if not more:
                            break
                        self._buffer.extend(more)

                    if len(self._buffer) < content_length:
                        break

                    body_bytes = bytes(self._buffer[:content_length])
                    del self._buffer[:content_length]

                    try:
                        text = body_bytes.decode("utf-8")
                        obj = json.loads(text)
                        self.messageReceived.emit(obj)
                    except Exception as e:
                        if self.debug:
                            print("LSPReader: failed to parse JSON body:", e)
                        continue
        except Exception as e:
            if self.debug:
                print("LSPReaderThread exception:", e)
        finally:
            self._running = False

    def stop(self):
        self._running = False
        try:
            self.requestInterruption()
            if self.isRunning():
                self.wait(2000)
        except Exception:
            pass