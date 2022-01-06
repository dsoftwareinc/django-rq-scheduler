#!/usr/bin/env python

import os
from distutils.core import setup

from setuptools import find_packages


def long_desc(root_path):
    FILES = ['README.md']
    for filename in FILES:
        filepath = os.path.realpath(os.path.join(root_path, filename))
        if os.path.isfile(filepath):
            with open(filepath, mode='r') as f:
                yield f.read()


PATH_OF_RUNNING_SCRIPT = os.path.abspath(os.path.dirname(__file__))
long_description = "\n\n".join(long_desc(PATH_OF_RUNNING_SCRIPT))

tests_require = [
    'factory_boy>=2.11.1',
]

setup(
    name='django-rqscheduler4',
    version='2022.1',
    description='A database backed job scheduler for Django RQ with Django',
    long_description=long_description,
    long_description_content_type='text/markdown',
    packages=find_packages(),
    include_package_data=True,
    author='Daniel Moran',
    author_email='daniel.maruani@gmail.com',
    license='MIT',
    url='https://github.com/cunla/django-rqscheduler',
    zip_safe=True,
    install_requires=[
        'django>=3.0.0',
        'django-model-utils>=4.2.0',
        'django-rq>=2.5.1',
        'rq-scheduler>=0.11.0',
        'pytz>=2021.3',
        'croniter>=1.1.0',
    ],
    tests_require=tests_require,
    test_suite='scheduler.tests',
    extras_require={
        'test': tests_require,
    },
    classifiers=[
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.6',
        'Framework :: Django',
    ],
)
