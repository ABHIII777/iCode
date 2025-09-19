from PyQt5 import Qsci
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *
from PyQt5.Qsci import *

from CompletionThread import *

import os

API = "AIzaSyAG_lnl2Cz8gg0IHoUTHGGQ50LqYq-8EM4"
URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={API}"

class Editor(Qsci.QsciScintilla):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._ghostText = ""
        self.completionThread = None
        self._placeHolder = ""
        self.filePath = None
        self.setUtf8(True)

        font = QFont("JetBrains Mono", 12)
        self.setFont(font)

        self.lexer = None
        self.setLexer(None)

        self.SendScintilla(Qsci.QsciScintilla.SCI_STYLESETFONT, 33, bytes(font.family(), "utf-8"))
        self.SendScintilla(Qsci.QsciScintilla.SCI_STYLESETSIZE, 33, 12)
        self.SendScintilla(Qsci.QsciScintilla.SCI_STYLESETFORE, 33, QColor("#a6adc8").rgb() & 0xffffff)
        self.SendScintilla(Qsci.QsciScintilla.SCI_STYLESETBACK, 33, QColor("#1e1e2e").rgb() & 0xffffff)

        self.SendScintilla(Qsci.QsciScintilla.SCI_ANNOTATIONSETVISIBLE, Qsci.QsciScintilla.ANNOTATION_BOXED)

        self.setMarginsBackgroundColor(QColor("#1e1e2e"))
        self.setMarginsForegroundColor(QColor("#a6adc8"))
        
        self.setAutoCompletionSource(Qsci.QsciScintilla.AcsAPIs)   
        self.setAutoCompletionThreshold(1)             
        self.setAutoCompletionReplaceWord(True)               
        self.setAutoCompletionFillupsEnabled(True) 

        self._aiTimer = QTimer(self)
        self._aiTimer.setSingleShot(True)
        self._aiTimer.setInterval(1000)
        self._aiTimer.timeout.connect(self.requestCompletion)

        self.completionTimer = QTimer(self)
        self.completionTimer.setSingleShot(True)
        self.completionTimer.timeout.connect(self.requestCompletion)

        self.setCallTipsBackgroundColor(Qt.white)
        self.setCallTipsForegroundColor(Qt.black)
        self.setCallTipsStyle(Qsci.QsciScintilla.CallTipsNoContext)
        self.setCallTipsPosition(Qsci.QsciScintilla.CallTipsAboveText)
        self.setCallTipsVisible(1)

    def setLexerForFile(self, filePath: str):

        ext = os.path.splitext(filePath)[1].lower()

        if ext == ".py":
            lexer = Qsci.QsciLexerPython()
        elif ext in [".cpp", ".cc", ".cxx", ".c"]:
            lexer = Qsci.QsciLexerCPP()
        elif ext in [".js", ".jsx"]:
            lexer = Qsci.QsciLexerJavaScript()
        elif ext in [".html", ".htm"]:
            lexer = Qsci.QsciLexerHTML()
        elif ext == ".css":
            lexer = Qsci.QsciLexerCSS()
        elif ext in [".java"]:
            lexer = Qsci.QsciLexerJava()
        elif ext in [".php"]:
            lexer = Qsci.QsciLexerPHP()
        elif ext in [".json"]:
            lexer = Qsci.QsciLexerJSON()
        elif ext in [".sh", ".bash"]:
            lexer = Qsci.QsciLexerBash()
        else:
            lexer = None   # fallback: plain text

        if lexer:
            lexer.setDefaultFont(self.font())
            self.setLexer(lexer)
            self.lexer = lexer
        else:
            self.setLexer(None)
            self.lexer = None

    def showCompletions(self, prefixLen, suggestions):
        if suggestions:
            self.autoCShow(prefixLen, " ".join(suggestions))

    def requestCompletion(self):
        try:
            pos = int(self.SendScintilla(Qsci.QsciScintilla.SCI_GETCURRENTPOS))
            text = self.text()
            beforeCursor = text[:pos]
            afterCursor = text[pos:]
        except Exception:
            beforeCursor = self.text()
            afterCursor = ""

        try:
            if self.completionThread and self.completionThread.isRunning():
                self.completionThread.requestInterruption()
                self.completionThread.quit()
                self.completionThread.wait(500)
        except Exception:
            pass

        prompt = f"""
Continue writing the following code and I only need what could possibly be the code after the cursor:

Code before cursor:
{beforeCursor}

Code after cursor:
{afterCursor}
"""
        
        if not beforeCursor.strip() and not afterCursor.strip():
            self._placeHolder = ""
            self._ghostText = ""
            self.viewport().update()
            return


        self.completionThread = CompletionThread(API, prompt, parent=self)
        self.completionThread.suggestionReady.connect(self.showPlaceholder)
        self.completionThread.finished.connect(self.completionThread.deleteLater)
        self.completionThread.start()

    def setGhostText(self, text:str):
        if text == self._ghostText:
            return

        self._ghostText = text

        if not self._ghostText:
            self._ghostPixmap = None
            self.viewport().update()
            return

        font = QFont(self.font())
        fm = QFontMetrics(font)
        lineHeight = fm.lineSpacing()

        lines = text.splitlines()
        w = max(fm.width(line) for line in lines)
        h = lineHeight * len(lines)

        pixmap = QPixmap(w, h)
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        painter.setPen(QColor(150,150,150))
        painter.setFont(font)

        for i, line in enumerate(lines):
            painter.drawText(0, (i * lineHeight) + fm.ascent(), line)

        painter.end()
        
        self._ghostPixmap = pixmap
        self.viewport().update()

    def paintEvent(self, event):
        super().paintEvent(event)

        if self._ghostText:
            painter = QPainter(self.viewport())
            painter.setPen(QColor(150,150,150))

            font = QFont(self.font())
            painter.setFont(font)

            pos = self.SendScintilla(Qsci.QsciScintilla.SCI_GETCURRENTPOS)
            x = self.SendScintilla(Qsci.QsciScintilla.SCI_POINTXFROMPOSITION, 0, pos)
            y = self.SendScintilla(Qsci.QsciScintilla.SCI_POINTYFROMPOSITION, 0, pos)

            fm = QFontMetrics(font)
            lineHeight = fm.lineSpacing()

            for i, line in enumerate(self._ghostText.splitlines()):
                painter.drawText(x, y + (i * lineHeight) + fm.ascent(), line)
                
            painter.end()

    def showPlaceholder(self, suggestion: str):
        if not suggestion or not suggestion.strip():
            self._placeHolderText = ""
            self._placeHolderPos = None
            self._ghostText = ""

            try:
                self.annotationClearAll()
            except Exception:
                pass
            return

        try:
            clean = suggestion.replace("```", "")
            clean = clean.replace("`", "")
            clean = clean.replace("python", "")
            clean = clean.lstrip("\n")
            clean = clean.rstrip()
            self._ghostText = clean

            if not clean:
                return

            self.viewport().update()

        except Exception as e:
            print("Calltipp error: ", e)
        

    def keyPressEvent(self, event):

        if event.key() == Qt.Key_Tab and self._ghostText:
            try:
                pos = self.SendScintilla(Qsci.QsciScintilla.SCI_GETCURRENTPOS)

                self.SendScintilla(Qsci.QsciScintilla.SCI_INSERTTEXT, pos, self._ghostText.encode("utf-8"))

                newPos = pos + len(self._ghostText)
                self.SendScintilla(Qsci.QsciScintilla.SCI_SETCURRENTPOS, newPos)
                self.SendScintilla(Qsci.QsciScintilla.SCI_SETANCHOR, newPos)

                self._placeHolder = ""
                self._ghostText = ""
                self.viewport().update()

                return

            except Exception as e:
                print("Some error occured: ", e)

        if self._ghostText and event.key() not in (Qt.Key_Shift, Qt.Key_Control, Qt.Key_Alt):
            self._ghostText = ""
            self.viewport().update()
        
        self.completionTimer.start(1000)
        super().keyPressEvent(event)

        try:
            ch = event.text()
        except Exception:
            ch = ""

        ch = event.text()
        if ch and (ch == "." or ch == "_" or ch.isalnum() or ch == "("):
            try:
                self._aiTimer.start()
                pass
            except Exception:
                pass