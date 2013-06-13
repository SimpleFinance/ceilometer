from setuptools import setup, find_packages

meta = dict(
    name             = "ceilometer",
    version          = "0.0.1",
    py_modules       = ["ceilometer"],
    install_requires = ["boto"],
    scripts          = ["scripts/ceilometer"],
)

setup(**meta)
