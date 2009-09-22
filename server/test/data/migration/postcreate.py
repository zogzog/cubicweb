"""cubicweb post creation script, set note's workflow

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""

wf = add_workflow(u'note workflow', 'Note')
todo = wf.add_state(u'todo', initial=True)
done = wf.add_state(u'done')
wf.add_transition(u'redoit', done, todo)
wf.add_transition(u'markasdone', todo, done)
checkpoint()

wf = add_workflow(u'affaire workflow', 'Affaire')
pitetre = wf.add_state(u'pitetre', initial=True)
encours = wf.add_state(u'en cours')
finie = wf.add_state(u'finie')
bennon = wf.add_state(u'ben non')
wf.add_transition(u'abort', pitetre, bennon)
wf.add_transition(u'start', pitetre, encours)
wf.add_transition(u'end', encours, finie)
checkpoint()

