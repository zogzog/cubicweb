from logilab.common.testlib import unittest_main
from cubicweb.devtools.apptest import EnvBasedTC

class WorkfloableMixInTC(EnvBasedTC):
    def test_wf_state(self):
        s = self.add_entity('State', name=u'activated')
        self.execute('SET X state_of ET WHERE ET name "Bookmark", X eid %(x)s',
                     {'x': s.eid})
        es = self.user().wf_state('activated')
        self.assertEquals(es.state_of[0].name, 'CWUser')

    def test_wf_transition(self):
        t = self.add_entity('Transition', name=u'deactivate')
        self.execute('SET X transition_of ET WHERE ET name "Bookmark", X eid %(x)s',
                     {'x': t.eid})
        et = self.user().wf_transition('deactivate')
        self.assertEquals(et.transition_of[0].name, 'CWUser')

    def test_change_state(self):
        user = self.user()
        user.change_state(user.wf_state('deactivated').eid)
        self.assertEquals(user.state, 'deactivated')

if __name__ == '__main__':
    unittest_main()
