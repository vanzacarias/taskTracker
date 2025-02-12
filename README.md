# Task Tracker

A PyQt5-based task tracking application with SQLite storage.

## Features
- Add, edit, and delete tasks
- Set due dates and track task status
- Automatic warning system for upcoming and overdue tasks
- Database backup and optimization
- Task statistics

## Project Structure
```
taskTracker/
├── gui/               # GUI components
│   ├── __init__.py
│   ├── main_window.py
│   └── task_dialog.py
├── database.py        # Database management
├── task_manager.py    # Task business logic
├── main.py           # Application entry point
├── setup.py          # Package configuration
└── requirements.txt   # Project dependencies
```

## Setup
1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the application:
```bash
python main.py
```

## Development
To set up the development environment:
1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Install in development mode:
```bash
pip install -e .
```