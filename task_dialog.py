from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QLineEdit,
                           QTextEdit, QDateEdit, QComboBox, QDialogButtonBox,
                           QLabel, QFrame, QMainWindow)
from PyQt5.QtCore import Qt, QDate
from PyQt5.QtGui import QFont, QIcon

class TaskDialog(QDialog):
    def __init__(self, parent=None, task=None):
        super().__init__(parent)
        self.task = task
        self.setWindowTitle("Task Details")
        self.setModal(True)
        self.setMinimumWidth(500)
        self.setStyleSheet("""
            QDialog {
                background-color: #f5f5f5;
            }
            QLineEdit, QTextEdit, QDateEdit, QComboBox {
                padding: 8px;
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 4px;
                min-height: 25px;
            }
            QLineEdit:focus, QTextEdit:focus, QDateEdit:focus, QComboBox:focus {
                border: 2px solid #2196F3;
            }
            QLabel {
                color: #424242;
                font-weight: bold;
            }
            QPushButton {
                padding: 8px 16px;
                background-color: #2196F3;
                color: white;
                border: none;
                border-radius: 4px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton[text="Cancel"] {
                background-color: #757575;
            }
            QPushButton[text="Cancel"]:hover {
                background-color: #616161;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                image: url("down_arrow.png");
                width: 12px;
                height: 12px;
            }
        """)
        self.init_ui()
        if self.task:
            self.setWindowTitle("Edit Task")
            self.title_edit.setText(task.title)
            self.description_edit.setPlainText(task.description)
            if task.due_date:
                self.due_date_edit.setDate(QDate.fromString(str(task.due_date), "yyyy-MM-dd"))
            self.status_combo.setCurrentText(task.status)

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # Title header
        header = QLabel("Task Information")
        header.setFont(QFont("Segoe UI", 16, QFont.Bold))
        header.setStyleSheet("color: #1976D2; margin-bottom: 10px;")
        layout.addWidget(header)

        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        separator.setStyleSheet("background-color: #ddd; margin-bottom: 15px;")
        layout.addWidget(separator)

        form_layout = QFormLayout()
        form_layout.setSpacing(15)
        form_layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        # Create form fields with enhanced styling
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("Enter task title")
        
        self.description_edit = QTextEdit()
        self.description_edit.setPlaceholderText("Enter task description")
        self.description_edit.setMinimumHeight(100)
        
        self.due_date_edit = QDateEdit()
        self.due_date_edit.setDate(QDate.currentDate())
        self.due_date_edit.setCalendarPopup(True)
        self.due_date_edit.setDisplayFormat("yyyy-MM-dd")
        
        self.status_combo = QComboBox()
        self.status_combo.addItems(["Not Started", "In Progress", "Completed"])
        self.status_combo.setItemData(0, "#757575", Qt.TextColorRole)
        self.status_combo.setItemData(1, "#FFA726", Qt.TextColorRole)
        self.status_combo.setItemData(2, "#4CAF50", Qt.TextColorRole)

        # Add styled form rows
        form_layout.addRow("Title:", self.title_edit)
        form_layout.addRow("Description:", self.description_edit)
        form_layout.addRow("Due Date:", self.due_date_edit)
        form_layout.addRow("Status:", self.status_combo)

        layout.addLayout(form_layout)

        # Add buttons with custom styling
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            Qt.Horizontal, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        
        # Add some spacing before buttons
        layout.addSpacing(10)
        layout.addWidget(buttons)

    def get_task_data(self):
        due_date = self.due_date_edit.date().toPyDate()  # Convert QDate to Python date
        return {
            'title': self.title_edit.text(),
            'description': self.description_edit.toPlainText(),
            'due_date': due_date,
            'status': self.status_combo.currentText()
        }

    def accept(self):
        super().accept()
        # Notify parent window to check due dates
        if isinstance(self.parent(), QMainWindow):
            self.parent().check_due_dates()
