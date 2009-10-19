"""Views, forms, actions... for the CubicWeb web client

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

import os
import sys
import tempfile
from rql import nodes


def need_table_view(rset, schema):
    """return True if we think that a table view is more appropriate than a
    list or primary view to display the given result set
    """
    rqlst = rset.syntax_tree()
    if len(rqlst.children) > 1:
        # UNION query, use a table
        return True
    selected = rqlst.children[0].selection
    try:
        mainvar = selected[0]
    except AttributeError:
        # not a variable ref, using table view is probably a good option
        return True
    if not (isinstance(mainvar, nodes.VariableRef) or
            (isinstance(mainvar, nodes.Constant) and mainvar.uid)):
        return True
    for i, etype in enumerate(rset.description[0][1:]):
        # etype may be None on outer join
        if etype is None:
            return True
        # check the selected index node is a VariableRef (else we
        # won't detect aggregate function
        if not isinstance(selected[i+1], nodes.VariableRef):
            return True
        # if this is not a final entity
        if not schema.eschema(etype).final:
            return True
        # if this is a final entity not linked to the main variable
        var = selected[i+1].variable
        for vref in var.references():
            rel = vref.relation()
            if rel is None:
                continue
            if mainvar.is_equivalent(rel.children[0]):
                break
        else:
            return True
    return False

# FIXME: VID_BY_MIMETYPE is unfortunately a bit too naive since
#        some browsers (e.g. FF2) send a bunch of mimetypes in
#        the Accept header, for instance:
#          text/xml,application/xml,application/xhtml+xml,text/html;q=0.9,
#          text/plain;q=0.8,image/png,*/*;q=0.5
VID_BY_MIMETYPE = {
    #'text/xml': 'xml',
    # XXX rss, owl...
}
def vid_from_rset(req, rset, schema):
    """given a result set, return a view id"""
    if rset is None:
        return 'index'
    for mimetype in req.parse_accept_header('Accept'):
        if mimetype in VID_BY_MIMETYPE:
            return VID_BY_MIMETYPE[mimetype]
    nb_rows = len(rset)
    # empty resultset
    if nb_rows == 0 :
        return 'noresult'
    # entity result set
    if not schema.eschema(rset.description[0][0]).final:
        if need_table_view(rset, schema):
            return 'table'
        if nb_rows == 1:
            if req.search_state[0] == 'normal':
                return 'primary'
            return 'outofcontext-search'
        if len(rset.column_types(0)) == 1:
            return 'adaptedlist'
        return 'list'
    return 'table'


def linksearch_select_url(req, rset):
    """when searching an entity to create a relation, return an url to select
    entities in the given rset
    """
    req.add_js( ('cubicweb.ajax.js', 'cubicweb.edition.js') )
    target, eid, r_type, searchedtype = req.search_state[1]
    if target == 'subject':
        id_fmt = '%s:%s:%%s' % (eid, r_type)
    else:
        id_fmt = '%%s:%s:%s' % (r_type, eid)
    triplets = '-'.join(id_fmt % row[0] for row in rset.rows)
    return "javascript: selectForAssociation('%s', '%s');" % (triplets, eid)


class TmpFileViewMixin(object):
    binary = True
    content_type = 'application/octet-stream'
    cache_max_age = 60*60*2 # stay in http cache for 2 hours by default

    def call(self):
        self.cell_call()

    def cell_call(self, row=0, col=0):
        self.cw_row, self.cw_col = row, col # in case one needs it
        fd, tmpfile = tempfile.mkstemp('.png')
        os.close(fd)
        self._generate(tmpfile)
        self.w(open(tmpfile, 'rb').read())
        os.unlink(tmpfile)
