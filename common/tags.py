from logilab.mtconverter import html_escape
from cubicweb.common.uilib import simple_sgml_tag
class tag(object):
    def __init__(self, name):
        self.name = name
        
    def __call__(self, __content=None, **attrs):
        return simple_sgml_tag(self.name, __content, **attrs)

input = tag('input')
textarea = tag('textarea')
a = tag('a')
span = tag('span')
img = tag('img')
label = tag('label')
option = tag('option')

def select(name, multiple=False, options=[]):
    if multiple:
        html = [u'<select name="%s" multiple="multiple">' % name]
    else:
        html = [u'<select name="%s">' % name]
    html += options
    html.append(u'</select>')
    return u'\n'.join(html)

