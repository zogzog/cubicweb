

class test(AttributeRelationType):
    permissions = {'read': ('managers', 'users', 'guests'),
                   'delete': ('managers',),
                   'add': ('managers',)}

class fiche(RelationType):
    inlined = True
    subject = 'Personne'
    object = 'Card'
    cardinality = '??'

class multisource_rel(RelationDefinition):
    subject = ('Card', 'Note')
    object = 'Note'


class see_also(RelationDefinition):
    subject = ('Bookmark', 'Note')
    object = ('Bookmark', 'Note')
