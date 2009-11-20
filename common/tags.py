"""helper classes to generate simple (X)HTML tags

:organization: Logilab
:copyright: 2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

from cubicweb.common.uilib import simple_sgml_tag, sgml_attributes

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

