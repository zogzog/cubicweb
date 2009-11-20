from cubicweb.devtools.testlib import CubicWebTC
from cubicweb import ValidationError

def add_wf(self, etype, name=None, default=False):
    if name is None:
        name = etype
    wf = self.execute('INSERT Workflow X: X name %(n)s', {'n': unicode(name)}).get_entity(0, 0)
    self.execute('SET WF workflow_of ET WHERE WF eid %(wf)s, ET name %(et)s',
                 {'wf': wf.eid, 'et': etype})
    if default:
        self.execute('SET ET default_workflow WF WHERE WF eid %(wf)s, ET name %(et)s',
                     {'wf': wf.eid, 'et': etype})
    return wf

def parse_hist(wfhist):
    return [(ti.previous_state.name, ti.new_state.name,
             ti.transition and ti.transition.name, ti.comment)
            for ti in wfhist]


class WorkflowBuildingTC(CubicWebTC):

    def test_wf_construction(self):
        wf = add_wf(self, 'Company')
        foo = wf.add_state(u'foo', initial=True)
        bar = wf.add_state(u'bar')
        self.assertEquals(wf.state_by_name('bar').eid, bar.eid)
        self.assertEquals(wf.state_by_name('barrr'), None)
        baz = wf.add_transition(u'baz', (foo,), bar, ('managers',))
        self.assertEquals(wf.transition_by_name('baz').eid, baz.eid)
        self.assertEquals(len(baz.require_group), 1)
        self.assertEquals(baz.require_group[0].name, 'managers')

    def test_duplicated_state(self):
        wf = add_wf(self, 'Company')
        wf.add_state(u'foo', initial=True)
        self.commit()
        wf.add_state(u'foo')
        ex = self.assertRaises(ValidationError, self.commit)
        # XXX enhance message
        self.assertEquals(ex.errors, {'state_of': 'unique constraint S name N, Y state_of O, Y name N failed'})
        # no pb if not in the same workflow
        wf2 = add_wf(self, 'Company')
        foo = wf2.add_state(u'foo', initial=True)
        self.commit()

    def test_duplicated_transition(self):
        wf = add_wf(self, 'Company')
        foo = wf.add_state(u'foo', initial=True)
        bar = wf.add_state(u'bar')
        wf.add_transition(u'baz', (foo,), bar, ('managers',))
        wf.add_transition(u'baz', (bar,), foo)
        ex = self.assertRaises(ValidationError, self.commit)
        # XXX enhance message
        self.assertEquals(ex.errors, {'transition_of': 'unique constraint S name N, Y transition_of O, Y name N failed'})


class WorkflowTC(CubicWebTC):

    def setup_database(self):
        rschema = self.schema['in_state']
        for x, y in rschema.iter_rdefs():
            self.assertEquals(rschema.rproperty(x, y, 'cardinality'), '1*')
        self.member = self.create_user('member')

    def test_workflow_base(self):
        e = self.create_user('toto')
        self.assertEquals(e.state, 'activated')
        e.change_state('deactivated', u'deactivate 1')
        self.commit()
        e.change_state('activated', u'activate 1')
        self.commit()
        e.change_state('deactivated', u'deactivate 2')
        self.commit()
        e.clear_related_cache('wf_info_for', 'object')
        self.assertEquals([tr.comment for tr in e.reverse_wf_info_for],
                          ['deactivate 1', 'activate 1', 'deactivate 2'])
        self.assertEquals(e.latest_trinfo().comment, 'deactivate 2')

    def test_possible_transitions(self):
        user = self.entity('CWUser X')
        trs = list(user.possible_transitions())
        self.assertEquals(len(trs), 1)
        self.assertEquals(trs[0].name, u'deactivate')
        self.assertEquals(trs[0].destination().name, u'deactivated')
        # test a std user get no possible transition
        cnx = self.login('member')
        # fetch the entity using the new session
        trs = list(cnx.user().possible_transitions())
        self.assertEquals(len(trs), 0)

    def _test_manager_deactivate(self, user):
        user.clear_related_cache('in_state', 'subject')
        self.assertEquals(len(user.in_state), 1)
        self.assertEquals(user.state, 'deactivated')
        trinfo = user.latest_trinfo()
        self.assertEquals(trinfo.previous_state.name, 'activated')
        self.assertEquals(trinfo.new_state.name, 'deactivated')
        self.assertEquals(trinfo.comment, 'deactivate user')
        self.assertEquals(trinfo.comment_format, 'text/plain')
        return trinfo

    def test_change_state(self):
        user = self.user()
        user.change_state('deactivated', comment=u'deactivate user')
        trinfo = self._test_manager_deactivate(user)
        self.assertEquals(trinfo.transition, None)

    def test_set_in_state_bad_wf(self):
        wf = add_wf(self, 'CWUser')
        s = wf.add_state(u'foo', initial=True)
        self.commit()
        ex = self.assertRaises(ValidationError, self.session.unsafe_execute,
                               'SET X in_state S WHERE X eid %(x)s, S eid %(s)s',
                               {'x': self.user().eid, 's': s.eid}, 'x')
        self.assertEquals(ex.errors, {'in_state': "state doesn't belong to entity's workflow. "
                                      "You may want to set a custom workflow for this entity first."})

    def test_fire_transition(self):
        user = self.user()
        user.fire_transition('deactivate', comment=u'deactivate user')
        user.clear_all_caches()
        self.assertEquals(user.state, 'deactivated')
        self._test_manager_deactivate(user)
        trinfo = self._test_manager_deactivate(user)
        self.assertEquals(trinfo.transition.name, 'deactivate')

    # XXX test managers can change state without matching transition

    def _test_stduser_deactivate(self):
        ueid = self.member.eid
        self.create_user('tutu')
        cnx = self.login('tutu')
        req = self.request()
        member = req.entity_from_eid(self.member.eid)
        ex = self.assertRaises(ValidationError,
                               member.fire_transition, 'deactivate')
        self.assertEquals(ex.errors, {'by_transition': "transition may not be fired"})
        cnx.close()
        cnx = self.login('member')
        req = self.request()
        member = req.entity_from_eid(self.member.eid)
        member.fire_transition('deactivate')
        cnx.commit()
        ex = self.assertRaises(ValidationError,
                               member.fire_transition, 'activate')
        self.assertEquals(ex.errors, {'by_transition': "transition may not be fired"})

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
        self.assertEquals(swftr1.destination().eid, swfstate1.eid)
        # workflows built, begin test
        self.group = self.add_entity('CWGroup', name=u'grp1')
        self.commit()
        self.assertEquals(self.group.current_state.eid, state1.eid)
        self.assertEquals(self.group.current_workflow.eid, mwf.eid)
        self.assertEquals(self.group.main_workflow.eid, mwf.eid)
        self.assertEquals(self.group.subworkflow_input_transition(), None)
        self.group.fire_transition('swftr1', u'go')
        self.commit()
        self.group.clear_all_caches()
        self.assertEquals(self.group.current_state.eid, swfstate1.eid)
        self.assertEquals(self.group.current_workflow.eid, swf.eid)
        self.assertEquals(self.group.main_workflow.eid, mwf.eid)
        self.assertEquals(self.group.subworkflow_input_transition().eid, swftr1.eid)
        self.group.fire_transition('tr1', u'go')
        self.commit()
        self.group.clear_all_caches()
        self.assertEquals(self.group.current_state.eid, state2.eid)
        self.assertEquals(self.group.current_workflow.eid, mwf.eid)
        self.assertEquals(self.group.main_workflow.eid, mwf.eid)
        self.assertEquals(self.group.subworkflow_input_transition(), None)
        # force back to swfstate1 is impossible since we can't any more find
        # subworkflow input transition
        ex = self.assertRaises(ValidationError,
                               self.group.change_state, swfstate1, u'gadget')
        self.assertEquals(ex.errors, {'to_state': "state doesn't belong to entity's current workflow"})
        self.rollback()
        # force back to state1
        self.group.change_state('state1', u'gadget')
        self.group.fire_transition('swftr1', u'au')
        self.group.clear_all_caches()
        self.group.fire_transition('tr2', u'chapeau')
        self.commit()
        self.group.clear_all_caches()
        self.assertEquals(self.group.current_state.eid, state3.eid)
        self.assertEquals(self.group.current_workflow.eid, mwf.eid)
        self.assertEquals(self.group.main_workflow.eid, mwf.eid)
        self.assertListEquals(parse_hist(self.group.workflow_history),
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
        ex = self.assertRaises(ValidationError, self.commit)
        self.assertEquals(ex.errors, {'subworkflow_exit': u"can't have multiple exits on the same state"})

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
        group = self.add_entity('CWGroup', name=u'grp1')
        self.commit()
        for trans in ('identify', 'release', 'close'):
            group.fire_transition(trans)
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
        group = self.add_entity('CWGroup', name=u'grp1')
        self.commit()
        for trans, nextstate in (('identify', 'xsigning'),
                                 ('xabort', 'created'),
                                 ('identify', 'xsigning'),
                                 ('xsign', 'identified'),
                                 ('release', 'xsigning'),
                                 ('xabort', 'identified')
                                 ):
            group.fire_transition(trans)
            self.commit()
            group.clear_all_caches()
            self.assertEquals(group.state, nextstate)


class CustomWorkflowTC(CubicWebTC):

    def setup_database(self):
        self.member = self.create_user('member')

    def test_custom_wf_replace_state_no_history(self):
        """member in inital state with no previous history, state is simply
        redirected when changing workflow
        """
        wf = add_wf(self, 'CWUser')
        wf.add_state('asleep', initial=True)
        self.execute('SET X custom_workflow WF WHERE X eid %(x)s, WF eid %(wf)s',
                     {'wf': wf.eid, 'x': self.member.eid})
        self.member.clear_all_caches()
        self.assertEquals(self.member.state, 'activated')# no change before commit
        self.commit()
        self.member.clear_all_caches()
        self.assertEquals(self.member.current_workflow.eid, wf.eid)
        self.assertEquals(self.member.state, 'asleep')
        self.assertEquals(self.member.workflow_history, ())

    def test_custom_wf_replace_state_keep_history(self):
        """member in inital state with some history, state is redirected and
        state change is recorded to history
        """
        self.member.fire_transition('deactivate')
        self.member.fire_transition('activate')
        wf = add_wf(self, 'CWUser')
        wf.add_state('asleep', initial=True)
        self.execute('SET X custom_workflow WF WHERE X eid %(x)s, WF eid %(wf)s',
                     {'wf': wf.eid, 'x': self.member.eid})
        self.commit()
        self.member.clear_all_caches()
        self.assertEquals(self.member.current_workflow.eid, wf.eid)
        self.assertEquals(self.member.state, 'asleep')
        self.assertEquals(parse_hist(self.member.workflow_history),
                          [('activated', 'deactivated', 'deactivate', None),
                           ('deactivated', 'activated', 'activate', None),
                           ('activated', 'asleep', None, 'workflow changed to "CWUser"')])

    def test_custom_wf_no_initial_state(self):
        """try to set a custom workflow which has no initial state"""
        self.member.fire_transition('deactivate')
        wf = add_wf(self, 'CWUser')
        wf.add_state('asleep')
        self.execute('SET X custom_workflow WF WHERE X eid %(x)s, WF eid %(wf)s',
                     {'wf': wf.eid, 'x': self.member.eid})
        ex = self.assertRaises(ValidationError, self.commit)
        self.assertEquals(ex.errors, {'custom_workflow': u'workflow has no initial state'})

    def test_custom_wf_bad_etype(self):
        """try to set a custom workflow which doesn't apply to entity type"""
        wf = add_wf(self, 'Company')
        wf.add_state('asleep', initial=True)
        self.execute('SET X custom_workflow WF WHERE X eid %(x)s, WF eid %(wf)s',
                     {'wf': wf.eid, 'x': self.member.eid})
        ex = self.assertRaises(ValidationError, self.commit)
        self.assertEquals(ex.errors, {'custom_workflow': 'constraint S is ET, O workflow_of ET failed'})

    def test_del_custom_wf(self):
        """member in some state shared by the new workflow, nothing has to be
        done
        """
        self.member.fire_transition('deactivate')
        wf = add_wf(self, 'CWUser')
        wf.add_state('asleep', initial=True)
        self.execute('SET X custom_workflow WF WHERE X eid %(x)s, WF eid %(wf)s',
                     {'wf': wf.eid, 'x': self.member.eid})
        self.commit()
        self.execute('DELETE X custom_workflow WF WHERE X eid %(x)s, WF eid %(wf)s',
                     {'wf': wf.eid, 'x': self.member.eid})
        self.member.clear_all_caches()
        self.assertEquals(self.member.state, 'asleep')# no change before commit
        self.commit()
        self.member.clear_all_caches()
        self.assertEquals(self.member.current_workflow.name, "default user workflow")
        self.assertEquals(self.member.state, 'activated')
        self.assertEquals(parse_hist(self.member.workflow_history),
                          [('activated', 'deactivated', 'deactivate', None),
                           ('deactivated', 'asleep', None, 'workflow changed to "CWUser"'),
                           ('asleep', 'activated', None, 'workflow changed to "default user workflow"'),])


class AutoTransitionTC(CubicWebTC):

    def setup_database(self):
        self.wf = add_wf(self, 'CWUser')
        asleep = self.wf.add_state('asleep', initial=True)
        dead = self.wf.add_state('dead')
        self.wf.add_transition('rest', asleep, asleep)
        self.wf.add_transition('sick', asleep, dead, type=u'auto',
                               conditions=({'expr': u'U surname "toto"',
                                            'mainvars': u'U'},))

    def test_auto_transition_fired(self):
        user = self.create_user('member')
        self.execute('SET X custom_workflow WF WHERE X eid %(x)s, WF eid %(wf)s',
                     {'wf': self.wf.eid, 'x': user.eid})
        self.commit()
        user.clear_all_caches()
        self.assertEquals(user.state, 'asleep')
        self.assertEquals([t.name for t in user.possible_transitions()],
                          ['rest'])
        user.fire_transition('rest')
        self.commit()
        user.clear_all_caches()
        self.assertEquals(user.state, 'asleep')
        self.assertEquals([t.name for t in user.possible_transitions()],
                          ['rest'])
        self.assertEquals(parse_hist(user.workflow_history),
                          [('asleep', 'asleep', 'rest', None)])
        self.request().user.set_attributes(surname=u'toto') # fulfill condition
        self.commit()
        user.fire_transition('rest')
        self.commit()
        user.clear_all_caches()
        self.assertEquals(user.state, 'dead')
        self.assertEquals(parse_hist(user.workflow_history),
                          [('asleep', 'asleep', 'rest', None),
                           ('asleep', 'asleep', 'rest', None),
                           ('asleep', 'dead', 'sick', None),])


class WorkflowHooksTC(CubicWebTC):

    def setUp(self):
        CubicWebTC.setUp(self)
        self.wf = self.session.user.current_workflow
        self.session.set_pool()
        self.s_activated = self.wf.state_by_name('activated').eid
        self.s_deactivated = self.wf.state_by_name('deactivated').eid
        self.s_dummy = self.wf.add_state(u'dummy').eid
        self.wf.add_transition(u'dummy', (self.s_deactivated,), self.s_dummy)
        ueid = self.create_user('stduser', commit=False).eid
        # test initial state is set
        rset = self.execute('Any N WHERE S name N, X in_state S, X eid %(x)s',
                            {'x' : ueid})
        self.failIf(rset, rset.rows)
        self.commit()
        initialstate = self.execute('Any N WHERE S name N, X in_state S, X eid %(x)s',
                                    {'x' : ueid})[0][0]
        self.assertEquals(initialstate, u'activated')
        # give access to users group on the user's wf transitions
        # so we can test wf enforcing on euser (managers don't have anymore this
        # enforcement
        self.execute('SET X require_group G '
                     'WHERE G name "users", X transition_of WF, WF eid %(wf)s',
                     {'wf': self.wf.eid})
        self.commit()

    # XXX currently, we've to rely on hooks to set initial state, or to use unsafe_execute
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
        ex = self.assertRaises(ValidationError,
                               user.fire_transition, 'activate')
        self.assertEquals(self._cleanup_msg(ex.errors['by_transition']),
                          u"transition isn't allowed from")
        cnx.close()

    def test_transition_checking2(self):
        cnx = self.login('stduser')
        user = cnx.user(self.session)
        ex = self.assertRaises(ValidationError,
                               user.fire_transition, 'dummy')
        self.assertEquals(self._cleanup_msg(ex.errors['by_transition']),
                          u"transition isn't allowed from")
        cnx.close()

    def test_transition_checking3(self):
        cnx = self.login('stduser')
        session = self.session
        user = cnx.user(session)
        user.fire_transition('deactivate')
        cnx.commit()
        session.set_pool()
        ex = self.assertRaises(ValidationError,
                               user.fire_transition, 'deactivate')
        self.assertEquals(self._cleanup_msg(ex.errors['by_transition']),
                                            u"transition isn't allowed from")
        # get back now
        user.fire_transition('activate')
        cnx.commit()
        cnx.close()


if __name__ == '__main__':
    from logilab.common.testlib import unittest_main
    unittest_main()
