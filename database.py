import sqlite3
from datetime import datetime, timedelta
from contextlib import contextmanager
import os
import shutil
import threading
import logging
import glob
import time

# Configure logging
logging.basicConfig(
    filename='database.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class DatabaseManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, db_file="tasks.db"):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    instance = super(DatabaseManager, cls).__new__(cls)
                    # Initialize attributes but don't connect to DB yet
                    instance.db_file = db_file
                    instance.max_backups = 5
                    cls._instance = instance
        return cls._instance

    def __init__(self, db_file="tasks.db", max_backups=5):
        # Only initialize if this is the first time
        if not hasattr(self, '_initialized'):
            self.max_backups = max_backups
            self._cleanup_old_backups()
            self.init_database()
            self._initialized = True

    def _cleanup_old_backups(self):
        """Keep only the most recent backups based on max_backups setting"""
        backup_dir = "backups"
        if not os.path.exists(backup_dir):
            return
            
        # Get list of backup files sorted by modification time
        backup_files = glob.glob(os.path.join(backup_dir, "tasks_backup_*.db"))
        backup_files.sort(key=os.path.getmtime, reverse=True)
        
        # Remove older backups exceeding max_backups
        for old_backup in backup_files[self.max_backups:]:
            try:
                os.remove(old_backup)
                logging.info(f"Removed old backup: {old_backup}")
            except Exception as e:
                logging.error(f"Failed to remove old backup {old_backup}: {str(e)}")

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = DatabaseManager()
        return cls._instance

    @contextmanager
    def get_connection(self):
        conn = None
        try:
            conn = sqlite3.connect(
                self.db_file, 
                detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
                timeout=20
            )
            conn.row_factory = sqlite3.Row
            yield conn
        except sqlite3.Error as e:
            logging.error(f"Database connection error: {str(e)}")
            raise
        finally:
            if conn:
                try:
                    conn.close()
                except sqlite3.Error as e:
                    logging.error(f"Error closing connection: {str(e)}")

    def execute_with_retry(self, operation, max_retries=3):
        """Execute database operation with retry logic"""
        for attempt in range(max_retries):
            try:
                with self.get_connection() as conn:
                    return operation(conn)
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < max_retries - 1:
                    time.sleep(0.1 * (attempt + 1))  # Exponential backoff
                    continue
                raise
            except Exception as e:
                logging.error(f"Database operation failed: {str(e)}")
                raise

    def init_database(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.executescript('''
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT,
                    due_date DATE,
                    status TEXT DEFAULT 'Not Started' CHECK(status IN ('Not Started', 'In Progress', 'Completed')),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE INDEX IF NOT EXISTS idx_tasks_due_date ON tasks(due_date);
                CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
                CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks(created_at);
                -- Add composite index for more efficient sorting and filtering
                CREATE INDEX IF NOT EXISTS idx_tasks_status_due_date ON tasks(status, due_date);
                
                -- Add index for title search
                CREATE INDEX IF NOT EXISTS idx_tasks_title ON tasks(title);
                
                CREATE TRIGGER IF NOT EXISTS update_task_timestamp 
                AFTER UPDATE ON tasks
                BEGIN
                    UPDATE tasks SET updated_at = CURRENT_TIMESTAMP 
                    WHERE id = NEW.id;
                END;
                
                -- Add efficient task loading view
                CREATE VIEW IF NOT EXISTS v_active_tasks AS
                SELECT * FROM tasks 
                WHERE status != 'Completed'
                ORDER BY 
                    CASE 
                        WHEN due_date < date('now') THEN 1
                        WHEN due_date = date('now') THEN 2
                        ELSE 3
                    END,
                    due_date ASC;
            ''')
            conn.commit()

    def add_task(self, title, description="", due_date=None, status="Not Started"):
        if not title:
            raise ValueError("Title cannot be empty")
            
        def _add(conn):
            cursor = conn.cursor()
            try:
                cursor.execute('''
                    INSERT INTO tasks (title, description, due_date, status)
                    VALUES (?, ?, ?, ?)
                ''', (title, description, due_date, status))
                conn.commit()
                return cursor.lastrowid
            except sqlite3.IntegrityError as e:
                conn.rollback()
                raise ValueError(f"Invalid task data: {str(e)}")
                
        return self.execute_with_retry(_add)

    def update_task(self, task_id, title, description="", due_date=None, status=None):
        if not title:
            raise ValueError("Title cannot be empty")
            
        def _update(conn):
            cursor = conn.cursor()
            try:
                if status:
                    cursor.execute('''
                        UPDATE tasks 
                        SET title=?, description=?, due_date=?, status=?, updated_at=CURRENT_TIMESTAMP
                        WHERE id=?
                    ''', (title, description, due_date, status, task_id))
                else:
                    cursor.execute('''
                        UPDATE tasks 
                        SET title=?, description=?, due_date=?, updated_at=CURRENT_TIMESTAMP
                        WHERE id=?
                    ''', (title, description, due_date, task_id))
                conn.commit()
                return cursor.rowcount > 0
            except sqlite3.IntegrityError as e:
                conn.rollback()
                raise ValueError(f"Invalid task data: {str(e)}")
                
        return self.execute_with_retry(_update)

    def delete_task(self, task_id):
        def _delete(conn):
            cursor = conn.cursor()
            cursor.execute('DELETE FROM tasks WHERE id=?', (task_id,))
            conn.commit()
            return cursor.rowcount > 0
            
        return self.execute_with_retry(_delete)

    def get_all_tasks(self, order_by='due_date', desc=False):
        """Get all tasks with optimized ordering"""
        valid_columns = {'created_at', 'due_date', 'title', 'status'}
        if order_by not in valid_columns:
            order_by = 'due_date'
            
        def _get_all(conn):
            cursor = conn.cursor()
            # Use optimized query based on status and due date
            cursor.execute('''
                SELECT * FROM tasks
                ORDER BY 
                    CASE 
                        WHEN status = 'Completed' THEN 2
                        ELSE 1
                    END,
                    CASE 
                        WHEN due_date IS NULL THEN 1
                        ELSE 0
                    END,
                    CASE 
                        WHEN ? = 'due_date' THEN due_date
                        WHEN ? = 'created_at' THEN created_at
                        WHEN ? = 'title' THEN title
                        ELSE status
                    END ''' + ('DESC' if desc else 'ASC'),
                (order_by, order_by, order_by))
            return cursor.fetchall()
            
        return self.execute_with_retry(_get_all)

    def get_task(self, task_id):
        def _get(conn):
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM tasks WHERE id=?', (task_id,))
            return cursor.fetchone()
            
        return self.execute_with_retry(_get)
            
    def get_tasks_by_status(self, status):
        def _get_by_status(conn):
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM tasks WHERE status=? ORDER BY due_date ASC', (status,))
            return cursor.fetchall()
            
        return self.execute_with_retry(_get_by_status)
            
    def get_upcoming_tasks(self, days=7):
        def _get_upcoming(conn):
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM tasks 
                WHERE due_date IS NOT NULL 
                AND due_date <= date('now', '+' || ? || ' days')
                AND status != 'Completed'
                ORDER BY due_date ASC
            ''', (days,))
            return cursor.fetchall()
            
        return self.execute_with_retry(_get_upcoming)
            
    def get_overdue_tasks(self):
        def _get_overdue(conn):
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM tasks 
                WHERE due_date < date('now') 
                AND status != 'Completed'
                ORDER BY due_date ASC
            ''')
            return cursor.fetchall()
            
        return self.execute_with_retry(_get_overdue)

    def cleanup_database(self):
        """Optional method to optimize database performance"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('VACUUM')

    def backup_database(self):
        """Create a backup of the database file"""
        if not os.path.exists(self.db_file):
            return False
            
        backup_dir = "backups"
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = os.path.join(backup_dir, f"tasks_backup_{timestamp}.db")
        
        try:
            shutil.copy2(self.db_file, backup_file)
            logging.info(f"Database backed up to {backup_file}")
            return True
        except Exception as e:
            logging.error(f"Backup failed: {str(e)}")
            return False

    def restore_from_backup(self, backup_file):
        """Restore database from a backup file"""
        if not os.path.exists(backup_file):
            raise FileNotFoundError("Backup file not found")
            
        try:
            # Close all connections first
            with self.get_connection() as conn:
                conn.close()
            
            # Restore the backup
            shutil.copy2(backup_file, self.db_file)
            logging.info(f"Database restored from {backup_file}")
            return True
        except Exception as e:
            logging.error(f"Restore failed: {str(e)}")
            return False

    def optimize_database(self):
        def _optimize(conn):
            cursor = conn.cursor()
            cursor.execute('PRAGMA optimize')
            cursor.execute('PRAGMA vacuum')
            cursor.execute('PRAGMA analysis_limit=1000')
            cursor.execute('PRAGMA analyze')
            conn.commit()
            logging.info("Database optimized")
            return True
            
        return self.execute_with_retry(_optimize)

    def get_database_stats(self):
        def _get_stats(conn):
            cursor = conn.cursor()
            stats = {}
            
            cursor.execute('SELECT COUNT(*) from tasks')
            stats['total_tasks'] = cursor.fetchone()[0]
            
            cursor.execute('''
                SELECT status, COUNT(*) 
                FROM tasks 
                GROUP BY status
            ''')
            stats['tasks_by_status'] = dict(cursor.fetchall())
            
            cursor.execute('''
                SELECT COUNT(*) 
                FROM tasks 
                WHERE due_date < date('now') 
                AND status != 'Completed'
            ''')
            stats['overdue_tasks'] = cursor.fetchone()[0]
            
            return stats
            
        return self.execute_with_retry(_get_stats)

    def get_active_tasks(self):
        """Get non-completed tasks in optimized order"""
        def _get_active(conn):
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM v_active_tasks')
            return cursor.fetchall()
            
        return self.execute_with_retry(_get_active)