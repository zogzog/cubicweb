"""workflow views:

* IWorkflowable views and forms
* workflow entities views (State, Transition, TrInfo)

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"
_ = unicode

from logilab.mtconverter import xml_escape
from logilab.common.graph import escape, GraphGenerator, DotBackend

from cubicweb import Unauthorized, view
from cubicweb.selectors import (implements, has_related_entities,
                                relation_possible, match_form_params)
from cubicweb.interfaces import IWorkflowable
from cubicweb.view import EntityView
from cubicweb.schema import display_name
from cubicweb.web import stdmsgs, action, component, form, action
from cubicweb.web import formfields as ff, formwidgets as fwdgs
from cubicweb.web.views import TmpFileViewMixin, forms, primary


# IWorkflowable views #########################################################

class ChangeStateForm(forms.CompositeEntityForm):
    id = 'changestate'

    form_renderer_id = 'base' # don't want EntityFormRenderer
    form_buttons = [fwdgs.SubmitButton(stdmsgs.YES),
                    fwdgs.Button(stdmsgs.NO, cwaction='cancel')]


class ChangeStateFormView(form.FormViewMixIn, view.EntityView):
    id = 'statuschange'
    title = _('status change')
    __select__ = implements(IWorkflowable) & match_form_params('treid')

    def cell_call(self, row, col):
        entity = self.entity(row, col)
        transition = self.req.entity_from_eid(self.req.form['treid'])
        dest = transition.destination()
        _ = self.req._
        form = self.vreg['forms'].select('changestate', self.req, entity=entity,
                                         redirect_path=self.redirectpath(entity))
        self.w(form.error_message())
        self.w(u'<h4>%s %s</h4>\n' % (_(transition.name),
                                      entity.view('oneline')))
        msg = _('status will change from %(st1)s to %(st2)s') % {
            'st1': _(entity.current_state.name),
            'st2': _(dest.name)}
        self.w(u'<p>%s</p>\n' % msg)
        trinfo = self.vreg['etypes'].etype_class('TrInfo')(self.req)
        self.initialize_varmaker()
        trinfo.eid = self.varmaker.next()
        subform = self.vreg['forms'].select('edition', self.req, entity=trinfo,
                                            mainform=False)
        subform.field_by_name('by_transition').widget = fwdgs.HiddenInput()
        form.form_add_subform(subform)
        self.w(form.form_render(wf_info_for=entity.eid,
                                by_transition=transition.eid))

    def redirectpath(self, entity):
        return entity.rest_path()


class WFHistoryView(EntityView):
    id = 'wfhistory'
    __select__ = relation_possible('wf_info_for', role='object')
    title = _('Workflow history')

    def cell_call(self, row, col, view=None):
        _ = self.req._
        eid = self.rset[row][col]
        sel = 'Any FS,TS,WF,D'
        rql = ' ORDERBY D DESC WHERE WF wf_info_for X,'\
              'WF from_state FS, WF to_state TS, WF comment C,'\
              'WF creation_date D'
        if self.vreg.schema.eschema('CWUser').has_perm(self.req, 'read'):
            sel += ',U,C'
            rql += ', WF owned_by U?'
            displaycols = range(5)
            headers = (_('from_state'), _('to_state'), _('comment'), _('date'),
                       _('CWUser'))
        else:
            sel += ',C'
            displaycols = range(4)
            headers = (_('from_state'), _('to_state'), _('comment'), _('date'))
        rql = '%s %s, X eid %%(x)s' % (sel, rql)
        try:
            rset = self.req.execute(rql, {'x': eid}, 'x')
        except Unauthorized:
            return
        if rset:
            self.wview('table', rset, title=_(self.title), displayactions=False,
                       displaycols=displaycols, headers=headers)


class WFHistoryVComponent(component.EntityVComponent):
    """display the workflow history for entities supporting it"""
    id = 'wfhistory'
    __select__ = WFHistoryView.__select__ & component.EntityVComponent.__select__
    context = 'navcontentbottom'
    title = _('Workflow history')

    def cell_call(self, row, col, view=None):
        self.wview('wfhistory', self.rset, row=row, col=col, view=view)

# workflow entity types views #################################################

class CellView(view.EntityView):
    id = 'cell'
    __select__ = implements('TrInfo')

    def cell_call(self, row, col, cellvid=None):
        self.w(self.entity(row, col).view('reledit', rtype='comment'))


class StateInContextView(view.EntityView):
    """convenience trick, State's incontext view should not be clickable"""
    id = 'incontext'
    __select__ = implements('State')

    def cell_call(self, row, col):
        self.w(xml_escape(self.view('textincontext', self.rset,
                                     row=row, col=col)))


class WorkflowPrimaryView(primary.PrimaryView):
    id = 'workflow'
    __select__ = implements('Workflow')
    cache_max_age = 60*60*2 # stay in http cache for 2 hours by default

    def render_entity_attributes(self, entity):
        self.w(u'<img src="%s" alt="%s"/>' % (
            xml_escape(entity.absolute_url(vid='wfgraph')),
            xml_escape(self.req._('graphical workflow for %s') % entity.name)))


# workflow images ##############################################################

class WorkflowDotPropsHandler(object):
    def __init__(self, req):
        self._ = req._

    def node_properties(self, stateortransition):
        """return default DOT drawing options for a state or transition"""
        props = {'label': stateortransition.name,
                 'fontname': 'Courier'}
        if hasattr(stateortransition, 'state_of'):
            props['shape'] = 'box'
            props['style'] = 'filled'
            if stateortransition.reverse_initial_state:
                props['color'] = '#88CC88'
        else:
            props['shape'] = 'ellipse'
            descr = []
            tr = stateortransition
            if tr.require_group:
                descr.append('%s %s'% (
                    self._('groups:'),
                    ','.join(g.name for g in tr.require_group)))
            if tr.condition:
                descr.append('%s %s'% (
                    self._('condition:'),
                    ' | '.join(e.expression for e in tr.condition)))
            if descr:
                props['label'] += escape('\n'.join(descr))
        return props

    def edge_properties(self, transition, fromstate, tostate):
        return {'label': '', 'dir': 'forward',
                'color': 'black', 'style': 'filled'}


class WorkflowVisitor:
    def __init__(self, entity):
        self.entity = entity

    def nodes(self):
        for state in self.entity.reverse_state_of:
            state.complete()
            yield state.eid, state

        for transition in self.entity.reverse_transition_of:
            transition.complete()
            yield transition.eid, transition

    def edges(self):
        for transition in self.entity.reverse_transition_of:
            for incomingstate in transition.reverse_allowed_transition:
                yield incomingstate.eid, transition.eid, transition
            yield transition.eid, transition.destination().eid, transition


class WorkflowImageView(TmpFileViewMixin, view.EntityView):
    id = 'wfgraph'
    content_type = 'image/png'
    __select__ = implements('Workflow')

    def _generate(self, tmpfile):
        """display schema information for an entity"""
        entity = self.entity(self.row, self.col)
        visitor = WorkflowVisitor(entity)
        prophdlr = WorkflowDotPropsHandler(self.req)
        generator = GraphGenerator(DotBackend('workflow', 'LR',
                                              ratio='compress', size='30,12'))
        return generator.generate(visitor, prophdlr, tmpfile)

