from setuptools import setup, find_packages

requiredPackages = [#should only contain third party pakages
    "coloredlogs",
    "numpy",
    "scipy",
    "PYPOWER",
    "matplotlib",
    "ipython",
    "requests",
    "paho-mqtt",
    "cvxopt",
    "python-dotenv",
    "osqp",
    "cvxpy"
],

setup(
    name="covee control",
    version="0.1",
    author="Edoardo De Din (RWTH Aachen University)",
    author_email="ededin@eonerc.rwth-aachen.de",
    install_requires = requiredPackages
)
