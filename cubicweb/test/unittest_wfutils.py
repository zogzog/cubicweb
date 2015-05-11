# copyright 2017 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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

import copy

from cubicweb.devtools import testlib
from cubicweb.wfutils import setup_workflow


class TestWFUtils(testlib.CubicWebTC):

    defs = {
        'group': {
            'etypes': 'CWGroup',
            'default': True,
            'initial_state': u'draft',
            'states': [u'draft', u'published'],
            'transitions': {
                u'publish': {
                    'fromstates': u'draft',
                    'tostate': u'published',
                    'requiredgroups': u'managers'
                }
            }
        }
    }

    def test_create_workflow(self):
        with self.admin_access.cnx() as cnx:
            wf = setup_workflow(cnx, 'group', self.defs['group'])
            self.assertEqual(wf.name, 'group')
            self.assertEqual(wf.initial.name, u'draft')

            draft = wf.state_by_name(u'draft')
            self.assertIsNotNone(draft)

            published = wf.state_by_name(u'published')
            self.assertIsNotNone(published)

            publish = wf.transition_by_name(u'publish')
            self.assertIsNotNone(publish)

            self.assertEqual(publish.destination_state, (published, ))
            self.assertEqual(draft.allowed_transition, (publish, ))

            self.assertEqual(
                {g.name for g in publish.require_group},
                {'managers'})

    def test_update(self):
        with self.admin_access.cnx() as cnx:
            wf = setup_workflow(cnx, 'group', self.defs['group'])
            eid = wf.eid

        with self.admin_access.cnx() as cnx:
            wfdef = copy.deepcopy(self.defs['group'])
            wfdef['states'].append('new')
            wfdef['initial_state'] = 'new'
            wfdef['transitions'][u'publish']['fromstates'] = ('draft', 'new')
            wfdef['transitions'][u'publish']['requiredgroups'] = (
                u'managers', u'users')
            wfdef['transitions'][u'todraft'] = {
                'fromstates': ('new', 'published'),
                'tostate': 'draft',
            }

            wf = setup_workflow(cnx, 'group', wfdef)
            self.assertEqual(wf.eid, eid)
            self.assertEqual(wf.name, 'group')
            self.assertEqual(wf.initial.name, u'new')

            new = wf.state_by_name(u'new')
            self.assertIsNotNone(new)

            draft = wf.state_by_name(u'draft')
            self.assertIsNotNone(draft)

            published = wf.state_by_name(u'published')
            self.assertIsNotNone(published)

            publish = wf.transition_by_name(u'publish')
            self.assertIsNotNone(publish)

            todraft = wf.transition_by_name(u'todraft')
            self.assertIsNotNone(todraft)

            self.assertEqual(
                {g.name for g in publish.require_group},
                {'managers', 'users'})

            self.assertEqual(publish.destination_state, (published, ))
            self.assertEqual(draft.allowed_transition, (publish, ))
            self.assertEqual(todraft.destination_state, (draft, ))
            self.assertEqual(published.allowed_transition, (todraft, ))
            self.assertCountEqual(new.allowed_transition, (publish, todraft))


if __name__ == '__main__':
    import unittest
    unittest.main()
