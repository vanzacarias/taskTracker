from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, 
                           QTableWidget, QPushButton, QHBoxLayout,
                           QTableWidgetItem, QMessageBox, QHeaderView, QStyle,
                           QLabel, QFrame, QMenuBar, QMenu, QAction, QToolTip,
                           QWidget, QSizePolicy, QProgressBar)
from PyQt5.QtCore import (Qt, QDate, QPropertyAnimation, QEasingCurve, 
                         QTimer, pyqtProperty, QThread, pyqtSignal)
from PyQt5.QtGui import QFont, QPalette, QColor, QIcon
from .task_dialog import TaskDialog
from task_manager import TaskManager
from datetime import datetime, timedelta

class BlinkingLabel(QLabel):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self._opacity = 1.0
        self._animation = QPropertyAnimation(self, b"opacity", self)
        self._animation.setDuration(800)  # Faster animation cycle
        self._animation.setLoopCount(-1)   # Infinite loop
        self._animation.setStartValue(1.0)
        self._animation.setEndValue(0.4)   # Less transparent for better visibility
        self._animation.setEasingCurve(QEasingCurve.InOutCubic)  # Smoother animation
        self._color = "#F57C00"  # Default color
        self.setMinimumWidth(30)  # Ensure consistent width
        self.setAlignment(Qt.AlignCenter)  # Center the warning symbol
        
    def get_opacity(self):
        return self._opacity
        
    def set_opacity(self, opacity):
        self._opacity = opacity
        color = self.property('customColor') or self._color
        # Convert hex to RGB and apply opacity
        r, g, b = tuple(int(color.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
        self.setStyleSheet(f"""
            QLabel {{
                color: rgba({r}, {g}, {b}, {opacity});
                font-size: 16px;  /* Larger warning symbol */
                font-weight: bold;
                padding: 8px 16px;
                margin: 0;
                background: transparent;
                border-radius: 4px;
            }}
            QLabel:hover {{
                background: rgba({r}, {g}, {b}, 0.1);
            }}
        """)
        
    opacity = pyqtProperty(float, get_opacity, set_opacity)
    
    def setProperty(self, name, value):
        if name == 'customColor':
            self._color = value
            self.set_opacity(self._opacity)  # Refresh style with new color
        super().setProperty(name, value)
        
    def start_blinking(self):
        self.set_opacity(1.0)  # Reset opacity before starting
        self._animation.start()
        
    def stop_blinking(self):
        self._animation.stop()
        self.set_opacity(1.0)  # Ensure full opacity when stopped

class TaskLoadThread(QThread):
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, task_manager):
        super().__init__()
        self.task_manager = task_manager

    def run(self):
        try:
            tasks = self.task_manager.list_tasks(force_refresh=True)
            self.finished.emit(tasks)
        except Exception as e:
            self.error.emit(str(e))

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.task_manager = TaskManager()
        self.setWindowTitle("Task Tracker")
        self.setGeometry(100, 100, 1000, 700)
        self.warning_action = None
        self.task_ids = []
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5;
            }
            QTableWidget {
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 4px;
                gridline-color: #eee;
            }
            QTableWidget::item {
                padding: 5px;
            }
            QTableWidget::item:selected {
                background-color: #e3f2fd;
                color: black;
            }
            QMenuBar {
                background-color: #2196F3;
                color: white;
            }
            QMenuBar::item {
                padding: 8px 16px;
                background-color: transparent;
                color: white;
            }
            QMenuBar::item:selected {
                background-color: #1976D2;
            }
            QMenu {
                background-color: white;
                border: 1px solid #ddd;
            }
            QMenu::item {
                padding: 8px 20px;
                color: #424242;
            }
            QMenu::item:selected {
                background-color: #e3f2fd;
            }
            QToolTip {
                background-color: #424242;
                color: white;
                border: 1px solid #616161;
                border-radius: 6px;
                padding: 12px;
                font-size: 12px;
                font-family: 'Segoe UI';
                max-width: 400px;
                opacity: 230;
            }
            QLabel#warningLabel {
                color: #F57C00;
                font-weight: bold;
                padding: 8px 16px;
                margin: 0;
                background: transparent;
            }
            QLabel#warningLabel[urgent="true"] {
                color: #D32F2F;
            }
            QLabel#warningLabel[today="true"] {
                color: #F57C00;
            }
        """)
        self.loading_indicator = QProgressBar()
        self.loading_indicator.setMaximum(0)  # Indeterminate progress
        self.loading_indicator.setMinimum(0)
        self.loading_indicator.setTextVisible(False)
        self.loading_indicator.setStyleSheet("""
            QProgressBar {
                border: none;
                background: transparent;
                height: 2px;
            }
            QProgressBar::chunk {
                background-color: #2196F3;
            }
        """)
        self.loading_indicator.hide()
        self.init_ui()
        
        # Load tasks immediately after UI initialization
        QTimer.singleShot(0, self.initial_load)
        
        # Set up periodic refresh
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh_tasks)
        self.refresh_timer.start(60000)  # Refresh every minute

    def initial_load(self):
        """Initial load of tasks with loading indicator"""
        self.loading_indicator.show()
        self.load_thread = TaskLoadThread(self.task_manager)
        self.load_thread.finished.connect(self._on_load_complete)
        self.load_thread.error.connect(self._on_load_error)
        self.load_thread.start()

    def _on_load_complete(self, tasks):
        """Handle completed task loading"""
        self.loading_indicator.hide()
        self.refresh_tasks()
        self.check_due_dates()

    def _on_load_error(self, error_message):
        """Handle task loading error"""
        self.loading_indicator.hide()
        QMessageBox.critical(self, "Loading Error",
            f"Failed to load tasks: {error_message}")

    def init_ui(self):
        # Create menubar
        menubar = self.menuBar()
        
        # Create Tasks menu
        tasks_menu = menubar.addMenu('Tasks')
        
        # Add task action
        add_action = QAction('Add Task', self)
        add_action.setStatusTip('Add a new task')
        add_action.triggered.connect(self.add_task)
        tasks_menu.addAction(add_action)
        
        # Edit task action
        edit_action = QAction('Edit Task', self)
        edit_action.setStatusTip('Edit selected task')
        edit_action.triggered.connect(self.edit_task)
        tasks_menu.addAction(edit_action)
        
        # Delete task action
        delete_action = QAction('Delete Task', self)
        delete_action.setStatusTip('Delete selected task')
        delete_action.triggered.connect(self.delete_task)
        tasks_menu.addAction(delete_action)

        # Add Database menu
        db_menu = menubar.addMenu('Database')
        
        # Backup action
        backup_action = QAction('Create Backup', self)
        backup_action.setStatusTip('Create a backup of the database')
        backup_action.triggered.connect(self.create_backup)
        db_menu.addAction(backup_action)
        
        # Optimize action
        optimize_action = QAction('Optimize Database', self)
        optimize_action.setStatusTip('Optimize database performance')
        optimize_action.triggered.connect(self.optimize_database)
        db_menu.addAction(optimize_action)
        
        # View Stats action
        stats_action = QAction('View Statistics', self)
        stats_action.setStatusTip('View database statistics')
        stats_action.triggered.connect(self.show_statistics)
        db_menu.addAction(stats_action)

        # Create a spacer widget to push the warning label to the right
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        menubar.setCornerWidget(spacer, Qt.TopLeftCorner)

        # Create warning label directly in menubar
        self.warning_label = BlinkingLabel('⚠')
        self.warning_label.setProperty('customColor', '#F57C00')
        self.warning_label.setVisible(False)
        self.warning_label.setToolTip('Tasks Due Soon')
        menubar.setCornerWidget(self.warning_label, Qt.TopRightCorner)
        
        # Central widget setup
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)

        # Add loading indicator at the top
        layout.addWidget(self.loading_indicator)

        # Create task table
        self.task_table = QTableWidget()
        self.task_table.setColumnCount(4)
        self.task_table.setHorizontalHeaderLabels(["Title", "Description", "Due Date", "Status"])
        self.task_table.horizontalHeader().setStyleSheet("""
            QHeaderView::section {
                background-color: #2196F3;
                color: white;
                padding: 8px;
                border: none;
                font-weight: bold;
            }
        """)
        
        # Set column widths
        self.task_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.task_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.task_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.task_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        
        self.task_table.verticalHeader().setVisible(False)
        self.task_table.setAlternatingRowColors(True)
        self.task_table.setShowGrid(True)
        self.task_table.setStyleSheet(self.task_table.styleSheet() + """
            QTableWidget {
                alternate-background-color: #f8f9fa;
            }
        """)
        layout.addWidget(self.task_table)

    def check_due_dates(self):
        today = datetime.now().date()
        warning_tasks = []
        
        for task in self.task_manager.list_tasks():
            if task.due_date and task.status != "Completed":
                days_remaining = task.days_until_due()
                
                if days_remaining is not None:
                    warning_reason = None
                    if days_remaining < 0:
                        warning_reason = "OVERDUE"
                    elif days_remaining == 0:
                        warning_reason = "DUE TODAY"
                    elif days_remaining <= 3:
                        warning_reason = f"DUE IN {days_remaining} DAYS"
                        
                    if warning_reason:
                        warning_tasks.append((task, days_remaining, warning_reason))
        
        if warning_tasks:
            tooltip_text = "⚠ Tasks Requiring Attention:\n\n"
            
            # Sort tasks by urgency (overdue first, then by days remaining)
            warning_tasks.sort(key=lambda x: (x[1] if x[1] >= 0 else -999))
            
            for task, days, reason in warning_tasks:
                status_indicator = "🔴" if days < 0 else "🟡" if days == 0 else "🟠"
                tooltip_text += f"{status_indicator} {task.title}\n"
                tooltip_text += f"   • Status: {task.status}\n"
                tooltip_text += f"   • Due Date: {task.due_date.strftime('%Y-%m-%d')}\n"
                tooltip_text += f"   • Warning: {reason}\n\n"
            
            self.warning_label.setVisible(True)
            self.warning_label.setToolTip(tooltip_text.strip())
            
            # Style the warning icon based on urgency
            if any(days < 0 for _, days, _ in warning_tasks):  # Overdue tasks
                self.warning_label.setProperty('customColor', '#D32F2F')
                self.warning_label.start_blinking()
            elif any(days == 0 for _, days, _ in warning_tasks):  # Due today
                self.warning_label.setProperty('customColor', '#F57C00')
                self.warning_label.start_blinking()
            else:  # Due soon
                self.warning_label.setProperty('customColor', '#FFA726')
                self.warning_label.stop_blinking()
            self.warning_label.style().unpolish(self.warning_label)
            self.warning_label.style().polish(self.warning_label)
        else:
            self.warning_label.stop_blinking()
            self.warning_label.setVisible(False)

    def refresh_tasks(self):
        """Refresh tasks with loading indicator"""
        if not self.loading_indicator.isVisible():
            self.loading_indicator.show()
            self.load_thread = TaskLoadThread(self.task_manager)
            self.load_thread.finished.connect(self._refresh_table_data)
            self.load_thread.error.connect(self._on_load_error)
            self.load_thread.start()

    def _refresh_table_data(self, tasks):
        """Update table with loaded tasks"""
        self.loading_indicator.hide()
        self.task_table.setRowCount(0)
        self.task_table.setRowCount(len(tasks))
        self.task_ids = []
        
        for row, task in enumerate(tasks):
            self.task_ids.append(task.id)
            
            # Title cell with status indicator
            title = ("✓ " if task.status == "Completed" else "")
            title += task.title
            title_item = QTableWidgetItem(title)
            title_item.setFont(QFont("Segoe UI", 9))
            if task.status == "Completed":
                title_item.setForeground(QColor("#2E7D32"))
            self.task_table.setItem(row, 0, title_item)
            
            # Description cell
            desc_item = QTableWidgetItem(task.description)
            desc_item.setFont(QFont("Segoe UI", 9))
            self.task_table.setItem(row, 1, desc_item)
            
            # Due date cell with formatted date and urgency indicator
            date_str = task.due_date.strftime("%Y-%m-%d") if task.due_date else ""
            days_remaining = task.days_until_due()
            if days_remaining is not None:
                if days_remaining < 0:
                    date_str = f"⚠ OVERDUE: {date_str}"
                elif days_remaining == 0:
                    date_str = f"⏰ DUE TODAY: {date_str}"
                elif days_remaining <= 3:
                    date_str = f"📅 {date_str} ({days_remaining} days left)"
                else:
                    date_str = f"📅 {date_str}"
                    
            date_item = QTableWidgetItem(date_str)
            date_item.setFont(QFont("Segoe UI", 9))
            date_item.setTextAlignment(Qt.AlignCenter)
            
            # Color code the date based on urgency
            if days_remaining is not None:
                if days_remaining < 0:  # Overdue
                    date_item.setForeground(QColor("#D32F2F"))
                    date_item.setBackground(QColor("#FFEBEE"))
                elif days_remaining == 0:  # Due today
                    date_item.setForeground(QColor("#F57C00"))
                    date_item.setBackground(QColor("#FFF3E0"))
                elif days_remaining <= 3:  # Due soon
                    date_item.setForeground(QColor("#F57C00"))
                    
            self.task_table.setItem(row, 2, date_item)
            
            # Status cell with color coding and progress indicators
            status_text = task.status
            if task.status == "In Progress":
                status_text = "🔄 " + status_text
            elif task.status == "Completed":
                status_text = "✅ " + status_text
            else:
                status_text = "⭕ " + status_text
                
            status_item = QTableWidgetItem(status_text)
            status_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
            status_item.setTextAlignment(Qt.AlignCenter)
            
            # Color code based on status
            if task.status == "Completed":
                status_item.setBackground(QColor("#E8F5E9"))
                status_item.setForeground(QColor("#2E7D32"))
            elif task.status == "In Progress":
                status_item.setBackground(QColor("#FFF3E0"))
                status_item.setForeground(QColor("#F57C00"))
            else:  # Not Started
                status_item.setBackground(QColor("#FAFAFA"))
                status_item.setForeground(QColor("#757575"))
                
            self.task_table.setItem(row, 3, status_item)
            
            # Set row height
            self.task_table.setRowHeight(row, 40)
        
        # Resize columns to content
        self.task_table.resizeColumnsToContents()
        # Ensure description column takes remaining space
        header = self.task_table.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        
        # Check for due dates after refreshing tasks
        self.check_due_dates()

    def add_task(self):
        dialog = TaskDialog(self)
        if dialog.exec_():
            task_data = dialog.get_task_data()
            self.task_manager.add_task(**task_data)
            self.refresh_tasks()

    def edit_task(self):
        current_row = self.task_table.currentRow()
        if current_row >= 0 and current_row < len(self.task_ids):
            tasks = self.task_manager.list_tasks()
            task = next((t for t in tasks if t.id == self.task_ids[current_row]), None)
            if task:
                dialog = TaskDialog(self, task)
                if dialog.exec_():
                    task_data = dialog.get_task_data()
                    self.task_manager.update_task(current_row, **task_data)
                    self.refresh_tasks()

    def delete_task(self):
        current_row = self.task_table.currentRow()
        if current_row >= 0 and current_row < len(self.task_ids):
            reply = QMessageBox.question(self, 'Confirm Delete',
                'Are you sure you want to delete this task?',
                QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.task_manager.delete_task(current_row)
                self.refresh_tasks()

    def create_backup(self):
        """Create a backup of the database"""
        if self.task_manager.db.backup_database():
            QMessageBox.information(self, "Backup Created", 
                "Database backup was created successfully in the 'backups' folder.")
        else:
            QMessageBox.warning(self, "Backup Failed", 
                "Failed to create database backup. Check the logs for details.")

    def optimize_database(self):
        """Optimize the database"""
        if self.task_manager.optimize_database():
            QMessageBox.information(self, "Database Optimized", 
                "Database optimization completed successfully.")
        else:
            QMessageBox.warning(self, "Optimization Failed", 
                "Failed to optimize database. Check the logs for details.")

    def show_statistics(self):
        """Show database statistics"""
        stats = self.task_manager.get_database_stats()
        if stats:
            message = f"""
Database Statistics:
------------------
Total Tasks: {stats['total_tasks']}

Tasks by Status:
• Not Started: {stats['tasks_by_status'].get('Not Started', 0)}
• In Progress: {stats['tasks_by_status'].get('In Progress', 0)}
• Completed: {stats['tasks_by_status'].get('Completed', 0)}

Overdue Tasks: {stats['overdue_tasks']}
"""
            QMessageBox.information(self, "Database Statistics", message)
