# -*- coding: utf-8 -*-
# copyright 2003-2010 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""

"""
import os
os.environ["DJANGO_SETTINGS_MODULE"] = 'data.settings'

from django import template


def encode_output(self, output):
    # Check type so that we don't run str() on a Unicode object
    if not isinstance(output, basestring):
        return unicode(output)
    return output

template.VariableNode.encode_output = encode_output

from cubicweb.view import StartupView

INDEX_TEMPLATE = template.Template(u'''
 <h1>hellô {{ user.login }}</h1>
''')

class MyIndex(StartupView):
    id = 'index'

    def call(self):
        ctx = template.Context({'user': self.req.user})
        return INDEX_TEMPLATE.render(ctx)
