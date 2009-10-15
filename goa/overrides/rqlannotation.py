"""
:organization: Logilab
:copyright: 2008-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

def set_qdata(getrschema, union, noinvariant):
    pass

class SQLGenAnnotator(object):
    def __init__(self, schema):
        self.schema = schema
        self.nfdomain = frozenset(eschema.type for eschema in schema.entities()
                                  if not eschema.final)
    def annotate(self, rqlst):
        rqlst.has_text_query = False
        rqlst.need_distinct = False


