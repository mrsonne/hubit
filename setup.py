# ... setup.py develop comes with an --uninstall option for when you're done hacking around (python setup.py develop -u)

#!/usr/bin/env python
# -*- encoding: utf-8 -*-
from __future__ import absolute_import
from __future__ import print_function

from glob import glob
from os.path import basename
from os.path import splitext

from setuptools import find_packages
from setuptools import setup

# yaml, graphviz

setup(
    name='hubit',
#    version=version,
    # packages=find_packages('src'),
    package_dir={'': '.'},
    py_modules=[splitext(basename(path))[0] for path in glob('hubit/*.py')],
    install_requires=[],
) 