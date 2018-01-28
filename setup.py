#!/usr/bin/env python
# -* encoding: utf-8 *-
import os
from setuptools import setup

HERE = os.path.dirname(__file__)

try:
    long_description = open(os.path.join(HERE, 'README.rst')).read()
except IOError:
    long_description = None


setup(
    name="django-dbconn-retry",
    version="0.1.4",
    packages=[
        'django_dbconn_retry',
        'django_dbconn_retry.tests',
    ],
    package_dir={
        '': '.',
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "Programming Language :: Python :: 3 :: Only",
        "License :: OSI Approved :: BSD License",
        "Operating System :: POSIX",
    ],
    url="https://github.com/jdelic/django-dbconn-retry/",
    author="Jonas Maurus (@jdelic)",
    author_email="jonas-dbconn-retry@gopythongo.com",
    maintainer="GoPythonGo.com",
    maintainer_email="info@gopythongo.com",
    description="Patch Django to retry a database connection first before failing.",
    long_description=long_description,

    install_requires=[
    ],
)
