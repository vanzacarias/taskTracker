import sys
from PyQt5.QtWidgets import QApplication, QMessageBox, QSplashScreen
from PyQt5.QtCore import Qt
from task_manager import TaskManager
from gui.main_window import MainWindow
from database import DatabaseManager

def initialize_database():
    try:
        db = DatabaseManager()
        # Test database connection and task loading
        try:
            tasks = db.get_all_tasks()
            return True
        except Exception as e:
            QMessageBox.critical(None, "Database Error",
                f"Failed to load tasks: {str(e)}\nThe application will now exit.")
            return False
    except Exception as e:
        QMessageBox.critical(None, "Database Error",
            f"Failed to initialize database: {str(e)}\nThe application will now exit.")
        return False

def print_menu():
    print("\n=== Task Tracker Menu ===")
    print("1. Add Task")
    print("2. List Tasks")
    print("3. Mark Task as Complete")
    print("4. Exit")

def main():
    app = QApplication(sys.argv)
    
    # Initialize database before creating the main window
    if not initialize_database():
        sys.exit(1)
    
    # Create and show main window
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
