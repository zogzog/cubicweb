"""SPARQL integration

:organization: Logilab
:copyright: 2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

import rql
from yams import xy

from lxml import etree
from lxml.builder import E

from cubicweb.view import StartupView, AnyRsetView
from cubicweb.web import form, formfields, formwidgets as fwdgs
from cubicweb.web.views import forms, urlrewrite
from cubicweb.spa2rql import Sparql2rqlTranslator


class SparqlForm(forms.FieldsForm):
    id = 'sparql'
    sparql = formfields.StringField(help=_('type here a sparql qyery'))
    vid = formfields.StringField(initial='sparql', widget=fwdgs.HiddenInput)
    form_buttons = [fwdgs.SubmitButton()]
    @property
    def action(self):
        return self.req.url()


class SparqlFormView(form.FormViewMixIn, StartupView):
    id = 'sparql'
    def call(self):
        form = self.vreg.select('forms', 'sparql', self.req)
        self.w(form.form_render())
        sparql = self.req.form.get('sparql')
        if sparql:
            try:
                qi = Sparql2rqlTranslator(self.schema).translate(sparql)
                rset = self.req.execute(qi.finalize())
            except rql.TypeResolverException, ex:
                self.w(self.req._('can not resolve entity types:') + u' ' + unicode('ex'))
            except UnsupportedQuery:
                self.w(self.req._('we are not yet ready to handle this query'))
            except xy.UnsupportedVocabulary, ex:
                self.w(self.req._('unknown vocabulary:') + u' ' + unicode('ex'))
            self.wview('table', rset, 'null')

## sparql resultset views #####################################################

YAMS_XMLSCHEMA_MAPPING = {
    'String': 'string',
    'Int': 'integer',
    'Float': 'float',
    'Boolean': 'boolean',
    'Datetime': 'dateTime',
    'Date': 'date',
    'Time': 'time',
    # XXX the following types don't have direct mapping
    'Decimal': 'string',
    'Interval': 'duration',
    'Password': 'string',
    'Bytes': 'base64Binary',
    }

def xmlschema(yamstype):
    return 'http://www.w3.org/2001/XMLSchema#%s' % YAMS_XMLSCHEMA_MAPPING[yamstype]

class SparqlResultXmlView(AnyRsetView):
    """The spec can be found here: http://www.w3.org/TR/rdf-sparql-XMLres/
    """
    id = 'sparql'
    content_type = 'application/sparql-results+xml'
    templatable = False
    # XXX use accept-headers-selectors to choose among the sparql result views

    def call(self):
        # XXX handle UNION
        rqlst = self.rset.syntax_tree().children[0]
        varnames = [var.name for var in rqlst.selection]
        results = E.results()
        for rowidx in xrange(len(self.rset)):
            result = E.result()
            for colidx, varname in enumerate(varnames):
                result.append(self.cell_binding(rowidx, colidx, varname))
            results.append(result)
        sparql = E.sparql(E.head(*(E.variable(name=name) for name in varnames)),
                          results)
        self.w(u'<?xml version="1.0"?>\n')
        self.w(etree.tostring(sparql, encoding=unicode))

    def cell_binding(self, row, col, varname):
        celltype = self.rset.description[row][col]
        if self.schema.eschema(celltype).is_final():
            cellcontent = self.view('cell', self.rset, row=row, col=col)
            return E.binding(E.literal(cellcontent,
                                       datatype=xmlschema(celltype)),
                             name=varname)
        else:
            entity = self.entity(row, col)
            return E.binding(E.uri(entity.absolute_url()), name=varname)
