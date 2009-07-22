"""SPARQL integration

:organization: Logilab
:copyright: 2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
import rql
from yams import xy

from cubicweb.view import StartupView
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
