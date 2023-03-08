from setuptools import setup, find_packages

setup(
    name="procal",
    description="A simple Qt-based programming calculator",
    author="fellerts",
    license="GPLv3",
    py_modules=["procal"],
    install_requires=[
        'PyQt6==6.2.3',
        'PyQt6-Qt6==6.2.4',
        'PyQt6-sip==13.2.1',
        'pyqtdarktheme==2.1.0',
    ],
    entry_points={
        "console_scripts": [
            "procal = procal:main",
        ],
    },
)

