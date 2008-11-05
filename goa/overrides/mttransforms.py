"""mime type transformation engine for cubicweb, based on mtconverter

:organization: Logilab
:copyright: 2001-2008 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

from logilab import mtconverter

from logilab.mtconverter.engine import TransformEngine
from logilab.mtconverter.transform import Transform
from cubicweb.common.uilib import rest_publish, html_publish, remove_html_tags

HTML_MIMETYPES = ('text/html', 'text/xhtml', 'application/xhtml+xml')
# CubicWeb specific transformations

class rest_to_html(Transform):
    inputs = ('text/rest', 'text/x-rst')
    output = 'text/html'
    def _convert(self, trdata):
        return rest_publish(trdata.appobject, trdata.decode())

class html_to_html(Transform):
    inputs = HTML_MIMETYPES
    output = 'text/html'
    def _convert(self, trdata):
        return html_publish(trdata.appobject, trdata.data)


# Instantiate and configure the transformation engine

mtconverter.UNICODE_POLICY = 'replace'

ENGINE = TransformEngine()
ENGINE.add_transform(rest_to_html())
ENGINE.add_transform(html_to_html())

HAS_PIL_TRANSFORMS = False
HAS_PYGMENTS_TRANSFORMS = False
    
class html_to_text(Transform):
    inputs = HTML_MIMETYPES
    output = 'text/plain'
    def _convert(self, trdata):
        return remove_html_tags(trdata.data)
ENGINE.add_transform(html_to_text())
