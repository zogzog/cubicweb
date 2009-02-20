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

def select(name, id=None, multiple=False, options=[]):
    attrs = {}
    if multiple:
        attrs['multiple'] = 'multiple'
    if id:
        attrs['id'] = id
    html = [u'<select name="%s" %s>' % (name,
                                        ' '.join('%s="%s"' % kv for kv in attrs.items()))]
    html += options
    html.append(u'</select>')
    return u'\n'.join(html)

