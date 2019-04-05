# copyright 2003 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
# contact http://www.logilab.fr/ -- mailto:contact@logilab.fr
#
# This file is part of CubicWeb.
#
# CubicWeb is free software: you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation, either version 2.1 of the License, or (at your option)
# any later version.
#
# CubicWeb is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License along
# with CubicWeb.  If not, see <http://www.gnu.org/licenses/>.
"""workflow views:

* IWorkflowable views and forms
* workflow entities views (State, Transition, TrInfo)
"""


from cubicweb import _

from logilab.mtconverter import xml_escape

from cubicweb import Unauthorized
from cubicweb.predicates import (one_line_rset,
                                 relation_possible, match_form_params,
                                 score_entity, is_instance, adaptable)
from cubicweb.view import EntityView
from cubicweb.web import stdmsgs, action, component, form
from cubicweb.web import formwidgets as fwdgs
from cubicweb.web.views import uicfg, forms, ibreadcrumbs
from cubicweb.web.views.tabs import TabbedPrimaryView, PrimaryTab
from cubicweb.web.views.dotgraphview import DotGraphView, DotPropsHandler

_pvs = uicfg.primaryview_section
_pvs.tag_subject_of(('Workflow', 'initial_state', '*'), 'hidden')
_pvs.tag_object_of(('*', 'state_of', 'Workflow'), 'hidden')
_pvs.tag_object_of(('*', 'transition_of', 'Workflow'), 'hidden')
_pvs.tag_object_of(('*', 'wf_info_for', '*'), 'hidden')
for rtype in ('in_state', 'by_transition', 'from_state', 'to_state'):
    _pvs.tag_subject_of(('*', rtype, '*'), 'hidden')
    _pvs.tag_object_of(('*', rtype, '*'), 'hidden')
_pvs.tag_object_of(('*', 'wf_info_for', '*'), 'hidden')

_abaa = uicfg.actionbox_appearsin_addmenu
_abaa.tag_subject_of(('BaseTransition', 'condition', 'RQLExpression'), False)
_abaa.tag_subject_of(('State', 'allowed_transition', 'BaseTransition'), False)
_abaa.tag_object_of(('SubWorkflowExitPoint', 'destination_state', 'State'),
                    False)
_abaa.tag_subject_of(('*', 'wf_info_for', '*'), False)
_abaa.tag_object_of(('*', 'wf_info_for', '*'), False)

_abaa.tag_object_of(('*', 'state_of', 'CWEType'), True)
_abaa.tag_object_of(('*', 'transition_of', 'CWEType'), True)
_abaa.tag_subject_of(('Transition', 'destination_state', '*'), True)
_abaa.tag_object_of(('*', 'allowed_transition', 'Transition'), True)
_abaa.tag_object_of(('*', 'destination_state', 'State'), True)
_abaa.tag_subject_of(('State', 'allowed_transition', '*'), True)
_abaa.tag_object_of(('State', 'state_of', 'Workflow'), True)
_abaa.tag_object_of(('Transition', 'transition_of', 'Workflow'), True)
_abaa.tag_object_of(('WorkflowTransition', 'transition_of', 'Workflow'), True)

_afs = uicfg.autoform_section
_affk = uicfg.autoform_field_kwargs


# IWorkflowable views #########################################################

class ChangeStateForm(forms.CompositeEntityForm):
    # set dom id to ensure there is no conflict with edition form (see
    # session_key() implementation)
    __regid__ = domid = 'changestate'

    form_renderer_id = 'base'  # don't want EntityFormRenderer
    form_buttons = [fwdgs.SubmitButton(),
                    fwdgs.Button(stdmsgs.BUTTON_CANCEL,
                                 {'class': fwdgs.Button.css_class + ' cwjs-edition-cancel'})]


class ChangeStateFormView(form.FormViewMixIn, EntityView):
    __regid__ = 'statuschange'
    title = _('status change')
    __select__ = (one_line_rset()
                  & match_form_params('treid')
                  & adaptable('IWorkflowable'))

    def cell_call(self, row, col):
        entity = self.cw_rset.get_entity(row, col)
        transition = self._cw.entity_from_eid(self._cw.form['treid'])
        form = self.get_form(entity, transition)
        self.w(u'<h4>%s %s</h4>\n' % (self._cw._(transition.name),
                                      entity.view('oneline')))
        msg = self._cw._('status will change from %(st1)s to %(st2)s') % {
            'st1': entity.cw_adapt_to('IWorkflowable').printable_state,
            'st2': self._cw._(transition.destination(entity).name)}
        self.w(u'<p>%s</p>\n' % msg)
        form.render(w=self.w)

    def redirectpath(self, entity):
        return entity.rest_path()

    def get_form(self, entity, transition, **kwargs):
        # XXX used to specify both rset/row/col and entity in case implements
        # selector (and not is_instance) is used on custom form
        form = self._cw.vreg['forms'].select(
            'changestate', self._cw, entity=entity, transition=transition,
            redirect_path=self.redirectpath(entity), **kwargs)
        trinfo = self._cw.vreg['etypes'].etype_class('TrInfo')(self._cw)
        trinfo.eid = next(self._cw.varmaker)
        subform = self._cw.vreg['forms'].select('edition', self._cw, entity=trinfo,
                                                mainform=False)
        subform.field_by_name('wf_info_for', 'subject').value = entity.eid
        trfield = subform.field_by_name('by_transition', 'subject')
        trfield.widget = fwdgs.HiddenInput()
        trfield.value = transition.eid
        form.add_subform(subform)
        return form


class WFHistoryView(EntityView):
    __regid__ = 'wfhistory'
    __select__ = (relation_possible('wf_info_for', role='object')
                  & score_entity(lambda x: x.cw_adapt_to('IWorkflowable').workflow_history))

    title = _('Workflow history')

    def cell_call(self, row, col, view=None, title=title):
        _ = self._cw._
        eid = self.cw_rset[row][col]
        sel = 'Any FS,TS,C,D'
        rql = ' ORDERBY D DESC WHERE WF wf_info_for X,'\
              'WF from_state FS, WF to_state TS, WF comment C,'\
              'WF creation_date D'
        if self._cw.vreg.schema.eschema('CWUser').has_perm(self._cw, 'read'):
            sel += ',U,WF'
            rql += ', WF owned_by U?'
            headers = (_('from_state'), _('to_state'), _('comment'), _('date'),
                       _('CWUser'))
        else:
            sel += ',WF'
            headers = (_('from_state'), _('to_state'), _('comment'), _('date'))
        sel += ',FSN,TSN,CF'
        rql = '%s %s, FS name FSN, TS name TSN, WF comment_format CF, X eid %%(x)s' % (sel, rql)
        try:
            rset = self._cw.execute(rql, {'x': eid})
        except Unauthorized:
            return
        if rset:
            if title:
                self.w(u'<h2>%s</h2>\n' % _(title))
            self.wview('table', rset, headers=headers,
                       cellvids={2: 'editable-final'})


class WFHistoryVComponent(component.EntityCtxComponent):
    """display the workflow history for entities supporting it"""
    __regid__ = 'wfhistory'
    __select__ = component.EntityCtxComponent.__select__ & WFHistoryView.__select__
    context = 'navcontentbottom'
    title = _('Workflow history')

    def render_body(self, w):
        self.entity.view('wfhistory', w=w, title=None)


class InContextWithStateView(EntityView):
    """display incontext view for an entity as well as its current state"""
    __regid__ = 'incontext-state'
    __select__ = adaptable('IWorkflowable')

    def entity_call(self, entity):
        iwf = entity.cw_adapt_to('IWorkflowable')
        self.w(u'%s [%s]' % (entity.view('incontext'), iwf.printable_state))


# workflow actions #############################################################

class WorkflowActions(action.Action):
    """fill 'workflow' sub-menu of the actions box"""
    __regid__ = 'workflow'
    __select__ = (action.Action.__select__ & one_line_rset()
                  & relation_possible('in_state'))

    submenu = _('workflow')
    order = 10

    def fill_menu(self, box, menu):
        entity = self.cw_rset.get_entity(self.cw_row or 0, self.cw_col or 0)
        menu.label = u'%s: %s' % (self._cw._('state'),
                                  entity.cw_adapt_to('IWorkflowable').printable_state)
        menu.append_anyway = True
        super(WorkflowActions, self).fill_menu(box, menu)

    def actual_actions(self):
        entity = self.cw_rset.get_entity(self.cw_row or 0, self.cw_col or 0)
        iworkflowable = entity.cw_adapt_to('IWorkflowable')
        hastr = False
        for tr in iworkflowable.possible_transitions():
            url = entity.absolute_url(vid='statuschange', treid=tr.eid)
            yield self.build_action(self._cw._(tr.name), url)
            hastr = True
        # don't propose to see wf if user can't pass any transition
        if hastr:
            wfurl = iworkflowable.current_workflow.absolute_url()
            yield self.build_action(self._cw._('view workflow'), wfurl)
        if iworkflowable.workflow_history:
            wfurl = entity.absolute_url(vid='wfhistory')
            yield self.build_action(self._cw._('view history'), wfurl)


# workflow entity types views ##################################################

_pvs = uicfg.primaryview_section
_pvs.tag_subject_of(('Workflow', 'initial_state', '*'), 'hidden')
_pvs.tag_object_of(('*', 'state_of', 'Workflow'), 'hidden')
_pvs.tag_object_of(('*', 'transition_of', 'Workflow'), 'hidden')
_pvs.tag_object_of(('*', 'default_workflow', 'Workflow'), 'hidden')

_abaa = uicfg.actionbox_appearsin_addmenu
_abaa.tag_subject_of(('BaseTransition', 'condition', 'RQLExpression'), False)
_abaa.tag_subject_of(('State', 'allowed_transition', 'BaseTransition'), False)
_abaa.tag_object_of(('SubWorkflowExitPoint', 'destination_state', 'State'),
                    False)
_abaa.tag_object_of(('State', 'state_of', 'Workflow'), True)
_abaa.tag_object_of(('BaseTransition', 'transition_of', 'Workflow'), False)
_abaa.tag_object_of(('Transition', 'transition_of', 'Workflow'), True)
_abaa.tag_object_of(('WorkflowTransition', 'transition_of', 'Workflow'), True)


class WorkflowPrimaryView(TabbedPrimaryView):
    __select__ = is_instance('Workflow')
    tabs = [_('wf_tab_info'), _('wfgraph')]
    default_tab = 'wf_tab_info'


class StateInContextView(EntityView):
    """convenience trick, State's incontext view should not be clickable"""
    __regid__ = 'incontext'
    __select__ = is_instance('State')

    def cell_call(self, row, col):
        self.w(xml_escape(self._cw.view('textincontext', self.cw_rset,
                                        row=row, col=col)))


class WorkflowTabTextView(PrimaryTab):
    __regid__ = 'wf_tab_info'
    __select__ = PrimaryTab.__select__ & one_line_rset() & is_instance('Workflow')

    def render_entity_attributes(self, entity):
        _ = self._cw._
        self.w(u'<div>%s</div>' % (entity.printable_value('description')))
        self.w(u'<span>%s%s</span>' % (_("workflow_of").capitalize(), _(" :")))
        html = []
        for e in entity.workflow_of:
            view = e.view('outofcontext')
            if entity.eid == e.default_workflow[0].eid:
                view += u' <span>[%s]</span>' % _('default_workflow')
            html.append(view)
        self.w(', '.join(v for v in html))
        self.w(u'<h2>%s</h2>' % _("Transition_plural"))
        rset = self._cw.execute(
            'Any T,T,DS,T,TT ORDERBY TN WHERE T transition_of WF, WF eid %(x)s,'
            'T type TT, T name TN, T destination_state DS?', {'x': entity.eid})
        self.wview('table', rset, 'null',
                   cellvids={1: 'trfromstates', 2: 'outofcontext', 3: 'trsecurity'},
                   headers=(_('Transition'), _('from_state'),
                            _('to_state'), _('permissions'), _('type')))


class TransitionSecurityTextView(EntityView):
    __regid__ = 'trsecurity'
    __select__ = is_instance('Transition')

    def cell_call(self, row, col):
        _ = self._cw._
        entity = self.cw_rset.get_entity(self.cw_row, self.cw_col)
        if entity.require_group:
            self.w(u'<div>%s%s %s</div>' %
                   (_('groups'), _(" :"),
                    u', '.join((g.view('incontext') for g
                               in entity.require_group))))
        if entity.condition:
            self.w(u'<div>%s%s %s</div>' %
                   (_('conditions'), _(" :"),
                    u'<br/>'.join((e.dc_title() for e in entity.condition))))


class TransitionAllowedTextView(EntityView):
    __regid__ = 'trfromstates'
    __select__ = is_instance('Transition')

    def cell_call(self, row, col):
        entity = self.cw_rset.get_entity(self.cw_row, self.cw_col)
        self.w(u', '.join((e.view('outofcontext') for e
                           in entity.reverse_allowed_transition)))


# workflow entity types edition ################################################

def _wf_items_for_relation(req, wfeid, wfrelation, field):
    wf = req.entity_from_eid(wfeid)
    rschema = req.vreg.schema[field.name]
    param = 'toeid' if field.role == 'subject' else 'fromeid'
    return sorted((e.view('combobox'), str(e.eid))
                  for e in getattr(wf, 'reverse_%s' % wfrelation)
                  if rschema.has_perm(req, 'add', **{param: e.eid}))


# TrInfo
_afs.tag_subject_of(('TrInfo', 'to_state', '*'), 'main', 'hidden')
_afs.tag_subject_of(('TrInfo', 'from_state', '*'), 'main', 'hidden')
_afs.tag_attribute(('TrInfo', 'tr_count'), 'main', 'hidden')


# BaseTransition
# XXX * allowed_transition BaseTransition
# XXX BaseTransition destination_state *

def transition_states_vocabulary(form, field):
    entity = form.edited_entity
    if entity.has_eid():
        wfeid = entity.transition_of[0].eid
    else:
        eids = form.linked_to.get(('transition_of', 'subject'))
        if not eids:
            return []
        wfeid = eids[0]
    return _wf_items_for_relation(form._cw, wfeid, 'state_of', field)


_afs.tag_subject_of(('*', 'destination_state', '*'), 'main', 'attributes')
_affk.tag_subject_of(('*', 'destination_state', '*'),
                     {'choices': transition_states_vocabulary})
_afs.tag_object_of(('*', 'allowed_transition', '*'), 'main', 'attributes')
_affk.tag_object_of(('*', 'allowed_transition', '*'),
                    {'choices': transition_states_vocabulary})


# State

def state_transitions_vocabulary(form, field):
    entity = form.edited_entity
    if entity.has_eid():
        wfeid = entity.state_of[0].eid
    else:
        eids = form.linked_to.get(('state_of', 'subject'))
        if not eids:
            return []
        wfeid = eids[0]
    return _wf_items_for_relation(form._cw, wfeid, 'transition_of', field)


_afs.tag_subject_of(('State', 'allowed_transition', '*'), 'main', 'attributes')
_affk.tag_subject_of(('State', 'allowed_transition', '*'),
                     {'choices': state_transitions_vocabulary})


# adaptaters ###################################################################

class WorkflowIBreadCrumbsAdapter(ibreadcrumbs.IBreadCrumbsAdapter):
    __select__ = is_instance('Workflow')

    # XXX what if workflow of multiple types?
    def parent_entity(self):
        return self.entity.workflow_of and self.entity.workflow_of[0] or None


class WorkflowItemIBreadCrumbsAdapter(ibreadcrumbs.IBreadCrumbsAdapter):
    __select__ = is_instance('BaseTransition', 'State')

    def parent_entity(self):
        return self.entity.workflow


class TransitionItemIBreadCrumbsAdapter(ibreadcrumbs.IBreadCrumbsAdapter):
    __select__ = is_instance('SubWorkflowExitPoint')

    def parent_entity(self):
        return self.entity.reverse_subworkflow_exit[0]


class TrInfoIBreadCrumbsAdapter(ibreadcrumbs.IBreadCrumbsAdapter):
    __select__ = is_instance('TrInfo')

    def parent_entity(self):
        return self.entity.for_entity


# workflow images ##############################################################

class WorkflowDotPropsHandler(DotPropsHandler):

    def node_properties(self, stateortransition):
        """return default DOT drawing options for a state or transition"""
        props = super(WorkflowDotPropsHandler, self).node_properties(stateortransition)
        if hasattr(stateortransition, 'state_of'):
            props['shape'] = 'box'
            props['style'] = 'filled'
            if stateortransition.reverse_initial_state:
                props['fillcolor'] = '#88CC88'
        else:
            props['shape'] = 'ellipse'
        return props


class WorkflowVisitor(object):
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
            for outgoingstate in transition.potential_destinations():
                yield transition.eid, outgoingstate.eid, transition


class WorkflowGraphView(DotGraphView):
    __regid__ = 'wfgraph'
    __select__ = EntityView.__select__ & one_line_rset() & is_instance('Workflow')

    def build_visitor(self, entity):
        return WorkflowVisitor(entity)

    def build_dotpropshandler(self):
        return WorkflowDotPropsHandler(self._cw)
