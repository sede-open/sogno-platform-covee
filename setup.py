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
    "alive-progress",
    "osqp",
    "cvxpy",
    "humanfriendly",
    "pyrlu"
],

setup(
    name="covee",
    version="0.1",
    author="Edoardo De Din",
    author_email="acs-software@eonerc.rwth-aachen.de",
    packages=['covee'],
    install_requires = requiredPackages
)
