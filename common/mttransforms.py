"""mime type transformation engine for cubicweb, based on mtconverter

:organization: Logilab
:copyright: 2001-2008 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

from logilab import mtconverter

from logilab.mtconverter.engine import TransformEngine
from logilab.mtconverter.transform import Transform
from logilab.mtconverter import (register_base_transforms,
                                 register_pil_transforms, 
                                 register_pygments_transforms)

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

try:
    from cubicweb.common.tal import compile_template
except ImportError:
    HAS_TAL = False
else:
    HAS_TAL = True
    
    class ept_to_html(Transform):
        inputs = ('text/cubicweb-page-template',)
        output = 'text/html'
        output_encoding = 'utf-8'
        def _convert(self, trdata):
            value = trdata.encode(self.output_encoding)
            return trdata.appobject.tal_render(compile_template(value), {})

    ENGINE.add_transform(ept_to_html())

if register_pil_transforms(ENGINE, verb=False):
    HAS_PIL_TRANSFORMS = True
else:
    HAS_PIL_TRANSFORMS = False
    
try:
    from logilab.mtconverter.transforms import pygmentstransforms
    for mt in ('text/plain',) + HTML_MIMETYPES:
        try:
            pygmentstransforms.mimetypes.remove(mt)
        except ValueError:
            continue
    register_pygments_transforms(ENGINE, verb=False)

    def patch_convert(cls):
        def _convert(self, trdata, origconvert=cls._convert):
            try:
                trdata.appobject.req.add_css('pygments.css')
            except AttributeError: # session has no add_css, only http request
                pass
            return origconvert(self, trdata)
        cls._convert = _convert
    patch_convert(pygmentstransforms.PygmentsHTMLTransform)
    
    HAS_PYGMENTS_TRANSFORMS = True
except ImportError:
    HAS_PYGMENTS_TRANSFORMS = False
    
register_base_transforms(ENGINE, verb=False)
