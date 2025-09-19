from PyQt5 import *
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *

import os

class Terminal(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.output = QTextEdit()
        self.output.setReadOnly(True)

        self.input = QLineEdit()
        self.input.returnPressed.connect(self.sendCommand)

        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.MergedChannels)
        self.process.readyReadStandardOutput.connect(self.onReadyRead)

        home_dir = os.path.expanduser("~")
        try:
            self.process.setWorkingDirectory(home_dir)
        except Exception:
            pass

        shell = "/bin/zsh"
        if not os.path.exists(shell):
            shell = "/bin/bash" if os.path.exists("/bin/bash") else None

        if shell:
            self.process.start(shell)
        else:
            self.output.append("No interactive shell found.")

        if not self.process.waitForStarted(1000):
            self.output.append("Failed to start shell.")

        layout = QVBoxLayout()
        layout.addWidget(self.output)
        layout.addWidget(self.input)
        self.setLayout(layout)

    def sendCommand(self):
        text = self.input.text().strip()

        if text:
            try:
                self.process.write((text + "\n").encode())
            except Exception:
                pass
            self.input.clear()

        if text.lower() == "clear":
            self.output.clear()
            self.input.clear()
            return

    def onReadyRead(self):
        try:
            data = bytes(self.process.readAllStandardOutput()).decode(errors="ignore")
        except Exception:
            data = ""

        self.output.moveCursor(self.output.textCursor().End)
        self.output.insertPlainText(data)
        self.output.moveCursor(self.output.textCursor().End)

    def closeEvent(self, event):
        try:
            proc = getattr(self, "process", None)
            if proc and proc.state() != QProcess.NotRunning:
                try:
                    proc.write(b"exit\n")
                    proc.waitForFinished(500)
                    if proc.state() != QProcess.NotRunning:
                        proc.kill()
                except Exception:
                    try:
                        proc.kill()
                    except Exception:
                        pass
        finally:
            super().closeEvent(event)