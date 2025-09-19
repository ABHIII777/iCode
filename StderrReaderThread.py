from PyQt5 import *
from PyQt5.QtCore import *

class StderrReaderThread(QThread):
    messageReceived = pyqtSignal(str)

    def __init__(self, stderrPipe, debug=False):
        super().__init__()
        self.stderr = stderrPipe
        self._running = True
        self.debug = debug

    def run(self):
        try:
            while not self.isInterruptionRequested():
                try:
                    chunk = self.stderr.readline()
                except Exception:
                    break
                if not chunk:
                    break
                try:
                    line = chunk.decode("utf-8", errors="ignore").rstrip("\n")
                except Exception:
                    line = str(chunk)
                if self.debug:
                    print("LSP stderr:", line)
                self.messageReceived.emit(line)
        finally:
            self._running = False

    def stop(self):
        try:
            self.requestInterruption()
            if self.isRunning():
                self.wait(2000)
        except Exception:
            pass