#!/usr/bin/env python
# pylint: disable=W0142,W0403,W0404,W0613,W0622,W0622,W0704,R0904,C0103,E0611
#
# copyright 2003-2011 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
# contact http://www.logilab.fr/ -- mailto:contact@logilab.fr
#
# This file is part of CubicWeb.
#
# CubicWeb is free software: you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation, either version 2.1 of the License, or (at your option)
# any later version.
#
# CubicWeb is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License along
# with CubicWeb.  If not, see <http://www.gnu.org/licenses/>.
"""Generic Setup script, takes package info from __pkginfo__.py file
"""

import io
from os.path import dirname, join

from setuptools import setup, find_packages


here = dirname(__file__)

# import required features
pkginfo = join(here, 'cubicweb', '__pkginfo__.py')
__pkginfo__ = {}
with open(pkginfo) as f:
    exec(f.read(), __pkginfo__)
modname = __pkginfo__['modname']
version = __pkginfo__['version']
license = __pkginfo__['license']
description = __pkginfo__['description']
web = __pkginfo__['web']
author = __pkginfo__['author']
author_email = __pkginfo__['author_email']

with io.open('README', encoding='utf-8') as f:
    long_description = f.read()

# import optional features
distname = __pkginfo__['distname']
package_data = __pkginfo__['package_data']


setup(
    name=distname,
    version=version,
    license=license,
    url=web,
    description=description,
    long_description=long_description,
    author=author,
    author_email=author_email,
    packages=find_packages(),
    package_data=package_data,
    include_package_data=True,
    install_requires=[
        'six >= 1.4.0',
        'logilab-common >= 1.4.0',
        'logilab-mtconverter >= 0.8.0',
        'rql >= 0.34.0',
        'yams >= 0.45.0',
        'lxml',
        'logilab-database >= 1.15.0',
        'passlib',
        'pytz',
        'Markdown',
        'unittest2 >= 0.7.0',
    ],
    entry_points={
        'console_scripts': [
            'cubicweb-ctl = cubicweb.cwctl:run',
        ],
        'paste.app_factory': [
            'pyramid_main=cubicweb.pyramid:pyramid_app',
        ],
    },
    extras_require={
        'captcha': [
            'Pillow',
        ],
        'crypto': [
            'pycrypto',
        ],
        'etwist': [
            'Twisted < 16.0.0',
        ],
        'ext': [
            'docutils >= 0.6',
        ],
        'ical': [
            'vobject >= 0.6.0',
        ],
        'pyramid': [
            'pyramid >= 1.5.0',
            'waitress >= 0.8.9',
            'wsgicors >= 0.3',
            'pyramid_multiauth',
            'repoze.lru',
        ],
        'rdf': [
            'rdflib',
        ],
        'sparql': [
            'fyzz >= 0.1.0',
        ],
        'zmq': [
            'pyzmq',
        ],
    },
    zip_safe=False,
)
