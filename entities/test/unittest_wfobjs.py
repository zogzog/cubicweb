# copyright 2003-2012 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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

from cubicweb import ValidationError
from cubicweb.devtools.testlib import CubicWebTC


def add_wf(self, etype, name=None, default=False):
    if name is None:
        name = etype
    return self.shell().add_workflow(name, etype, default=default,
                                     ensure_workflowable=False)

def parse_hist(wfhist):
    return [(ti.previous_state.name, ti.new_state.name,
             ti.transition and ti.transition.name, ti.comment)
            for ti in wfhist]


class WorkflowBuildingTC(CubicWebTC):

    def test_wf_construction(self):
        wf = add_wf(self, 'Company')
        foo = wf.add_state(u'foo', initial=True)
        bar = wf.add_state(u'bar')
        self.assertEqual(wf.state_by_name('bar').eid, bar.eid)
        self.assertEqual(wf.state_by_name('barrr'), None)
        baz = wf.add_transition(u'baz', (foo,), bar, ('managers',))
        self.assertEqual(wf.transition_by_name('baz').eid, baz.eid)
        self.assertEqual(len(baz.require_group), 1)
        self.assertEqual(baz.require_group[0].name, 'managers')

    def test_duplicated_state(self):
        wf = add_wf(self, 'Company')
        wf.add_state(u'foo', initial=True)
        self.commit()
        wf.add_state(u'foo')
        with self.assertRaises(ValidationError) as cm:
            self.commit()
        self.assertEqual({'name-subject': 'workflow already has a state of that name'},
                         cm.exception.errors)
        # no pb if not in the same workflow
        wf2 = add_wf(self, 'Company')
        foo = wf2.add_state(u'foo', initial=True)
        self.commit()
        # gnark gnark
        bar = wf.add_state(u'bar')
        self.commit()
        bar.cw_set(name=u'foo')
        with self.assertRaises(ValidationError) as cm:
            self.commit()
        self.assertEqual({'name-subject': 'workflow already has a state of that name'},
                         cm.exception.errors)

    def test_duplicated_transition(self):
        wf = add_wf(self, 'Company')
        foo = wf.add_state(u'foo', initial=True)
        bar = wf.add_state(u'bar')
        wf.add_transition(u'baz', (foo,), bar, ('managers',))
        wf.add_transition(u'baz', (bar,), foo)
        with self.assertRaises(ValidationError) as cm:
            self.commit()
        self.assertEqual(cm.exception.errors, {'name-subject': 'workflow already has a transition of that name'})
        # no pb if not in the same workflow
        wf2 = add_wf(self, 'Company')
        foo = wf.add_state(u'foo', initial=True)
        bar = wf.add_state(u'bar')
        wf.add_transition(u'baz', (foo,), bar, ('managers',))
        self.commit()
        # gnark gnark
        biz = wf.add_transition(u'biz', (bar,), foo)
        self.commit()
        biz.cw_set(name=u'baz')
        with self.assertRaises(ValidationError) as cm:
            self.commit()
        self.assertEqual(cm.exception.errors, {'name-subject': 'workflow already has a transition of that name'})


class WorkflowTC(CubicWebTC):

    def setup_database(self):
        req = self.request()
        rschema = self.schema['in_state']
        for rdef in rschema.rdefs.itervalues():
            self.assertEqual(rdef.cardinality, '1*')
        self.member = self.create_user(req, 'member')

    def test_workflow_base(self):
        req = self.request()
        e = self.create_user(req, 'toto')
        iworkflowable = e.cw_adapt_to('IWorkflowable')
        self.assertEqual(iworkflowable.state, 'activated')
        iworkflowable.change_state('deactivated', u'deactivate 1')
        self.commit()
        iworkflowable.change_state('activated', u'activate 1')
        self.commit()
        iworkflowable.change_state('deactivated', u'deactivate 2')
        self.commit()
        e.cw_clear_relation_cache('wf_info_for', 'object')
        self.assertEqual([tr.comment for tr in e.reverse_wf_info_for],
                          ['deactivate 1', 'activate 1', 'deactivate 2'])
        self.assertEqual(iworkflowable.latest_trinfo().comment, 'deactivate 2')

    def test_possible_transitions(self):
        user = self.execute('CWUser X').get_entity(0, 0)
        iworkflowable = user.cw_adapt_to('IWorkflowable')
        trs = list(iworkflowable.possible_transitions())
        self.assertEqual(len(trs), 1)
        self.assertEqual(trs[0].name, u'deactivate')
        self.assertEqual(trs[0].destination(None).name, u'deactivated')
        # test a std user get no possible transition
        cnx = self.login('member')
        req = self.request()
        # fetch the entity using the new session
        trs = list(req.user.cw_adapt_to('IWorkflowable').possible_transitions())
        self.assertEqual(len(trs), 0)
        cnx.close()

    def _test_manager_deactivate(self, user):
        iworkflowable = user.cw_adapt_to('IWorkflowable')
        user.cw_clear_relation_cache('in_state', 'subject')
        self.assertEqual(len(user.in_state), 1)
        self.assertEqual(iworkflowable.state, 'deactivated')
        trinfo = iworkflowable.latest_trinfo()
        self.assertEqual(trinfo.previous_state.name, 'activated')
        self.assertEqual(trinfo.new_state.name, 'deactivated')
        self.assertEqual(trinfo.comment, 'deactivate user')
        self.assertEqual(trinfo.comment_format, 'text/plain')
        return trinfo

    def test_change_state(self):
        user = self.user()
        iworkflowable = user.cw_adapt_to('IWorkflowable')
        iworkflowable.change_state('deactivated', comment=u'deactivate user')
        trinfo = self._test_manager_deactivate(user)
        self.assertEqual(trinfo.transition, None)

    def test_set_in_state_bad_wf(self):
        wf = add_wf(self, 'CWUser')
        s = wf.add_state(u'foo', initial=True)
        self.commit()
        with self.session.security_enabled(write=False):
            with self.assertRaises(ValidationError) as cm:
                self.session.execute('SET X in_state S WHERE X eid %(x)s, S eid %(s)s',
                                     {'x': self.user().eid, 's': s.eid})
            self.assertEqual(cm.exception.errors, {'in_state-subject': "state doesn't belong to entity's workflow. "
                                      "You may want to set a custom workflow for this entity first."})

    def test_fire_transition(self):
        user = self.user()
        iworkflowable = user.cw_adapt_to('IWorkflowable')
        iworkflowable.fire_transition('deactivate', comment=u'deactivate user')
        user.cw_clear_all_caches()
        self.assertEqual(iworkflowable.state, 'deactivated')
        self._test_manager_deactivate(user)
        trinfo = self._test_manager_deactivate(user)
        self.assertEqual(trinfo.transition.name, 'deactivate')

    def test_goback_transition(self):
        req = self.request()
        wf = req.user.cw_adapt_to('IWorkflowable').current_workflow
        asleep = wf.add_state('asleep')
        wf.add_transition('rest', (wf.state_by_name('activated'),
                                   wf.state_by_name('deactivated')),
                          asleep)
        wf.add_transition('wake up', asleep)
        user = self.create_user(req, 'stduser')
        iworkflowable = user.cw_adapt_to('IWorkflowable')
        iworkflowable.fire_transition('rest')
        self.commit()
        iworkflowable.fire_transition('wake up')
        self.commit()
        self.assertEqual(iworkflowable.state, 'activated')
        iworkflowable.fire_transition('deactivate')
        self.commit()
        iworkflowable.fire_transition('rest')
        self.commit()
        iworkflowable.fire_transition('wake up')
        self.commit()
        user.cw_clear_all_caches()
        self.assertEqual(iworkflowable.state, 'deactivated')

    # XXX test managers can change state without matching transition

    def _test_stduser_deactivate(self):
        ueid = self.member.eid
        req = self.request()
        self.create_user(req, 'tutu')
        cnx = self.login('tutu')
        req = self.request()
        iworkflowable = req.entity_from_eid(self.member.eid).cw_adapt_to('IWorkflowable')
        with self.assertRaises(ValidationError) as cm:
            iworkflowable.fire_transition('deactivate')
        self.assertEqual(cm.exception.errors, {'by_transition-subject': "transition may not be fired"})
        cnx.close()
        cnx = self.login('member')
        req = self.request()
        iworkflowable = req.entity_from_eid(self.member.eid).cw_adapt_to('IWorkflowable')
        iworkflowable.fire_transition('deactivate')
        cnx.commit()
        with self.assertRaises(ValidationError) as cm:
            iworkflowable.fire_transition('activate')
        self.assertEqual(cm.exception.errors, {'by_transition-subject': "transition may not be fired"})
        cnx.close()

    def test_fire_transition_owned_by(self):
        self.execute('INSERT RQLExpression X: X exprtype "ERQLExpression", '
                     'X expression "X owned_by U", T condition X '
                     'WHERE T name "deactivate"')
        self._test_stduser_deactivate()

    def test_fire_transition_has_update_perm(self):
        self.execute('INSERT RQLExpression X: X exprtype "ERQLExpression", '
                     'X expression "U has_update_permission X", T condition X '
                     'WHERE T name "deactivate"')
        self._test_stduser_deactivate()

    def test_swf_base(self):
        """subworkflow

        +-----------+  tr1   +-----------+
        | swfstate1 | ------>| swfstate2 |
        +-----------+        +-----------+
                  |  tr2  +-----------+
                  `------>| swfstate3 |
                          +-----------+

        main workflow

        +--------+  swftr1             +--------+
        | state1 | -------[swfstate2]->| state2 |
        +--------+     |               +--------+
                       |               +--------+
                       `-[swfstate3]-->| state3 |
                                       +--------+
        """
        # sub-workflow
        swf = add_wf(self, 'CWGroup', name='subworkflow')
        swfstate1 = swf.add_state(u'swfstate1', initial=True)
        swfstate2 = swf.add_state(u'swfstate2')
        swfstate3 = swf.add_state(u'swfstate3')
        tr1 = swf.add_transition(u'tr1', (swfstate1,), swfstate2)
        tr2 = swf.add_transition(u'tr2', (swfstate1,), swfstate3)
        # main workflow
        mwf = add_wf(self, 'CWGroup', name='main workflow', default=True)
        state1 = mwf.add_state(u'state1', initial=True)
        state2 = mwf.add_state(u'state2')
        state3 = mwf.add_state(u'state3')
        swftr1 = mwf.add_wftransition(u'swftr1', swf, state1,
                                      [(swfstate2, state2), (swfstate3, state3)])
        swf.cw_clear_all_caches()
        self.assertEqual(swftr1.destination(None).eid, swfstate1.eid)
        # workflows built, begin test
        group = self.request().create_entity('CWGroup', name=u'grp1')
        self.commit()
        iworkflowable = group.cw_adapt_to('IWorkflowable')
        self.assertEqual(iworkflowable.current_state.eid, state1.eid)
        self.assertEqual(iworkflowable.current_workflow.eid, mwf.eid)
        self.assertEqual(iworkflowable.main_workflow.eid, mwf.eid)
        self.assertEqual(iworkflowable.subworkflow_input_transition(), None)
        iworkflowable.fire_transition('swftr1', u'go')
        self.commit()
        group.cw_clear_all_caches()
        self.assertEqual(iworkflowable.current_state.eid, swfstate1.eid)
        self.assertEqual(iworkflowable.current_workflow.eid, swf.eid)
        self.assertEqual(iworkflowable.main_workflow.eid, mwf.eid)
        self.assertEqual(iworkflowable.subworkflow_input_transition().eid, swftr1.eid)
        iworkflowable.fire_transition('tr1', u'go')
        self.commit()
        group.cw_clear_all_caches()
        self.assertEqual(iworkflowable.current_state.eid, state2.eid)
        self.assertEqual(iworkflowable.current_workflow.eid, mwf.eid)
        self.assertEqual(iworkflowable.main_workflow.eid, mwf.eid)
        self.assertEqual(iworkflowable.subworkflow_input_transition(), None)
        # force back to swfstate1 is impossible since we can't any more find
        # subworkflow input transition
        with self.assertRaises(ValidationError) as cm:
            iworkflowable.change_state(swfstate1, u'gadget')
        self.assertEqual(cm.exception.errors, {'to_state-subject': "state doesn't belong to entity's workflow"})
        self.rollback()
        # force back to state1
        iworkflowable.change_state('state1', u'gadget')
        iworkflowable.fire_transition('swftr1', u'au')
        group.cw_clear_all_caches()
        iworkflowable.fire_transition('tr2', u'chapeau')
        self.commit()
        group.cw_clear_all_caches()
        self.assertEqual(iworkflowable.current_state.eid, state3.eid)
        self.assertEqual(iworkflowable.current_workflow.eid, mwf.eid)
        self.assertEqual(iworkflowable.main_workflow.eid, mwf.eid)
        self.assertListEqual(parse_hist(iworkflowable.workflow_history),
                              [('state1', 'swfstate1', 'swftr1', 'go'),
                               ('swfstate1', 'swfstate2', 'tr1', 'go'),
                               ('swfstate2', 'state2', 'swftr1', 'exiting from subworkflow subworkflow'),
                               ('state2', 'state1', None, 'gadget'),
                               ('state1', 'swfstate1', 'swftr1', 'au'),
                               ('swfstate1', 'swfstate3', 'tr2', 'chapeau'),
                               ('swfstate3', 'state3', 'swftr1', 'exiting from subworkflow subworkflow'),
                               ])

    def test_swf_exit_consistency(self):
        # sub-workflow
        swf = add_wf(self, 'CWGroup', name='subworkflow')
        swfstate1 = swf.add_state(u'swfstate1', initial=True)
        swfstate2 = swf.add_state(u'swfstate2')
        tr1 = swf.add_transition(u'tr1', (swfstate1,), swfstate2)
        # main workflow
        mwf = add_wf(self, 'CWGroup', name='main workflow', default=True)
        state1 = mwf.add_state(u'state1', initial=True)
        state2 = mwf.add_state(u'state2')
        state3 = mwf.add_state(u'state3')
        mwf.add_wftransition(u'swftr1', swf, state1,
                             [(swfstate2, state2), (swfstate2, state3)])
        with self.assertRaises(ValidationError) as cm:
            self.commit()
        self.assertEqual(cm.exception.errors, {'subworkflow_exit-subject': u"can't have multiple exits on the same state"})

    def test_swf_fire_in_a_row(self):
        # sub-workflow
        subwf = add_wf(self, 'CWGroup', name='subworkflow')
        xsigning = subwf.add_state('xsigning', initial=True)
        xaborted = subwf.add_state('xaborted')
        xsigned = subwf.add_state('xsigned')
        xabort = subwf.add_transition('xabort', (xsigning,), xaborted)
        xsign = subwf.add_transition('xsign', (xsigning,), xsigning)
        xcomplete = subwf.add_transition('xcomplete', (xsigning,), xsigned,
                                         type=u'auto')
        # main workflow
        twf = add_wf(self, 'CWGroup', name='mainwf', default=True)
        created    = twf.add_state(_('created'), initial=True)
        identified = twf.add_state(_('identified'))
        released   = twf.add_state(_('released'))
        closed   = twf.add_state(_('closed'))
        twf.add_wftransition(_('identify'), subwf, (created,),
                             [(xsigned, identified), (xaborted, created)])
        twf.add_wftransition(_('release'), subwf, (identified,),
                             [(xsigned, released), (xaborted, identified)])
        twf.add_wftransition(_('close'), subwf, (released,),
                             [(xsigned, closed), (xaborted, released)])
        self.commit()
        group = self.request().create_entity('CWGroup', name=u'grp1')
        self.commit()
        iworkflowable = group.cw_adapt_to('IWorkflowable')
        for trans in ('identify', 'release', 'close'):
            iworkflowable.fire_transition(trans)
            self.commit()


    def test_swf_magic_tr(self):
        # sub-workflow
        subwf = add_wf(self, 'CWGroup', name='subworkflow')
        xsigning = subwf.add_state('xsigning', initial=True)
        xaborted = subwf.add_state('xaborted')
        xsigned = subwf.add_state('xsigned')
        xabort = subwf.add_transition('xabort', (xsigning,), xaborted)
        xsign = subwf.add_transition('xsign', (xsigning,), xsigned)
        # main workflow
        twf = add_wf(self, 'CWGroup', name='mainwf', default=True)
        created    = twf.add_state(_('created'), initial=True)
        identified = twf.add_state(_('identified'))
        released   = twf.add_state(_('released'))
        twf.add_wftransition(_('identify'), subwf, created,
                             [(xaborted, None), (xsigned, identified)])
        twf.add_wftransition(_('release'), subwf, identified,
                             [(xaborted, None)])
        self.commit()
        group = self.request().create_entity('CWGroup', name=u'grp1')
        self.commit()
        iworkflowable = group.cw_adapt_to('IWorkflowable')
        for trans, nextstate in (('identify', 'xsigning'),
                                 ('xabort', 'created'),
                                 ('identify', 'xsigning'),
                                 ('xsign', 'identified'),
                                 ('release', 'xsigning'),
                                 ('xabort', 'identified')
                                 ):
            iworkflowable.fire_transition(trans)
            self.commit()
            group.cw_clear_all_caches()
            self.assertEqual(iworkflowable.state, nextstate)


class CustomWorkflowTC(CubicWebTC):

    def setup_database(self):
        req = self.request()
        self.member = self.create_user(req, 'member')

    def test_custom_wf_replace_state_no_history(self):
        """member in inital state with no previous history, state is simply
        redirected when changing workflow
        """
        wf = add_wf(self, 'CWUser')
        wf.add_state('asleep', initial=True)
        self.execute('SET X custom_workflow WF WHERE X eid %(x)s, WF eid %(wf)s',
                     {'wf': wf.eid, 'x': self.member.eid})
        self.member.cw_clear_all_caches()
        iworkflowable = self.member.cw_adapt_to('IWorkflowable')
        self.assertEqual(iworkflowable.state, 'activated')# no change before commit
        self.commit()
        self.member.cw_clear_all_caches()
        self.assertEqual(iworkflowable.current_workflow.eid, wf.eid)
        self.assertEqual(iworkflowable.state, 'asleep')
        self.assertEqual(iworkflowable.workflow_history, ())

    def test_custom_wf_replace_state_keep_history(self):
        """member in inital state with some history, state is redirected and
        state change is recorded to history
        """
        iworkflowable = self.member.cw_adapt_to('IWorkflowable')
        iworkflowable.fire_transition('deactivate')
        iworkflowable.fire_transition('activate')
        wf = add_wf(self, 'CWUser')
        wf.add_state('asleep', initial=True)
        self.execute('SET X custom_workflow WF WHERE X eid %(x)s, WF eid %(wf)s',
                     {'wf': wf.eid, 'x': self.member.eid})
        self.commit()
        self.member.cw_clear_all_caches()
        self.assertEqual(iworkflowable.current_workflow.eid, wf.eid)
        self.assertEqual(iworkflowable.state, 'asleep')
        self.assertEqual(parse_hist(iworkflowable.workflow_history),
                          [('activated', 'deactivated', 'deactivate', None),
                           ('deactivated', 'activated', 'activate', None),
                           ('activated', 'asleep', None, 'workflow changed to "CWUser"')])

    def test_custom_wf_no_initial_state(self):
        """try to set a custom workflow which has no initial state"""
        iworkflowable = self.member.cw_adapt_to('IWorkflowable')
        iworkflowable.fire_transition('deactivate')
        wf = add_wf(self, 'CWUser')
        wf.add_state('asleep')
        self.execute('SET X custom_workflow WF WHERE X eid %(x)s, WF eid %(wf)s',
                     {'wf': wf.eid, 'x': self.member.eid})
        with self.assertRaises(ValidationError) as cm:
            self.commit()
        self.assertEqual(cm.exception.errors, {'custom_workflow-subject': u'workflow has no initial state'})

    def test_custom_wf_bad_etype(self):
        """try to set a custom workflow which doesn't apply to entity type"""
        wf = add_wf(self, 'Company')
        wf.add_state('asleep', initial=True)
        self.execute('SET X custom_workflow WF WHERE X eid %(x)s, WF eid %(wf)s',
                     {'wf': wf.eid, 'x': self.member.eid})
        with self.assertRaises(ValidationError) as cm:
            self.commit()
        self.assertEqual(cm.exception.errors, {'custom_workflow-subject': u"workflow isn't a workflow for this type"})

    def test_del_custom_wf(self):
        """member in some state shared by the new workflow, nothing has to be
        done
        """
        iworkflowable = self.member.cw_adapt_to('IWorkflowable')
        iworkflowable.fire_transition('deactivate')
        wf = add_wf(self, 'CWUser')
        wf.add_state('asleep', initial=True)
        self.execute('SET X custom_workflow WF WHERE X eid %(x)s, WF eid %(wf)s',
                     {'wf': wf.eid, 'x': self.member.eid})
        self.commit()
        self.execute('DELETE X custom_workflow WF WHERE X eid %(x)s, WF eid %(wf)s',
                     {'wf': wf.eid, 'x': self.member.eid})
        self.member.cw_clear_all_caches()
        self.assertEqual(iworkflowable.state, 'asleep')# no change before commit
        self.commit()
        self.member.cw_clear_all_caches()
        self.assertEqual(iworkflowable.current_workflow.name, "default user workflow")
        self.assertEqual(iworkflowable.state, 'activated')
        self.assertEqual(parse_hist(iworkflowable.workflow_history),
                          [('activated', 'deactivated', 'deactivate', None),
                           ('deactivated', 'asleep', None, 'workflow changed to "CWUser"'),
                           ('asleep', 'activated', None, 'workflow changed to "default user workflow"'),])


class AutoTransitionTC(CubicWebTC):

    def setup_custom_wf(self):
        wf = add_wf(self, 'CWUser')
        asleep = wf.add_state('asleep', initial=True)
        dead = wf.add_state('dead')
        wf.add_transition('rest', asleep, asleep)
        wf.add_transition('sick', asleep, dead, type=u'auto',
                          conditions=({'expr': u'X surname "toto"',
                                       'mainvars': u'X'},))
        return wf

    def test_auto_transition_fired(self):
        wf = self.setup_custom_wf()
        req = self.request()
        user = self.create_user(req, 'member')
        iworkflowable = user.cw_adapt_to('IWorkflowable')
        self.execute('SET X custom_workflow WF WHERE X eid %(x)s, WF eid %(wf)s',
                     {'wf': wf.eid, 'x': user.eid})
        self.commit()
        user.cw_clear_all_caches()
        self.assertEqual(iworkflowable.state, 'asleep')
        self.assertEqual([t.name for t in iworkflowable.possible_transitions()],
                          ['rest'])
        iworkflowable.fire_transition('rest')
        self.commit()
        user.cw_clear_all_caches()
        self.assertEqual(iworkflowable.state, 'asleep')
        self.assertEqual([t.name for t in iworkflowable.possible_transitions()],
                          ['rest'])
        self.assertEqual(parse_hist(iworkflowable.workflow_history),
                          [('asleep', 'asleep', 'rest', None)])
        user.cw_set(surname=u'toto') # fulfill condition
        self.commit()
        iworkflowable.fire_transition('rest')
        self.commit()
        user.cw_clear_all_caches()
        self.assertEqual(iworkflowable.state, 'dead')
        self.assertEqual(parse_hist(iworkflowable.workflow_history),
                          [('asleep', 'asleep', 'rest', None),
                           ('asleep', 'asleep', 'rest', None),
                           ('asleep', 'dead', 'sick', None),])

    def test_auto_transition_custom_initial_state_fired(self):
        wf = self.setup_custom_wf()
        req = self.request()
        user = self.create_user(req, 'member', surname=u'toto')
        self.execute('SET X custom_workflow WF WHERE X eid %(x)s, WF eid %(wf)s',
                     {'wf': wf.eid, 'x': user.eid})
        self.commit()
        iworkflowable = user.cw_adapt_to('IWorkflowable')
        self.assertEqual(iworkflowable.state, 'dead')

    def test_auto_transition_initial_state_fired(self):
        wf = self.execute('Any WF WHERE ET default_workflow WF, '
                          'ET name %(et)s', {'et': 'CWUser'}).get_entity(0, 0)
        dead = wf.add_state('dead')
        wf.add_transition('sick', wf.state_by_name('activated'), dead,
                          type=u'auto', conditions=({'expr': u'X surname "toto"',
                                                     'mainvars': u'X'},))
        self.commit()
        req = self.request()
        user = self.create_user(req, 'member', surname=u'toto')
        self.commit()
        iworkflowable = user.cw_adapt_to('IWorkflowable')
        self.assertEqual(iworkflowable.state, 'dead')


class WorkflowHooksTC(CubicWebTC):

    def setUp(self):
        CubicWebTC.setUp(self)
        req = self.request()
        self.wf = req.user.cw_adapt_to('IWorkflowable').current_workflow
        self.s_activated = self.wf.state_by_name('activated').eid
        self.s_deactivated = self.wf.state_by_name('deactivated').eid
        self.s_dummy = self.wf.add_state(u'dummy').eid
        self.wf.add_transition(u'dummy', (self.s_deactivated,), self.s_dummy)
        ueid = self.create_user(req, 'stduser', commit=False).eid
        # test initial state is set
        rset = self.execute('Any N WHERE S name N, X in_state S, X eid %(x)s',
                            {'x' : ueid})
        self.assertFalse(rset, rset.rows)
        self.commit()
        initialstate = self.execute('Any N WHERE S name N, X in_state S, X eid %(x)s',
                                    {'x' : ueid})[0][0]
        self.assertEqual(initialstate, u'activated')
        # give access to users group on the user's wf transitions
        # so we can test wf enforcing on euser (managers don't have anymore this
        # enforcement
        self.execute('SET X require_group G '
                     'WHERE G name "users", X transition_of WF, WF eid %(wf)s',
                     {'wf': self.wf.eid})
        self.commit()

    # XXX currently, we've to rely on hooks to set initial state, or to use execute
    # def test_initial_state(self):
    #     cnx = self.login('stduser')
    #     cu = cnx.cursor()
    #     self.assertRaises(ValidationError, cu.execute,
    #                       'INSERT CWUser X: X login "badaboum", X upassword %(pwd)s, '
    #                       'X in_state S WHERE S name "deactivated"', {'pwd': 'oops'})
    #     cnx.close()
    #     # though managers can do whatever he want
    #     self.execute('INSERT CWUser X: X login "badaboum", X upassword %(pwd)s, '
    #                  'X in_state S, X in_group G WHERE S name "deactivated", G name "users"', {'pwd': 'oops'})
    #     self.commit()

    # test that the workflow is correctly enforced

    def _cleanup_msg(self, msg):
        """remove the variable part of one specific error message"""
        lmsg = msg.split()
        lmsg.pop(1)
        lmsg.pop()
        return ' '.join(lmsg)

    def test_transition_checking1(self):
        cnx = self.login('stduser')
        user = cnx.user(self.session)
        iworkflowable = user.cw_adapt_to('IWorkflowable')
        with self.assertRaises(ValidationError) as cm:
            iworkflowable.fire_transition('activate')
        self.assertEqual(self._cleanup_msg(cm.exception.errors['by_transition-subject']),
                          u"transition isn't allowed from")
        cnx.close()

    def test_transition_checking2(self):
        cnx = self.login('stduser')
        user = cnx.user(self.session)
        iworkflowable = user.cw_adapt_to('IWorkflowable')
        with self.assertRaises(ValidationError) as cm:
            iworkflowable.fire_transition('dummy')
        self.assertEqual(self._cleanup_msg(cm.exception.errors['by_transition-subject']),
                          u"transition isn't allowed from")
        cnx.close()

    def test_transition_checking3(self):
        with self.login('stduser') as cnx:
            session = self.session
            user = self.user()
            iworkflowable = user.cw_adapt_to('IWorkflowable')
            iworkflowable.fire_transition('deactivate')
            session.commit()
            session.set_cnxset()
            with self.assertRaises(ValidationError) as cm:
                iworkflowable.fire_transition('deactivate')
            self.assertEqual(self._cleanup_msg(cm.exception.errors['by_transition-subject']),
                                                u"transition isn't allowed from")
            session.rollback()
            session.set_cnxset()
            # get back now
            iworkflowable.fire_transition('activate')
            session.commit()


if __name__ == '__main__':
    from logilab.common.testlib import unittest_main
    unittest_main()
