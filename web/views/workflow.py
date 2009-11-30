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
from cubicweb.selectors import (implements, has_related_entities, one_line_rset,
                                relation_possible, match_form_params,
                                entity_implements, score_entity)
from cubicweb.interfaces import IWorkflowable
from cubicweb.view import EntityView
from cubicweb.schema import display_name
from cubicweb.web import uicfg, stdmsgs, action, component, form, action
from cubicweb.web import formfields as ff, formwidgets as fwdgs
from cubicweb.web.views import TmpFileViewMixin, forms, primary, autoform


# IWorkflowable views #########################################################

class ChangeStateForm(forms.CompositeEntityForm):
    id = 'changestate'

    form_renderer_id = 'base' # don't want EntityFormRenderer
    form_buttons = [fwdgs.SubmitButton(),
                    fwdgs.Button(stdmsgs.BUTTON_CANCEL, cwaction='cancel')]


class ChangeStateFormView(form.FormViewMixIn, view.EntityView):
    id = 'statuschange'
    title = _('status change')
    __select__ = (one_line_rset() & implements(IWorkflowable)
                  & match_form_params('treid'))

    def cell_call(self, row, col):
        entity = self.rset.get_entity(row, col)
        transition = self.req.entity_from_eid(self.req.form['treid'])
        form = self.get_form(entity, transition)
        self.w(form.error_message())
        self.w(u'<h4>%s %s</h4>\n' % (self.req._(transition.name),
                                      entity.view('oneline')))
        msg = _('status will change from %(st1)s to %(st2)s') % {
            'st1': entity.printable_state,
            'st2': self.req._(transition.destination().name)}
        self.w(u'<p>%s</p>\n' % msg)
        self.w(form.form_render(wf_info_for=entity.eid,
                                by_transition=transition.eid))

    def redirectpath(self, entity):
        return entity.rest_path()

    def get_form(self, entity, transition, **kwargs):
        # XXX used to specify both rset/row/col and entity in case implements
        # selector (and not entity_implements) is used on custom form
        form = self.vreg['forms'].select(
            'changestate', self.req, entity=entity, transition=transition,
            redirect_path=self.redirectpath(entity), **kwargs)
        trinfo = self.vreg['etypes'].etype_class('TrInfo')(self.req)
        self.initialize_varmaker()
        trinfo.eid = self.varmaker.next()
        subform = self.vreg['forms'].select('edition', self.req, entity=trinfo,
                                            mainform=False)
        subform.field_by_name('by_transition').widget = fwdgs.HiddenInput()
        form.add_subform(subform)
        return form


class WFHistoryView(EntityView):
    id = 'wfhistory'
    __select__ = relation_possible('wf_info_for', role='object') & \
                 score_entity(lambda x: x.workflow_history)
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


# workflow actions #############################################################

class WorkflowActions(action.Action):
    """fill 'workflow' sub-menu of the actions box"""
    id = 'workflow'
    __select__ = (action.Action.__select__ & one_line_rset() &
                  relation_possible('in_state'))

    submenu = _('workflow')
    order = 10

    def fill_menu(self, box, menu):
        entity = self.rset.get_entity(self.row or 0, self.col or 0)
        menu.label = u'%s: %s' % (self.req._('state'), entity.printable_state)
        menu.append_anyway = True
        super(WorkflowActions, self).fill_menu(box, menu)

    def actual_actions(self):
        entity = self.rset.get_entity(self.row or 0, self.col or 0)
        hastr = False
        for tr in entity.possible_transitions():
            url = entity.absolute_url(vid='statuschange', treid=tr.eid)
            yield self.build_action(self.req._(tr.name), url)
            hastr = True
        # don't propose to see wf if user can't pass any transition
        if hastr:
            wfurl = entity.current_workflow.absolute_url()
            yield self.build_action(self.req._('view workflow'), wfurl)
        if entity.workflow_history:
            wfurl = entity.absolute_url(vid='wfhistory')
            yield self.build_action(self.req._('view history'), wfurl)


# workflow entity types views ##################################################

_pvs = uicfg.primaryview_section
_pvs.tag_subject_of(('Workflow', 'initial_state', '*'), 'hidden')
_pvs.tag_object_of(('*', 'state_of', 'Workflow'), 'hidden')
_pvs.tag_object_of(('*', 'transition_of', 'Workflow'), 'hidden')

_abaa = uicfg.actionbox_appearsin_addmenu
_abaa.tag_subject_of(('BaseTransition', 'condition', 'RQLExpression'), False)
_abaa.tag_subject_of(('State', 'allowed_transition', 'BaseTransition'), False)
_abaa.tag_object_of(('SubWorkflowExitPoint', 'destination_state', 'State'),
                    False)
_abaa.tag_object_of(('State', 'state_of', 'Workflow'), True)
_abaa.tag_object_of(('BaseTransition', 'transition_of', 'Workflow'), False)
_abaa.tag_object_of(('Transition', 'transition_of', 'Workflow'), True)
_abaa.tag_object_of(('WorkflowTransition', 'transition_of', 'Workflow'), True)

class WorkflowPrimaryView(primary.PrimaryView):
    __select__ = implements('Workflow')

    def render_entity_attributes(self, entity):
        self.w(entity.view('reledit', rtype='description'))
        self.w(u'<img src="%s" alt="%s"/>' % (
            xml_escape(entity.absolute_url(vid='wfgraph')),
            xml_escape(self.req._('graphical workflow for %s') % entity.name)))


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


# workflow entity types edition ################################################

_afs = uicfg.autoform_section
_afs.tag_subject_of(('TrInfo', 'to_state', '*'), 'generated')
_afs.tag_subject_of(('TrInfo', 'from_state', '*'), 'generated')
_afs.tag_object_of(('State', 'allowed_transition', '*'), 'primary')
_afs.tag_subject_of(('State', 'allowed_transition', '*'), 'primary')

def workflow_items_for_relation(req, wfeid, wfrelation, targetrelation):
    wf = req.entity_from_eid(wfeid)
    rschema = req.vreg.schema[targetrelation]
    return sorted((e.view('combobox'), e.eid)
                  for e in getattr(wf, 'reverse_%s' % wfrelation)
                  if rschema.has_perm(req, 'add', toeid=e.eid))


class TransitionEditionForm(autoform.AutomaticEntityForm):
    __select__ = entity_implements('Transition')

    def workflow_states_for_relation(self, targetrelation):
        eids = self.edited_entity.linked_to('transition_of', 'subject')
        if eids:
            return workflow_items_for_relation(self.req, eids[0], 'state_of',
                                               targetrelation)
        return []

    def subject_destination_state_vocabulary(self, rtype, limit=None):
        if not self.edited_entity.has_eid():
            return self.workflow_states_for_relation('destination_state')
        return self.subject_relation_vocabulary(rtype, limit)

    def object_allowed_transition_vocabulary(self, rtype, limit=None):
        if not self.edited_entity.has_eid():
            return self.workflow_states_for_relation('allowed_transition')
        return self.subject_relation_vocabulary(rtype, limit)


class StateEditionForm(autoform.AutomaticEntityForm):
    __select__ = entity_implements('State')

    def subject_allowed_transition_vocabulary(self, rtype, limit=None):
        if not self.edited_entity.has_eid():
            eids = self.edited_entity.linked_to('state_of', 'subject')
            if eids:
                return workflow_items_for_relation(self.req, eids[0], 'transition_of',
                                                   'allowed_transition')
        return []


# workflow images ##############################################################

class WorkflowDotPropsHandler(object):
    def __init__(self, req):
        self._ = req._

    def node_properties(self, stateortransition):
        """return default DOT drawing options for a state or transition"""
        props = {'label': stateortransition.printable_value('name'),
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
                    ','.join(g.printable_value('name') for g in tr.require_group)))
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
        entity = self.rset.get_entity(self.row, self.col)
        visitor = WorkflowVisitor(entity)
        prophdlr = WorkflowDotPropsHandler(self.req)
        generator = GraphGenerator(DotBackend('workflow', 'LR',
                                              ratio='compress', size='30,12'))
        return generator.generate(visitor, prophdlr, tmpfile)

