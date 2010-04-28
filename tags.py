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
"""helper classes to generate simple (X)HTML tags

"""
__docformat__ = "restructuredtext en"

from cubicweb.uilib import simple_sgml_tag, sgml_attributes

class tag(object):
    def __init__(self, name, escapecontent=True):
        self.name = name
        self.escapecontent = escapecontent

    def __call__(self, __content=None, **attrs):
        attrs.setdefault('escapecontent', self.escapecontent)
        return simple_sgml_tag(self.name, __content, **attrs)

button = tag('button')
input = tag('input')
textarea = tag('textarea')
a = tag('a')
span = tag('span')
div = tag('div', False)
img = tag('img')
label = tag('label')
option = tag('option')
h1 = tag('h1')
h2 = tag('h2')
h3 = tag('h3')
h4 = tag('h4')
h5 = tag('h5')
tr = tag('tr')
th = tag('th')
td = tag('td')

def select(name, id=None, multiple=False, options=[], **attrs):
    if multiple:
        attrs['multiple'] = 'multiple'
    if id:
        attrs['id'] = id
    attrs['name'] = name
    html = [u'<select %s>' % sgml_attributes(attrs)]
    html += options
    html.append(u'</select>')
    return u'\n'.join(html)

