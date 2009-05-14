"""
:organization: Logilab
:copyright: 2008-2009 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

def set_qdata(getrschema, union, noinvariant):
    pass

class SQLGenAnnotator(object):
    def __init__(self, schema):
        self.schema = schema
        self.nfdomain = frozenset(eschema.type for eschema in schema.entities()
                                  if not eschema.is_final())
    def annotate(self, rqlst):
        rqlst.has_text_query = False
        rqlst.need_distinct = False


