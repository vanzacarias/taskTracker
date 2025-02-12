from datetime import datetime
from database import DatabaseManager
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtCore import QTimer
import sqlite3
import logging
from functools import lru_cache
import time

class Task:
    def __init__(self, id=None, title="", description="", due_date=None, status="Not Started", created_at=None, updated_at=None):
        self.id = id
        self.title = title
        self.description = description
        # Convert string date to datetime.date if needed
        if isinstance(due_date, str) and due_date:
            try:
                self.due_date = datetime.strptime(due_date, "%Y-%m-%d").date()
            except (ValueError, TypeError):
                self.due_date = None
        else:
            self.due_date = due_date
        self.status = status
        self.created_at = created_at
        self.updated_at = updated_at

    @classmethod
    def from_db_row(cls, row):
        """Create a Task instance from a database row"""
        if row is None:
            return None
        # Handle SQLite row object
        if isinstance(row, sqlite3.Row):
            return cls(
                id=row['id'],
                title=row['title'],
                description=row['description'],
                due_date=row['due_date'],
                status=row['status'],
                created_at=row['created_at'],
                updated_at=row['updated_at']
            )
        # Handle regular tuple
        return cls(
            id=row[0],
            title=row[1],
            description=row[2],
            due_date=row[3],
            status=row[4],
            created_at=row[5],
            updated_at=row[6]
        )

    def __str__(self):
        status_symbol = "✓" if self.status == "Completed" else " "
        desc = f" - {self.description}" if self.description else ""
        date = f" (Due: {self.due_date})" if self.due_date else ""
        return f"[{status_symbol}] {self.title}{desc}{date}"

    def days_until_due(self):
        if not self.due_date:
            return None
        return (self.due_date - datetime.now().date()).days

    def to_dict(self):
        """Convert task to dictionary for database operations"""
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'due_date': self.due_date,
            'status': self.status,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }

class TaskManager:
    def __init__(self):
        self.db = DatabaseManager()
        self._tasks = []
        self._active_tasks = []
        self._last_refresh = 0
        self._cache_lifetime = 5  # Cache lifetime in seconds
        
        # Initialize tasks immediately
        self.refresh_tasks()
        
        # Set up auto-backup timer after tasks are loaded
        self.backup_timer = QTimer()
        self.backup_timer.timeout.connect(self._auto_backup)
        self.backup_timer.start(30 * 60 * 1000)

    @lru_cache(maxsize=32)
    def _get_task_by_id(self, task_id):
        """Get a task by ID with caching"""
        return next((task for task in self._tasks if task.id == task_id), None)

    def _auto_backup(self):
        """Automatically backup the database"""
        try:
            if self.db.backup_database():
                logging.info("Automatic backup completed successfully")
            else:
                logging.warning("Automatic backup failed")
        except Exception as e:
            logging.error(f"Error during automatic backup: {str(e)}")

    def get_database_stats(self):
        """Get statistics about tasks"""
        try:
            return self.db.get_database_stats()
        except Exception as e:
            logging.error(f"Error getting database stats: {str(e)}")
            return None

    def optimize_database(self):
        """Optimize database performance"""
        try:
            return self.db.optimize_database()
        except Exception as e:
            logging.error(f"Error optimizing database: {str(e)}")
            return False

    def refresh_tasks(self, order_by='due_date', desc=False, force=False):
        """Reload tasks from database with caching"""
        current_time = time.time()
        
        # Return cached results if within cache lifetime
        if not force and (current_time - self._last_refresh) < self._cache_lifetime:
            return self._tasks
            
        try:
            # Load active tasks first for immediate display
            db_active_tasks = self.db.get_active_tasks()
            self._active_tasks = [Task.from_db_row(row) for row in db_active_tasks]
            
            # Load all tasks
            db_tasks = self.db.get_all_tasks(order_by=order_by, desc=desc)
            self._tasks = [Task.from_db_row(row) for row in db_tasks]
            
            # Update cache timestamp
            self._last_refresh = current_time
            
            # Clear the task ID cache when refreshing
            self._get_task_by_id.cache_clear()
            
            return self._tasks
        except sqlite3.Error as e:
            logging.error(f"Database error during refresh: {str(e)}")
            QMessageBox.critical(None, "Database Error", 
                f"Failed to refresh tasks: {str(e)}")
            return []
        except Exception as e:
            logging.error(f"Unexpected error during refresh: {str(e)}")
            QMessageBox.critical(None, "Error", 
                "An unexpected error occurred while refreshing tasks")
            return []

    def add_task(self, title, description="", due_date=None, status="Not Started"):
        try:
            task_id = self.db.add_task(title, description, due_date, status)
            # Force refresh after adding
            self.refresh_tasks(force=True)
            return self._get_task_by_id(task_id)
        except ValueError as e:
            QMessageBox.warning(None, "Invalid Input", str(e))
            return None
        except Exception as e:
            QMessageBox.critical(None, "Database Error", 
                f"Failed to add task: {str(e)}")
            return None

    def update_task(self, index, title, description="", due_date=None, status=None):
        if 0 <= index < len(self._tasks):
            task = self._tasks[index]
            try:
                if self.db.update_task(task.id, title, description, due_date, status):
                    # Force refresh after update
                    self.refresh_tasks(force=True)
                    return self._get_task_by_id(task.id)
            except ValueError as e:
                QMessageBox.warning(None, "Invalid Input", str(e))
            except Exception as e:
                QMessageBox.critical(None, "Database Error", 
                    f"Failed to update task: {str(e)}")
        return None

    def delete_task(self, index):
        if 0 <= index < len(self._tasks):
            task = self._tasks[index]
            try:
                if self.db.delete_task(task.id):
                    deleted_task = task
                    # Force refresh after delete
                    self.refresh_tasks(force=True)
                    return deleted_task
            except Exception as e:
                QMessageBox.critical(None, "Database Error", 
                    f"Failed to delete task: {str(e)}")
        return None

    def list_tasks(self, active_only=False, force_refresh=False):
        """Get tasks with option to show only active ones"""
        if force_refresh:
            self.refresh_tasks(force=True)
        return self._active_tasks if active_only else self._tasks

    def get_upcoming_tasks(self, days=7):
        """Get tasks due within the specified number of days"""
        try:
            db_tasks = self.db.get_upcoming_tasks(days)
            return [Task.from_db_row(row) for row in db_tasks]
        except Exception as e:
            QMessageBox.critical(None, "Database Error", 
                f"Failed to get upcoming tasks: {str(e)}")
            return []

    def get_overdue_tasks(self):
        """Get all overdue tasks"""
        try:
            db_tasks = self.db.get_overdue_tasks()
            return [Task.from_db_row(row) for row in db_tasks]
        except Exception as e:
            QMessageBox.critical(None, "Database Error", 
                f"Failed to get overdue tasks: {str(e)}")
            return []

    def get_tasks_by_status(self, status):
        """Get all tasks with the specified status"""
        try:
            db_tasks = self.db.get_tasks_by_status(status)
            return [Task.from_db_row(row) for row in db_tasks]
        except Exception as e:
            QMessageBox.critical(None, "Database Error", 
                f"Failed to get tasks by status: {str(e)}")
            return []
