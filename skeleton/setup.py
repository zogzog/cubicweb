#!/usr/bin/env python
# pylint: disable-msg=W0404,W0622,W0704,W0613,W0152
# Copyright (c) 2003-2009 LOGILAB S.A. (Paris, FRANCE).
# http://www.logilab.fr/ -- mailto:contact@logilab.fr
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; either version 2 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
""" Generic Setup script, takes package info from __pkginfo__.py file """

from distutils.core import setup

# import required features
from __pkginfo__ import distname, version, license, short_desc, long_desc, \
     web, author, author_email
# import optional features
try:
    from __pkginfo__ import data_files
except ImportError:
    data_files = None
try:
    from __pkginfo__ import include_dirs
except ImportError:
    include_dirs = []

def install(**kwargs):
    """setup entry point"""
    #kwargs['distname'] = modname
    return setup(name=distname,
                 version=version,
                 license=license,
                 description=short_desc,
                 long_description=long_desc,
                 author=author,
                 author_email=author_email,
                 url=web,
                 data_files=data_files,
                 **kwargs)

if __name__ == '__main__' :
    install()
