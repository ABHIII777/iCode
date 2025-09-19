from PyQt5.QtCore import QThread, pyqtSignal
import google.generativeai as genai
import json

class CompletionThread(QThread):
    suggestionReady = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, apiKey, prompt, parent=None, debug=True):
        super().__init__(parent)
        self.apiKey = apiKey
        self.prompt = prompt
        self._cancel = False
        self.debug = debug

    def cancel(self):
        self._cancel = True

    def run(self):
        suggestion = ""

        if self.isInterruptionRequested():
            return

        try:
            if self._cancel:
                self.suggestionReady.emit("")
                return

            genai.configure(api_key=self.apiKey)

            # Use gemini-pro (text) or gemini-1.5-flash (multi-modal)
            model = genai.GenerativeModel("gemini-2.5-flash")

            # if self.debug:
                # print(f"[DEBUG] Sending prompt to Gemini: {self.prompt}")

            response = model.generate_content(self.prompt)

            if self.isInterruptionRequested():
                return

            if not self._cancel:
                if getattr(response, "text", None):
                    suggestion = response.text.strip()
                elif hasattr(response, "candidates"):
                    for c in response.candidates:
                        if c.content.parts:
                            suggestion = c.content.parts[0].text.strip()
                            break

        except Exception as e:
            suggestion = ""
            # print(f"[ERROR] Suggestion failed: {e}")

        # if self.debug:
        #     print("[INFO] Final suggestion:", suggestion if suggestion else "<EMPTY>")

        self.suggestionReady.emit(suggestion)
        self.finished.emit()
