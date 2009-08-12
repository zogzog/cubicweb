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
from cubicweb.web import stdmsgs, action, component, form
from cubicweb.web.form import FormViewMixIn
from cubicweb.web.formfields import StringField,  RichTextField
from cubicweb.web.formwidgets import HiddenInput, SubmitButton, Button
from cubicweb.web.views import TmpFileViewMixin, forms


# IWorkflowable views #########################################################

class ChangeStateForm(forms.EntityFieldsForm):
    id = 'changestate'

    form_renderer_id = 'base' # don't want EntityFormRenderer
    form_buttons = [SubmitButton(stdmsgs.YES),
                     Button(stdmsgs.NO, cwaction='cancel')]

    __method = StringField(name='__method', initial='set_state',
                           widget=HiddenInput)
    state = StringField(eidparam=True, widget=HiddenInput)
    trcomment = RichTextField(label=_('comment:'), eidparam=True)


class ChangeStateFormView(FormViewMixIn, view.EntityView):
    id = 'statuschange'
    title = _('status change')
    __select__ = implements(IWorkflowable) & match_form_params('treid')

    def cell_call(self, row, col):
        entity = self.rset.get_entity(row, col)
        state = entity.in_state[0]
        transition = self.req.entity_from_eid(self.req.form['treid'])
        dest = transition.destination()
        _ = self.req._
        form = self.vreg.select('forms', 'changestate', self.req, rset=self.rset,
                                row=row, col=col, entity=entity,
                                redirect_path=self.redirectpath(entity))
        self.w(form.error_message())
        self.w(u'<h4>%s %s</h4>\n' % (_(transition.name),
                                      entity.view('oneline')))
        msg = _('status will change from %(st1)s to %(st2)s') % {
            'st1': _(state.name),
            'st2': _(dest.name)}
        self.w(u'<p>%s</p>\n' % msg)
        self.w(form.form_render(state=dest.eid, trcomment=u'',
                                trcomment_format=self.req.property_value('ui.default-text-format')))

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
        self.w(self.rset.get_entity(row, col).view('reledit', rtype='comment'))


class StateInContextView(view.EntityView):
    """convenience trick, State's incontext view should not be clickable"""
    id = 'incontext'
    __select__ = implements('State')

    def cell_call(self, row, col):
        self.w(xml_escape(self.view('textincontext', self.rset,
                                     row=row, col=col)))


# workflow images #############################################################

class ViewWorkflowAction(action.Action):
    id = 'workflow'
    __select__ = implements('CWEType') & has_related_entities('state_of', 'object')

    category = 'mainactions'
    title = _('view workflow')
    def url(self):
        entity = self.rset.get_entity(self.row or 0, self.col or 0)
        return entity.absolute_url(vid='workflow')


class CWETypeWorkflowView(view.EntityView):
    id = 'workflow'
    __select__ = implements('CWEType')
    cache_max_age = 60*60*2 # stay in http cache for 2 hours by default

    def cell_call(self, row, col, **kwargs):
        entity = self.rset.get_entity(row, col)
        self.w(u'<h1>%s</h1>' % (self.req._('workflow for %s')
                                 % display_name(self.req, entity.name)))
        self.w(u'<img src="%s" alt="%s"/>' % (
            xml_escape(entity.absolute_url(vid='ewfgraph')),
            xml_escape(self.req._('graphical workflow for %s') % entity.name)))


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
                descr.append('%s %s'% (self._('condition:'), tr.condition))
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


class CWETypeWorkflowImageView(TmpFileViewMixin, view.EntityView):
    id = 'ewfgraph'
    content_type = 'image/png'
    __select__ = implements('CWEType')

    def _generate(self, tmpfile):
        """display schema information for an entity"""
        entity = self.rset.get_entity(self.row, self.col)
        visitor = WorkflowVisitor(entity)
        prophdlr = WorkflowDotPropsHandler(self.req)
        generator = GraphGenerator(DotBackend('workflow', 'LR',
                                              ratio='compress', size='30,12'))
        return generator.generate(visitor, prophdlr, tmpfile)

