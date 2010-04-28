# copyright 2003-2010 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
__docformat__ = "restructuredtext en"
_ = unicode

import tempfile
import os

from logilab.mtconverter import xml_escape
from logilab.common.graph import escape, GraphGenerator, DotBackend

from cubicweb import Unauthorized, view
from cubicweb.selectors import (implements, has_related_entities, one_line_rset,
                                relation_possible, match_form_params,
                                implements, score_entity)
from cubicweb.interfaces import IWorkflowable
from cubicweb.view import EntityView
from cubicweb.schema import display_name
from cubicweb.web import uicfg, stdmsgs, action, component, form, action
from cubicweb.web import formfields as ff, formwidgets as fwdgs
from cubicweb.web.views import TmpFileViewMixin, forms, primary, autoform
from cubicweb.web.views.tabs import TabbedPrimaryView, PrimaryTab

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
_afs.tag_subject_of(('TrInfo', 'to_state', '*'), 'main', 'hidden')
_afs.tag_subject_of(('TrInfo', 'from_state', '*'), 'main', 'hidden')
_afs.tag_object_of(('State', 'allowed_transition', '*'), 'main', 'attributes')


# IWorkflowable views #########################################################

class ChangeStateForm(forms.CompositeEntityForm):
    __regid__ = 'changestate'

    form_renderer_id = 'base' # don't want EntityFormRenderer
    form_buttons = [fwdgs.SubmitButton(),
                    fwdgs.Button(stdmsgs.BUTTON_CANCEL, cwaction='cancel')]


class ChangeStateFormView(form.FormViewMixIn, view.EntityView):
    __regid__ = 'statuschange'
    title = _('status change')
    __select__ = (one_line_rset() & implements(IWorkflowable)
                  & match_form_params('treid'))

    def cell_call(self, row, col):
        entity = self.cw_rset.get_entity(row, col)
        transition = self._cw.entity_from_eid(self._cw.form['treid'])
        form = self.get_form(entity, transition)
        self.w(u'<h4>%s %s</h4>\n' % (self._cw._(transition.name),
                                      entity.view('oneline')))
        msg = self._cw._('status will change from %(st1)s to %(st2)s') % {
            'st1': entity.printable_state,
            'st2': self._cw._(transition.destination(entity).name)}
        self.w(u'<p>%s</p>\n' % msg)
        self.w(form.render())

    def redirectpath(self, entity):
        return entity.rest_path()

    def get_form(self, entity, transition, **kwargs):
        # XXX used to specify both rset/row/col and entity in case implements
        # selector (and not implements) is used on custom form
        form = self._cw.vreg['forms'].select(
            'changestate', self._cw, entity=entity, transition=transition,
            redirect_path=self.redirectpath(entity), **kwargs)
        trinfo = self._cw.vreg['etypes'].etype_class('TrInfo')(self._cw)
        trinfo.eid = self._cw.varmaker.next()
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
    __select__ = relation_possible('wf_info_for', role='object') & \
                 score_entity(lambda x: x.workflow_history)

    title = _('Workflow history')

    def cell_call(self, row, col, view=None):
        _ = self._cw._
        eid = self.cw_rset[row][col]
        sel = 'Any FS,TS,WF,D'
        rql = ' ORDERBY D DESC WHERE WF wf_info_for X,'\
              'WF from_state FS, WF to_state TS, WF comment C,'\
              'WF creation_date D'
        if self._cw.vreg.schema.eschema('CWUser').has_perm(self._cw, 'read'):
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
            rset = self._cw.execute(rql, {'x': eid})
        except Unauthorized:
            return
        if rset:
            self.wview('table', rset, title=_(self.title), displayactions=False,
                       displaycols=displaycols, headers=headers)


class WFHistoryVComponent(component.EntityVComponent):
    """display the workflow history for entities supporting it"""
    __regid__ = 'wfhistory'
    __select__ = WFHistoryView.__select__ & component.EntityVComponent.__select__
    context = 'navcontentbottom'
    title = _('Workflow history')

    def cell_call(self, row, col, view=None):
        self.wview('wfhistory', self.cw_rset, row=row, col=col, view=view)


# workflow actions #############################################################

class WorkflowActions(action.Action):
    """fill 'workflow' sub-menu of the actions box"""
    __regid__ = 'workflow'
    __select__ = (action.Action.__select__ & one_line_rset() &
                  relation_possible('in_state'))

    submenu = _('workflow')
    order = 10

    def fill_menu(self, box, menu):
        entity = self.cw_rset.get_entity(self.cw_row or 0, self.cw_col or 0)
        menu.label = u'%s: %s' % (self._cw._('state'), entity.printable_state)
        menu.append_anyway = True
        super(WorkflowActions, self).fill_menu(box, menu)

    def actual_actions(self):
        entity = self.cw_rset.get_entity(self.cw_row or 0, self.cw_col or 0)
        hastr = False
        for tr in entity.possible_transitions():
            url = entity.absolute_url(vid='statuschange', treid=tr.eid)
            yield self.build_action(self._cw._(tr.name), url)
            hastr = True
        # don't propose to see wf if user can't pass any transition
        if hastr:
            wfurl = entity.current_workflow.absolute_url()
            yield self.build_action(self._cw._('view workflow'), wfurl)
        if entity.workflow_history:
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
    __select__ = implements('Workflow')
    tabs = [  _('wf_tab_info'), _('wfgraph'),]
    default_tab = 'wf_tab_info'


class CellView(view.EntityView):
    __regid__ = 'cell'
    __select__ = implements('TrInfo')

    def cell_call(self, row, col, cellvid=None):
        self.w(self.cw_rset.get_entity(row, col).view('reledit', rtype='comment'))


class StateInContextView(view.EntityView):
    """convenience trick, State's incontext view should not be clickable"""
    __regid__ = 'incontext'
    __select__ = implements('State')

    def cell_call(self, row, col):
        self.w(xml_escape(self._cw.view('textincontext', self.cw_rset,
                                        row=row, col=col)))

class WorkflowTabTextView(PrimaryTab):
    __regid__ = 'wf_tab_info'
    __select__ = PrimaryTab.__select__ & one_line_rset() & implements('Workflow')

    def render_entity_attributes(self, entity):
        _ = self._cw._
        self.w(u'<div>%s</div>' % (entity.printable_value('description')))
        self.w(u'<span>%s%s</span>' % (_("workflow_of").capitalize(), _(" :")))
        html = []
        for e in  entity.workflow_of:
            view = e.view('outofcontext')
            if entity.eid == e.default_workflow[0].eid:
                view += u' <span>[%s]</span>' % _('default_workflow')
            html.append(view)
        self.w(', '.join(v for v in html))
        self.w(u'<h2>%s</h2>' % _("Transition_plural"))
        rset = self._cw.execute(
            'Any T,T,DS,T,TT ORDERBY TN WHERE T transition_of WF, WF eid %(x)s,'
            'T type TT, T name TN, T destination_state DS?', {'x': entity.eid})
        self.wview('editable-table', rset, 'null',
                   cellvids={ 1: 'trfromstates', 2: 'outofcontext', 3:'trsecurity',},
                   headers = (_('Transition'),  _('from_state'),
                              _('to_state'), _('permissions'), _('type') ),
                   )


class TransitionSecurityTextView(view.EntityView):
    __regid__ = 'trsecurity'
    __select__ = implements('Transition')

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
                   ( _('conditions'), _(" :"),
                     u'<br/>'.join((e.dc_title() for e
                                in entity.condition))))

class TransitionAllowedTextView(view.EntityView):
    __regid__ = 'trfromstates'
    __select__ = implements('Transition')

    def cell_call(self, row, col):
        entity = self.cw_rset.get_entity(self.cw_row, self.cw_col)
        self.w(u', '.join((e.view('outofcontext') for e
                           in entity.reverse_allowed_transition)))


# workflow entity types edition ################################################

_afs = uicfg.autoform_section
_afs.tag_subject_of(('TrInfo', 'to_state', '*'), 'main', 'hidden')
_afs.tag_subject_of(('TrInfo', 'from_state', '*'), 'main', 'hidden')
_afs.tag_object_of(('State', 'allowed_transition', '*'), 'main', 'attributes')
_afs.tag_subject_of(('State', 'allowed_transition', '*'), 'main', 'attributes')

def workflow_items_for_relation(req, wfeid, wfrelation, targetrelation):
    wf = req.entity_from_eid(wfeid)
    rschema = req.vreg.schema[targetrelation]
    return sorted((e.view('combobox'), e.eid)
                  for e in getattr(wf, 'reverse_%s' % wfrelation)
                  if rschema.has_perm(req, 'add', toeid=e.eid))


class TransitionEditionForm(autoform.AutomaticEntityForm):
    __select__ = implements('Transition')

    def workflow_states_for_relation(self, targetrelation):
        eids = self.edited_entity.linked_to('transition_of', 'subject')
        if eids:
            return workflow_items_for_relation(self._cw, eids[0], 'state_of',
                                               targetrelation)
        return []

    def subject_destination_state_vocabulary(self, rtype, limit=None):
        if not self.edited_entity.has_eid():
            return self.workflow_states_for_relation('destination_state')
        return self.subject_relation_vocabulary(rtype, limit)

    def object_allowed_transition_vocabulary(self, rtype, limit=None):
        if not self.edited_entity.has_eid():
            return self.workflow_states_for_relation('allowed_transition')
        return self.object_relation_vocabulary(rtype, limit)


class StateEditionForm(autoform.AutomaticEntityForm):
    __select__ = implements('State')

    def subject_allowed_transition_vocabulary(self, rtype, limit=None):
        if not self.edited_entity.has_eid():
            eids = self.edited_entity.linked_to('state_of', 'subject')
            if eids:
                return workflow_items_for_relation(self._cw, eids[0], 'transition_of',
                                                   'allowed_transition')
        return []


# workflow images ##############################################################

class WorkflowDotPropsHandler(object):
    def __init__(self, req):
        self._ = req._

    def node_properties(self, stateortransition):
        """return default DOT drawing options for a state or transition"""
        props = {'label': stateortransition.printable_value('name'),
                 'fontname': 'Courier', 'fontsize':10,
                 'href': stateortransition.absolute_url(),
                 }
        if hasattr(stateortransition, 'state_of'):
            props['shape'] = 'box'
            props['style'] = 'filled'
            if stateortransition.reverse_initial_state:
                props['fillcolor'] = '#88CC88'
        else:
            props['shape'] = 'ellipse'
            descr = []
            tr = stateortransition
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
            for outgoingstate in transition.potential_destinations():
                yield transition.eid, outgoingstate.eid, transition


class WorkflowGraphView(view.EntityView):
    __regid__ = 'wfgraph'
    __select__ = EntityView.__select__ & one_line_rset() & implements('Workflow')

    def cell_call(self, row, col):
        entity = self.cw_rset.get_entity(row, col)
        visitor = WorkflowVisitor(entity)
        prophdlr = WorkflowDotPropsHandler(self._cw)
        wfname = 'workflow%s' % str(entity.eid)
        generator = GraphGenerator(DotBackend(wfname, None,
                                              ratio='compress', size='30,10'))
        # map file
        pmap, mapfile = tempfile.mkstemp(".map", wfname)
        os.close(pmap)
        # image file
        fd, tmpfile = tempfile.mkstemp('.png')
        os.close(fd)
        generator.generate(visitor, prophdlr, tmpfile, mapfile)
        self.w(u'<img src="%s" alt="%s" usemap="#%s" />' % (
            xml_escape(entity.absolute_url(vid='wfimage', tmpfile=tmpfile)),
            xml_escape(self._cw._('graphical workflow for %s') % entity.name),
            wfname))
        stream = open(mapfile, 'r').read()
        stream = stream.decode(self._cw.encoding)
        self.w(stream)
        os.unlink(mapfile)

class WorkflowImageView(TmpFileViewMixin, view.EntityView):
    __regid__ = 'wfimage'
    __select__ = implements('Workflow')
    content_type = 'image/png'

    def cell_call(self, row=0, col=0):
        tmpfile = self._cw.form.get('tmpfile', None)
        self.w(open(tmpfile, 'rb').read())
        os.unlink(tmpfile)
