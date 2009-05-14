class Note(EntityType):

    permissions = {'read':   ('managers', 'users', 'guests',),
                   'update': ('managers', 'owners',),
                   'delete': ('managers', ),
                   'add':    ('managers',
                              ERQLExpression('X ecrit_part PE, U in_group G, '
                                             'PE require_permission P, P name "add_note", '
                                             'P require_group G'),)}

    date = Datetime()
    type = String(maxsize=1)
    whatever = Int()
    mydate = Date(default='TODAY')
    para = String(maxsize=512)
    shortpara = String(maxsize=64)
    ecrit_par = SubjectRelation('Personne', constraints=[RQLConstraint('S concerne A, O concerne A')])

class ecrit_par(RelationType):
    permissions = {'read':   ('managers', 'users', 'guests',),
                   'delete': ('managers', ),
                   'add':    ('managers',
                              RRQLExpression('O require_permission P, P name "add_note", '
                                             'U in_group G, P require_group G'),)
                   }
    inlined = True
