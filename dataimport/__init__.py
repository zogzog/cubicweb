# copyright 2003-2015 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""Package containing various utilities to import data into cubicweb."""


def callfunc_every(func, number, iterable):
    """yield items of `iterable` one by one and call function `func`
    every `number` iterations. Always call function `func` at the end.
    """
    for idx, item in enumerate(iterable):
        yield item
        if not idx % number:
            func()
    func()

# import for backward compat
from cubicweb.dataimport.stores import *
from cubicweb.dataimport.pgstore import *
from cubicweb.dataimport.csv import *
from cubicweb.dataimport.deprecated import *
