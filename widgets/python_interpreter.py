# PythonInterpreter + OutputRedirect
import sys
from PyQt6.QtWidgets import QVBoxLayout, QPushButton, QWidget, QToolBar, QPushButton, QTextEdit
from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtCore import QSize
from utils.paths import resource_path

class PythonInterpreter(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowIcon(QIcon(resource_path("icons/python.png")))
        self.setWindowTitle("Python Interpreter")
        self.resize(600, 400)

        self.layout = QVBoxLayout()
        self.code_input = QTextEdit(self)
        self.code_input.setPlaceholderText("Write your Python code here...")
        self.layout.addWidget(self.code_input)

        self.run_button = QPushButton("Run Code", self)
        self.run_button.clicked.connect(self.execute_code)
        self.layout.addWidget(self.run_button)

        self.output_display = QTextEdit(self)
        self.output_display.setReadOnly(True)
        self.layout.addWidget(self.output_display)

        self.setLayout(self.layout)

        self.toolbar()

    def execute_code(self):
        code = self.code_input.toPlainText()
        try:
            old_stdout = sys.stdout
            sys.stdout = OutputRedirect(self.output_display)
            exec(code)
        except Exception as e:
            self.output_display.append(f"Error: {e}")
        finally:
            sys.stdout = old_stdout

    def toolbar(self):
        toolbar = QToolBar()
        toolbar.setIconSize(QSize(15, 15))

        run = QAction(QIcon(resource_path("icons/polygon.png"), "Draw", self))
        run.triggered.connect(self.execute_code)
        toolbar.addAction(run)

class OutputRedirect:
    def __init__(self, text_edit):
        self.text_edit = text_edit

    def write(self, text):
        self.text_edit.append(text)

    def flush(self):
        pass
    
    