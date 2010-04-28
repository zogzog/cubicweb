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
"""cubicweb post creation script, set note's workflow

"""

wf = add_workflow(u'note workflow', 'Note')
todo = wf.add_state(u'todo', initial=True)
done = wf.add_state(u'done')
wf.add_transition(u'redoit', done, todo)
wf.add_transition(u'markasdone', todo, done)
commit()

wf = add_workflow(u'affaire workflow', 'Affaire')
pitetre = wf.add_state(u'pitetre', initial=True)
encours = wf.add_state(u'en cours')
finie = wf.add_state(u'finie')
bennon = wf.add_state(u'ben non')
wf.add_transition(u'abort', pitetre, bennon)
wf.add_transition(u'start', pitetre, encours)
wf.add_transition(u'end', encours, finie)
commit()

