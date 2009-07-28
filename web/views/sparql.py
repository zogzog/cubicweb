"""SPARQL integration

:organization: Logilab
:copyright: 2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
v__docformat__ = "restructuredtext en"

import rql
from yams import xy

from lxml import etree
from lxml.builder import E

from cubicweb.view import StartupView, AnyRsetView
from cubicweb.web import Redirect, form, formfields, formwidgets as fwdgs
from cubicweb.web.views import forms, urlrewrite
try:
    from cubicweb.spa2rql import Sparql2rqlTranslator
except ImportError:
    # fyzz not available (only a recommends)
    Sparql2rqlTranslator = None

class SparqlForm(forms.FieldsForm):
    id = 'sparql'
    sparql = formfields.StringField(help=_('type here a sparql query'))
    resultvid = formfields.StringField(choices=((_('table'), 'table'),
                                                (_('sparql xml'), 'sparqlxml')),
                                       widget=fwdgs.Radio,
                                       initial='table')
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
        vid = self.req.form.get('resultvid', 'table')
        if sparql:
            try:
                qinfo = Sparql2rqlTranslator(self.schema).translate(sparql)
            except rql.TypeResolverException, ex:
                self.w(self.req._('can not resolve entity types:') + u' ' + unicode('ex'))
            except UnsupportedQuery:
                self.w(self.req._('we are not yet ready to handle this query'))
            except xy.UnsupportedVocabulary, ex:
                self.w(self.req._('unknown vocabulary:') + u' ' + unicode('ex'))
            if vid == 'sparqlxml':
                url = self.build_url('view', rql=qinfo.finalize(), vid=vid)
                raise Redirect(url)
            rset = self.req.execute(qinfo.finalize())
            self.wview(vid, rset, 'null')


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
    id = 'sparqlxml'
    content_type = 'application/sparql-results+xml'
    templatable = False

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
        self.w(etree.tostring(sparql, encoding=unicode, pretty_print=True))

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

    def set_request_content_type(self):
        """overriden to set the correct filetype and filename"""
        self.req.set_content_type(self.content_type,
                                  filename='sparql.xml',
                                  encoding=self.req.encoding)

def registration_callback(vreg):
    if Sparql2rqlTranslator is not None:
        vreg.register_all(globals().values(), __name__)
