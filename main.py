from PyQt5 import *
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *

from LSPClient import *
from Editor import *
from Terminal import *

import uuid
import sys

LSP_SERVERS = {
    ".py":  (["pyright-langserver", "--stdio"], "python"),
    ".cpp": (["clangd"], "cpp"),
    ".c":   (["clangd"], "c"),
    ".js":  (["typescript-language-server", "--stdio"], "javascript"),
    ".ts":  (["typescript-language-server", "--stdio"], "typescript"),
    ".go":  (["gopls"], "go"),
    ".rs":  (["rust-analyzer"], "rust"),
    ".java":(["jdtls"], "java"),
    ".sh":  (["bash-language-server", "start"], "bash"),
    ".json":(["vscode-json-language-server", "--stdio"], "json"),
}

class MainWindow(QMainWindow):

    def __init__(self, debug=False):
        super().__init__()

        self.debug = debug
        self._completionTimer = QTimer(self)
        self._completionTimer.setSingleShot(True)
        self._completionTimer.timeout.connect(self._do_completion_request)

        container = QWidget()
        self.setCentralWidget(container)
        self.setStyleSheet("QMainWindow {background-color: #1e1e2e;}")

        self.main_area = QWidget(container)
        self.main_area.setStyleSheet("QWidget {background-color: #181825; border-radius: 20px;}")

        main_area_layout = QHBoxLayout(self.main_area)
        main_area_layout.setContentsMargins(20, 20, 20, 20)
        main_area_layout.setSpacing(10)

        self.file_tree_container = QWidget()
        self.file_tree_container.setStyleSheet("QWidget {background-color: #1e1e2e; border-radius: 10px;}")
        self.tree_layout = QVBoxLayout(self.file_tree_container)
        self.tree_layout.setContentsMargins(10, 10, 10, 10)
        self.tree_layout.setSpacing(15)

        toolBar = QHBoxLayout()

        self.explorerLabel = QLabel("Explorer")
        self.explorerLabel.setStyleSheet("font-size: 16px; font-weight: bold; color: #a6adc8;")

        self.openFolderButton = QPushButton("Folder")
        self.openFolderButton.clicked.connect(self.FolderFunction)
        self.saveButton = QPushButton("Save")
        self.saveButton.clicked.connect(self.saveFileFunction)

        toolBar.addWidget(self.explorerLabel)
        toolBar.addStretch(1)
        toolBar.addWidget(self.openFolderButton)
        toolBar.addWidget(self.saveButton)
        self.tree_layout.addLayout(toolBar)

        self.RootTreeModel = QFileSystemModel()
        self.RootTreeModel.setRootPath("")
        self.RootTree = QTreeView()
        self.RootTree.setModel(self.RootTreeModel)
        self.RootTree.setRootIndex(self.RootTreeModel.index(""))
        self.tree_layout.addWidget(self.RootTree)
        main_area_layout.addWidget(self.file_tree_container, 1)

        self.file_tree_container.hide()
        # QShortcut(QKeySequence("Meta+1"), self, self.toggleFileTree)
        toggleFileTree = QShortcut(QKeySequence("Meta+N"), self)
        toggleFileTree.setContext(3)
        print("Acitvating the filetree toggle.")
        toggleFileTree.activated.connect(self.toggleFileTree)
        print("File tree toggled successfully>>>")

        self.editor_terminal_container = QWidget()
        self.editor_terminal_container.setStyleSheet("QWidget {background-color: #1e1e2e; border-radius: 10px;}")
        editor_terminal_layout = QVBoxLayout(self.editor_terminal_container)
        editor_terminal_layout.setContentsMargins(10, 10, 10, 10)
        editor_terminal_layout.setSpacing(10)

        self.runButton = QPushButton(self.editor_terminal_container)
        self.runButton.setText("▶ RUN")
        self.runButton.clicked.connect(self.compileAndRun)
        self.runButton.setStyleSheet("""
            QPushButton {
                background-color: #a6e3a1;
                color: #1e1e2e;
                border-radius: 12px;
                padding: 10px 20px;
                font-weight: bold;
                font-size: 12px;
            }

            QPushButton:hover {
                background-color: #94e2d5;
            }
        """)

        self.workSpace = Editor(parent=self.editor_terminal_container)
        self.terminal = Terminal(parent=self.editor_terminal_container)

        editor_terminal_layout.addWidget(self.workSpace, 5)
        editor_terminal_layout.addWidget(self.terminal, 2)
        main_area_layout.addWidget(self.editor_terminal_container, 3)

        self.bottom_bar = QWidget(container)
        self.bottom_bar.setStyleSheet("""
            QWidget {
                background-color: #181825;
                border-radius: 15px;
                margin-top: 5px;
            }
        """)

        bottom_bar_layout = QHBoxLayout(self.bottom_bar)
        bottom_bar_layout.setContentsMargins(20, 10, 20, 10)
        bottom_bar_layout.setSpacing(15)

        statusCircle = QLabel()
        statusCircle.setFixedSize(18, 18)
        statusCircle.setStyleSheet("background-color: #89b4fa; border-radius: 8px;")
        bottom_bar_layout.addWidget(statusCircle)

        user_profile = QLabel("ABBHHHLEEIISSHHH>>>\nDeveloper")
        user_profile.setStyleSheet("color: #cdd6f4;")
        bottom_bar_layout.addWidget(user_profile)
        bottom_bar_layout.addStretch(1)

        self.resize(1200, 800)
        QTimer.singleShot(0, self.setupLayout)

        try:
            lexer = self.workSpace.lexer()
            font = QFont("JetBrains Mono", 12)
            font.setStyleHint(QFont.TypeWriter)
            lexer.setFont(font)
            lexer.setDefaultFont(font)
            self.workSpace.setFont(font)
            self.workSpace.setLexer(lexer)

            self.api = Qsci.QsciAPIs(lexer)
            self.api.prepare()

            self.workSpace.setIndentationsUseTabs(True)

            self.workSpace.setColor(QColor("#1e1e2e"))
            self.workSpace.setPaper(QColor("#cdd6f4"))
            self.workSpace.setCaretForegroundColor(QColor("#89b4fa"))
            self.workSpace.setCaretLineVisible(True)
            self.workSpace.setCaretLineBackgroundColor(QColor("#313244"))

            try:
                self.workSpace.setWrapMode(Qsci.QsciScintilla.WrapNone)
                self.workSpace.setWrapVisualFlags(Qsci.QsciScintilla.WrapFlagNone)
            except Exception:
                pass

            self.workSpace.setAutoCompletionSource(Qsci.QsciScintilla.AcsAll)
            self.workSpace.setAutoCompletionThreshold(1)
            self.workSpace.setAutoCompletionCaseSensitivity(False)

            self.workSpace.setCallTipsStyle(Qsci.Scintilla.CallTipsContext)
            self.workSpace.setCallTipsVisible(5)

        except Exception:
            pass

        self.lastLabels = []
        try:
            self.workSpace.SCN_CHARADDED.connect(self.onCharAdd)
        except Exception:
            pass

        self.currentFilePath = None

        try:
            self.RootTree.clicked.connect(self.OnFileClickFunction)
        except Exception:
            pass

    def toggleFileTree(self):
        # self.file_tree_container.setVisible(not self.file_tree_container.isVisible())
        if self.file_tree_container.isVisible():
            self.file_tree_container.hide()

        else:
            self.file_tree_container.setVisible(not self.file_tree_container.isVisible())
            self.file_tree_container.setFixedWidth(200)

    def setupLayout(self):
        self.resizeEvent(None)

    def resizeEvent(self, event):
        super().resizeEvent(event)

        window_size = self.size()
        width = window_size.width()
        height = window_size.height()

        bar_height = 80
        bar_width = width * 0.95
        bar_x = (width - bar_width) / 2
        bar_y = height - bar_height - 20
        self.bottom_bar.setGeometry(int(bar_x), int(bar_y), int(bar_width), int(bar_height))
        self.bottom_bar.raise_()

        main_area_width = bar_width
        main_area_height = height - bar_height - 40
        main_area_x = bar_x
        main_area_y = 20
        self.main_area.setGeometry(int(main_area_x), int(main_area_y), int(main_area_width), int(main_area_height))
        self.main_area.raise_()

        run_btn_width = 80
        run_btn_height = 40
        btn_x = self.editor_terminal_container.width() - run_btn_width - 30
        btn_y = 20
        self.runButton.setGeometry(int(btn_x), int(btn_y), int(run_btn_width), int(run_btn_height))
        self.runButton.raise_()

    def FolderFunction(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            try:
                self.treeModel = QFileSystemModel()
                self.treeModel.setRootPath(os.path.join(folder))
                self.terminal.process.write(f"cd {folder} \n".encode())
                self.filetree = QTreeView()
                self.filetree.setModel(self.treeModel)
                self.filetree.setRootIndex(self.treeModel.index(folder))

                for i in reversed(range(self.tree_layout.count())):
                    item = self.tree_layout.itemAt(i)
                    if item is None:
                        continue
                    widget = item.widget()
                    if widget and widget != self.openFolderButton:
                        self.tree_layout.removeWidget(widget)
                        widget.setParent(None)

                self.tree_layout.addWidget(self.filetree)
                self.filetree.clicked.connect(self.OnFileClickFunction)

            except Exception as e:
                if self.debug:
                    print("FolderFunction error:", e)

    def style_workspace_with_lexer(self, lexer):
        font = QFont("JetBrains Mono", 12)

        self.workSpace.setCaretForegroundColor(QColor("#89b4fa"))
        self.workSpace.setCaretLineVisible(True)
        self.workSpace.setCaretLineBackgroundColor(QColor("#313244"))
        self.workSpace.setMarginsForegroundColor(QColor("#a6adc8"))
        self.workSpace.setMarginsBackgroundColor(QColor("#1b1b38"))
        self.workSpace.setMarginLineNumbers(0, True)
        self.workSpace.setMarginWidth(0, "0000")
        self.workSpace.setSelectionBackgroundColor(QColor("#45475a"))
        self.workSpace.setSelectionForegroundColor(QColor("#cdd6f4"))
        self.workSpace.setFont(font)

        colors = {
            "default": "#cdd6f4",
            "keyword": "#f38ba8",
            "number": "#94e2d5",
            "string": "#f9e2af",
            "function": "#a6e3a1",
            "comment": "#6c7086",
            "class": "#89b4fa",
            "operator": "#f5c2e7",
            "background": "#1b1b38"
        }

        if lexer:

            if hasattr(lexer, "Keyword"):
                lexer.setColor(QColor(colors["keyword"]), lexer.Keyword)
            if hasattr(lexer, "Number"):
                lexer.setColor(QColor(colors["number"]), lexer.Number)
            if hasattr(lexer, "String"):
                lexer.setColor(QColor(colors["string"]), lexer.String)
            if hasattr(lexer, "Comment"):
                lexer.setColor(QColor(colors["comment"]), lexer.Comment)
            if hasattr(lexer, "ClassName"):
                lexer.setColor(QColor(colors["class"]), lexer.ClassName)
            if hasattr(lexer, "FunctionMethodName"):
                lexer.setColor(QColor(colors["function"]), lexer.FunctionMethodName)
            if hasattr(lexer, "Operator"):
                lexer.setColor(QColor(colors["operator"]), lexer.Operator)

        self.workSpace.setLexer(lexer)
        self.workSpace.setPaper(QColor("#1b1b38"))
        self.workSpace.setColor(QColor("#cdd6f4"))

    def setLexerForExtension(self, ext):
        lexer_map = {
            ".py": Qsci.QsciLexerPython,
            ".cpp": Qsci.QsciLexerCPP,
            ".c": Qsci.QsciLexerCPP,
            ".h": Qsci.QsciLexerCPP,
            ".hpp": Qsci.QsciLexerCPP,
            ".json": Qsci.QsciLexerJSON,
            ".html": Qsci.QsciLexerHTML,
            ".htm": Qsci.QsciLexerHTML,
            ".css": Qsci.QsciLexerCSS,
            ".js": Qsci.QsciLexerJavaScript,
            ".ts": Qsci.QsciLexerJavaScript,
            ".md": Qsci.QsciLexerMarkdown,
            ".sh": Qsci.QsciLexerBash,
            ".bash": Qsci.QsciLexerBash,
            ".yaml": Qsci.QsciLexerYAML,
            ".yml": Qsci.QsciLexerYAML,
            ".xml": Qsci.QsciLexerXML,
        }

        lexer_class = lexer_map.get(ext)
        return lexer_class() if lexer_class else None

    def OnFileClickFunction(self, index):
        try:
            filePath = self.treeModel.filePath(index)

            self.workSpace.setLexerForFile(filePath)
            self.currentFilePath = filePath

            with open(filePath, 'r', encoding="utf-8", errors="ignore") as f:
                content = f.read()

            self.workSpace.setText(content)

            ext = os.path.splitext(filePath)[1].lower()
            cmd, langId = LSP_SERVERS.get(ext, (["pyright-langserver", "--stdio"], "python"))
            self.lsp = LSPClient(cmd=cmd, languageId=langId, debug=self.debug)

            self.setLexerForExtension(ext)
            lexer = self.setLexerForExtension(ext)
            lexer = self.workSpace.lexer

            if lexer:
                self.style_workspace_with_lexer(lexer)
            else:
                print("No lexer applied for current file")

        except Exception as e:
            self.workSpace.setText(f"Error opening the file...{e}")

    def saveFileFunction(self):
        if self.currentFilePath and os.path.isfile(self.currentFilePath):
            try:
                changes = self.workSpace.text()
                tmp_path = self.currentFilePath + ".tmp"
                with open(tmp_path, "w", encoding="utf-8") as f:
                    f.write(changes)
                os.replace(tmp_path, self.currentFilePath)
            except Exception as e:
                self.workSpace.setText(f"Cannot make changes in the file...{e}")
        else:
            QMessageBox.warning(self, "Warning", "No file selected to save...")


    def _getCursorPositionInfo(self):
        try:
            line, index = self.workSpace.getCursorPosition()
        except Exception:
            line, index = 0, 0
        text = self.workSpace.text()
        if self.currentFilePath:
            uri = "file://" + os.path.abspath(self.currentFilePath)
        else:
            if not hasattr(self, "_tempPath"):
                tempDir = os.path.join(os.getcwd(), ".tmp_lsp")
                os.makedirs(tempDir, exist_ok=True)
                self._tempPath = os.path.join(tempDir, f"untitled_{uuid.uuid4().hex}.py")
            try:
                with open(self._tempPath, "w", encoding="utf-8") as f:
                    f.write(text or "")
            except Exception:
                pass
            uri = "file://" + os.path.abspath(self._tempPath)
        return uri, line, index, text

    def onCharAdd(self, chCode):
        try:

            editor = self.sender()

            if not isinstance(editor, Editor):
                return

            ch = chr(chCode) if isinstance(chCode, int) and 0 <= chCode <= 0x10FFFF else ""

            if not self.lsp:
                return

            uri, line, index, text = self._getCursorPositionInfo()

            if getattr(self.lsp, "lastUri", None) != uri:
                self.lsp.openDocument(uri, text)
                self.lsp.lastUri = uri

            else:
                self.lsp.changeDocument(uri, text)

            if ch.isalnum() or ch in {".", "_"}:
                self.lsp.requestCompletion(uri, line, index, self.handleCompletionResponse)

            if ch == "(":
                self.lsp.signatureHelp(uri, line, index, callback=self.handleSignatureResponse)

            if ch == ".":
                self.lsp.requestCompletion(uri, line, index, self.handleCompletionResponse)
                # self.autoCompleteFromAPIs()

        except Exception as e:
            if getattr(self, "debug", False):
                print("Error in onCharAdd: ", e)

    def handleSignatureResponse(self, response):
        try:

            if not response or not response.get("signatures"):
                return

            if isinstance(response, str):
                import json
                response = json.loads(response)

            signatures = response.get("signatures", [])
            if not signatures:
                return

            active_sig_index = response.get("activeSignature", 0)
            sig = signatures[active_sig_index] if 0 <= active_sig_index < len(signatures) else signatures[0]

            label = sig.get("label", "")

            if not label:
                return

            QTimer.singleShot(0, lambda: self.safeUpdateUI(label))

        except Exception as e:
            print("Error in handleSignatureResponse:", e)

    def safeUpdateUI(self, label):
        try:
            if self.workSpace.SendScintilla(Qsci.QsciScintilla.SCI_AUTOCACTIVE) != 0:
                self.workSpace.SendScintilla(Qsci.QsciScintilla.SCI_AUTOCCANCEL)

            pos = self.workSpace.SendScintilla(Qsci.QsciScintilla.SCI_GETCURRENTPOS)

            if self.workSpace.SendScintilla(Qsci.QsciScintilla.SCI_CALLTIPACTIVE) != 0:
                self.workSpace.SendScintilla(Qsci.QsciScintilla.SCI_CALLTIPCANCEL)

            self.workSpace.SendScintilla(Qsci.QsciScintilla.SCI_CALLTIPSHOW, pos, label.encode("utf-8"))

        except Exception as e:
            print("UI ERROR in safeUpdateUI:", e)

    def handleCompletionResponse(self, response):
        try:
            if not response:
                return

            if getattr(self, "debug", False):
                print("Completion response:", response)

            if isinstance(response, str):
                import json
                response = json.loads(response)

            items = response.get("items", [])
            if not items:
                return

            completions = []
            for item in items:
                label = item.get("label") or item.get("insertText")
                if label:
                    completions.append(label)

            def safeUpdateUI():
                try:
                    line, index = self.workSpace.getCursorPosition()
                    lineContent = self.workSpace.text(line)

                    textBeforeCursor = lineContent[:index]

                    prefixStart = 0

                    for i in range(len(textBeforeCursor) -1, -1, -1):
                        char = textBeforeCursor[i]

                        if not (char.isalnum() or char == "_" or char == "."):
                            prefixStart = i + 1
                            break

                    prefix_len = index - prefixStart

                    if textBeforeCursor.endswith("."):
                        prefix_len = 1
                    self.autoCompletionFromList(prefix_len, completions)

                except Exception as e:
                    if getattr(self, "debug", False):
                        print(f"UI ERROR: The autoCompletionFromList command failed on the main thread: {e}")

            QTimer.singleShot(0, safeUpdateUI)

        except Exception as e:
            if getattr(self, "debug", False):
                print("Error in handleCompletionResponse:", e)

    def _do_completion_request(self):
        try:
            if not getattr(self, "lsp", None):
                return
            uri, line, char, text = self._getCursorPositionInfo()

            try:
                if getattr(self.lsp, "lastUri", None) != uri:
                    self.lsp.openDocument(uri, text)
                else:
                    self.lsp.changeDocument(uri, text)
            except Exception as e:
                if self.debug:
                    print("Error updating LSP before completion: ", e)

            def completion_cb(labels):
                try:
                    if not labels:
                        self.lastLabels = []
                        return

                    normalized = []
                    seen = set()
                    for s in labels:
                        try:
                            ss = str(s)
                        except Exception:
                            continue
                        if ss and ss not in seen:
                            normalized.append(ss)
                            seen.add(ss)

                    if not normalized:
                        self.lastLabels = []
                        return

                    self.lastLabels = normalized

                    try:
                        lexer = self.workSpace.lexer()
                        self.api = Qsci.QsciAPIs(lexer)
                    except Exception:
                        self.api = None

                    if self.api:
                        for n in normalized:
                            try:
                                self.api.add(n)
                            except Exception:
                                pass
                        try:
                            self.api.prepare()
                        except Exception:
                            pass

                    try:
                        pos = self.workSpace.SendScintilla(Qsci.QsciScintilla.SCI_GETCURRENTPOS)
                        start = self.workSpace.SendScintilla(Qsci.QsciScintilla.SCI_WORDSTARTPOSITION, pos, True)
                        prefixLen = max(0, pos - start)
                    except Exception:
                        prefixLen = 0

                    QTimer.singleShot(0, lambda: self.autoCompletionFromList(prefixLen, normalized))
                except Exception as e:
                    print("Autocompletion failed:", e)

            self.lsp.requestCompletion(uri, line, char, completion_cb)
        except Exception as e:
            if self.debug:
                print("Error requesting completion:", e)

    def autoCompletionFromList(self, prefixLen, suggestions):
        try:
            lexer = self.workSpace.lexer

            if not lexer:
                return

            if lexer:
                self.api = Qsci.QsciAPIs(lexer)

            self.api.clear()

            for s in suggestions:
                try:
                    self.api.add(s)
                except Exception as e:
                    print(f"Exception occured: {e}")

            self.api.prepare()
            lexer.setAPIs(self.api)

            self.workSpace.setLexer(lexer)

            if prefixLen >= self.workSpace.autoCompletionThreshold():
                self.workSpace.setAutoCompletionSource(Qsci.QsciScintilla.AcsAll)
                self.workSpace.setAutoCompletionThreshold(1)
                self.workSpace.setAutoCompletionCaseSensitivity(False)
                self.workSpace.setAutoCompletionUseSingle(False)

                self.workSpace.autoCompleteFromAPIs()
            QTimer.singleShot(0, self.workSpace.ensureCursorVisible)

        except Exception as e:
            print("Auto-completion popup failed: ", e)

    def compileAndRun(self):
        try:
            if not getattr(self, "currentFilePath", None):
                QMessageBox.warning(self, "Error", "Please select a file to run.")
                return

            file_path = self.currentFilePath

            if hasattr(self, "tempProcess") and self.tempProcess.state() != QProcess.NotRunning:
                self.tempProcess.kill()
                self.tempProcess.waitForFinished()

            if file_path.endswith(".py"):
                self.tempProcess = QProcess(self)
                self.tempProcess.setProcessChannelMode(QProcess.MergedChannels)
                self.tempProcess.readyReadStandardOutput.connect(self.scriptOutput)

                python_exec = sys.executable or "/usr/local/bin/python3"
                self.tempProcess.start(python_exec, [file_path])

            elif file_path.endswith(".c"):
                self.tempProcess = QProcess(self)
                self.tempProcess.setProcessChannelMode(QProcess.MergedChannels)
                self.tempProcess.readyReadStandardOutput.connect(self.scriptOutput)

                out_bin = os.path.join(os.path.dirname(file_path), "a.out")

                self.tempProcess.start("gcc", [file_path, "-o", out_bin])
                self.tempProcess.waitForFinished()
                if os.path.exists(out_bin):
                    self.tempProcess = QProcess(self)
                    self.tempProcess.setProcessChannelMode(QProcess.MergedChannels)
                    self.tempProcess.readyReadStandardOutput.connect(self.scriptOutput)
                    self.tempProcess.start(out_bin)

        except Exception as e:
            QMessageBox.critical(self, "Run Error", str(e))

    def scriptOutput(self):
        try:
            data = bytes(self.tempProcess.readAllStandardOutput()).decode(errors="ignore")
        except Exception:
            data = ""
        try:
            self.terminal.output.moveCursor(self.terminal.output.textCursor().End)
            self.terminal.output.insertPlainText(data)
            self.terminal.output.moveCursor(self.terminal.output.textCursor().End)
        except Exception:
            pass

    def closeEvent(self, event):
        try:
            if getattr(self, "lsp", None):
                try:
                    self.lsp.shutdown()
                except Exception:
                    pass
            try:
                if getattr(self.workSpace, "completionThread", None) and self.workSpace.completionThread.isRunning():
                    self.workSpace.completionThread.requestInterruption()
                    self.workSpace.completionThread.quit()
                    self.workSpace.completionThread.wait(200)
            except Exception:
                pass

            try:
                if getattr(self.lsp, "reader", None):
                    self.lsp.reader.stop()
                if getattr(self.lsp, "stderr_reader", None):
                    self.lsp.stderr_reader.stop()
            except Exception:
                pass

            try:
                if hasattr(self, "terminal") and hasattr(self.terminal, "process"):
                    proc = self.terminal.process
                    if proc and proc.state() != QProcess.NotRunning:
                        proc.write(b"exit\n")
                        proc.waitForFinished(500)
                        if proc.state() != QProcess.NotRunning:
                            proc.kill()
            except Exception:
                pass

            try:
                if hasattr(self, "completionThread") and self.completionThread:
                    if self.completionThread.isRunnung():
                        self.completionThread.requestInterruption()
                        self.completionThread.quit()
                        self.completionThread.wait(500)

            except Exception as e:
                pass

        except Exception as e:
            print(f"Error while closing: {e}")

        event.accept()


if __name__ == "__main__":
    pyright_cmd = None
    debug = False
    if len(sys.argv) > 1:
        if not sys.argv[1].startswith('-'):
            pyright_cmd = [sys.argv[1], '--stdio']
    if '--debug' in sys.argv:
        debug = True

    app = QApplication(sys.argv)

    styleSheet = """
/* Main Window */
QMainWindow {
    background-color: #1e1e2e; /* dark background */
    color: #cdd6f4;
}

/* Menu Bar */
QMenuBar {
    background-color: #181825;
    color: #cdd6f4;
    border-bottom: 1px solid #313244;
}
QMenuBar::item:selected {
    background-color: #313244;
}
QMenu {
    background-color: #181825;
    color: #cdd6f4;
    border: 1px solid #313244;
}
QMenu::item:selected {
    background-color: #45475a;
}

/* Status Bar */
QStatusBar {
    background-color: #181825;
    color: #a6adc8;
    border-top: 1px solid #313244;
}

/* Buttons */
QPushButton {
    background-color: #313244;
    color: #cdd6f4;
    border-radius: 6px;
    padding: 5px 10px;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #45475a;
}
QPushButton:pressed {
    background-color: #585b70;
}

/* TreeView (e.g. file explorer) */
QTreeView {
    background-color: #1e1e2e;
    color: #cdd6f4;
    border: None;
    selection-background-color: #45475a;
    selection-color: #cdd6f4;
    font-size: 12px;
}

/* Terminal / PlainTextEdit */
QPlainTextEdit, QTextEdit {
    background-color: #11111b;
    color: #cdd6f4;
    border: 1px solid #313244;
    border-radius: 8px;
}

/* Line Edit (search bar, etc.) */
QLineEdit {
    background-color: #11111b;
    color: #cdd6f4;
    border: 1px solid #313244;
    border-radius: 6px;
    padding: 4px;
}
QLineEdit:focus {
    border: 1px solid #89b4fa; /* blue accent */
}

/* Scrollbars */
QScrollBar:vertical {
    border: none;
    background: #1e1e2e;
    width: 10px;
}
QScrollBar::handle:vertical {
    background: #45475a;
    border-radius: 5px;
}
QScrollBar::handle:vertical:hover {
    background: #585b70;
}

QScrollBar:horizontal {
    border: none;
    background: #1e1e2e;
    height: 10px;
}
QScrollBar::handle:horizontal {
    background: #45475a;
    border-radius: 5px;
}
QScrollBar::handle:horizontal:hover {
    background: #585b70;
}
"""

    app.setStyleSheet(styleSheet)

    window = MainWindow(debug=debug)
    window.show()
    sys.exit(app.exec_())
