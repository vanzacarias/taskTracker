from setuptools import setup, find_packages

setup(
    name="tasktracker",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        'PyQt5>=5.15.0',
    ],
    python_requires='>=3.6',
    entry_points={
        'console_scripts': [
            'tasktracker=main:main',
        ],
    },
    author="Your Name",
    description="A PyQt5-based task tracking application with SQLite storage",
)