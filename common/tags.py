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
