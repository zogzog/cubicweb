"""cubicweb post creation script, set note's workflow"""

todoeid = add_state(u'todo', 'Note', initial=True)
doneeid = add_state(u'done', 'Note')
add_transition(u'redoit', 'Note', (doneeid,), todoeid)
add_transition(u'markasdone', 'Note', (todoeid,), doneeid)
checkpoint()

pitetre = add_state(u'pitetre', 'Affaire', initial=True)
encours = add_state(u'en cours', 'Affaire')
finie = add_state(u'finie', 'Affaire')
bennon = add_state(u'ben non', 'Affaire')
add_transition(u'abort', 'Affaire', (pitetre,), bennon)
add_transition(u'start', 'Affaire', (pitetre,), encours)
add_transition(u'end', 'Affaire', (encours,), finie)
checkpoint()

