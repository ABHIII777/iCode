from PyQt5 import *
from PyQt5.QtCore import *
from LSPReaderThread import *
from StderrReaderThread import *

import threading
import subprocess
import os
import time

class LSPClient(QObject):
    completionReceived = pyqtSignal(list)

    def __init__(self, cmd=None, debug=False, languageId="python"):
        super().__init__()
        if cmd is None:
            cmd = ["pyright-langserver", "--stdio"]

        self.languageId = languageId
        self.debug = debug
        self._write_lock = threading.Lock()
        self._id_lock = threading.Lock()

        try:
            self.process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0
            )
        except Exception as e:
            raise RuntimeError(f"Failed to start LSP server: {e}")

        self._stdout = self.process.stdout
        self._stdin = self.process.stdin
        self._stderr = self.process.stderr

        self._id = 0
        self._pending = {}

        self.reader = LSPReaderThread(self._stdout, debug=self.debug)
        self.reader.messageReceived.connect(self._onMessage)
        self.reader.start()

        self.stderr_reader = StderrReaderThread(self._stderr, debug=self.debug)
        self.stderr_reader.messageReceived.connect(lambda line: print("LSP stderr:", line) if self.debug else None)
        self.stderr_reader.start()

        root_uri = "file://" + os.path.abspath(os.getcwd())
        if self.debug:
            print("LSP: sending initialize, root_uri=", root_uri)
        
        capabilities = {
            "textDocument": {
                "completion": {
                    "completionItem": {
                        "snippetSupport": True,
                        "documentationFormat": ["markdown", "plaintext"],
                    }
                },
                "signatureHelp": {
                    "signatureInformation": {
                        "documentationFormat": ["markdown", "plaintext"],
                        "parameterInformation": {"labelOffsetSupport": True},
                    }
                },
            }
        }

        self._sendRequest("initialize", {
            "processId": os.getpid(),
            "rootUri": root_uri,
            "capabilities": capabilities,
            "trace" : "verbose",
        }, callback=None)

        time.sleep(0.01)
        self._sendNotification("initialized", {})

        self.lastUri = None
        self.lastText = None
        self._version = 1

    def _nextId(self):
        with self._id_lock:
            self._id += 1
            return self._id

    def _send(self, obj):
        try:
            body = json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
            header = f"Content-Length: {len(body)}\r\n\r\n".encode("utf-8")

            if self.debug:
                method = obj.get('method', '<resp>') if isinstance(obj, dict) else '<raw>'
                print(f"LSP => {method} id={obj.get('id') if isinstance(obj, dict) else 'n/a'}")

            with self._write_lock:
                try:
                    if self._stdin:
                        self._stdin.write(header + body)
                        self._stdin.flush()
                except Exception as e:
                    if self.debug:
                        print("LSP send error:", e)
        except Exception as e:
            if self.debug:
                print("LSP _send serialization error:", e)

    def _sendRequest(self, method, params, callback=None):
        msgId = self._nextId()
        msg = {"jsonrpc": "2.0", "id": msgId, "method": method, "params": params}
        if callback:
            self._pending[msgId] = callback
        self._send(msg)
        return msgId

    def _sendNotification(self, method, params):
        msg = {"jsonrpc": "2.0", "method": method, "params": params}
        self._send(msg)

    def _onMessage(self, msg):
        if self.debug:
            print('LSP <=', msg)

        try:
            if "id" in msg and ("result" in msg or "error" in msg):
                rid = msg.get("id")

                cb = self._pending.pop(rid, None)

                if cb:
                    try:
                        cb(msg.get("result"))
                    except Exception as e:
                        if self.debug:
                            print("LSP callback raised an exception", e)

                else:
                    pass
            else:
                if self.debug and 'method' in msg:
                    print("LSP notification:", msg.get('method'))
        except Exception as e:
            if self.debug:
                print("_onMessage exception", e)

    def openDocument(self, uri, text):
        params = {
            "textDocument": {
                "uri": uri,
                "languageId": self.languageId,
                "version": self._version,
                "text": text
            }
        }
        if self.debug:
            print("LSP: didOpen", uri)
        self._sendNotification("textDocument/didOpen", params)
        self.lastUri = uri
        self.lastText = text

    def changeDocument(self, uri, text, version=None):
        if version is None:
            self._version += 1
            version = self._version

        params = {
            "textDocument": {"uri": uri, "version": version or int(time.time())},
            "contentChanges": [{"text": text}]
        }

        if self.debug:
            print("LSP: didChange", uri, "ver", version)

        if text == self.lastText:
            return
        self._sendNotification("textDocument/didChange", params)
        self.lastText = text

    def completion(self, uri, line, character, callback = None):
        params = {
            "textDocument" : {"uri" : uri},
            "position" : {"line" : line, "character" : character}
        }

        self._sendRequest("textDocument/completion", params, callback)

    def signatureHelp(self, uri, line, character, callback = None):
        params = {
            "textDocument" : {"uri" : uri},
            "position" : {"line" : line, "character" : character}
        }

        self._sendRequest("textDocument/signatureHelp", params, callback)

    def requestCompletion(self, uri, line, character, callback):
        def cb(result):
            labels = []
            if not result:
                callback([])
                return

            items = result.get("items", result) if isinstance(result, dict) else result
            for it in items or []:
                label = it.get("label") or it.get("insertText") or ""
                if isinstance(label, dict):
                    label = label.get("label", "")
                labels.append(label)
            callback(labels)

        params = {
            "textDocument": {"uri": uri},
            "position": {"line": line, "character": character}
        }
        if self.debug:
            print("LSP: completion request", uri, line, character)
        # self._sendRequest("textDocument/completion", params, callback=cb)
        self._sendRequest("textDocument/completion", params, callback=callback)

    def shutdown(self):
        try:
            self._sendRequest("shutdown", {}, callback=lambda r: None)
            self._sendNotification("exit", {})
        except Exception:
            pass
        try:
            if getattr(self, "reader", None):
                self.reader.stop()
        except Exception:
            pass
        try:
            if getattr(self, "stderr_reader", None):
                self.stderr_reader.stop()
        except Exception:
            pass
        try:
            if getattr(self, "process", None):
                self.process.terminate()
                time.sleep(0.05)
                if self.process.poll() is None:
                    self.process.kill()
        except Exception:
            pass