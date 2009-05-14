

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

class multisource_crossed_rel(RelationDefinition):
    subject = ('Card', 'Note')
    object = 'Note'

class multisource_inlined_rel(RelationType):
    inlined = True
    cardinality = '?*'
    subject = ('Card', 'Note')
    object = ('Affaire', 'Note')


class see_also(RelationDefinition):
    subject = ('Bookmark', 'Note')
    object = ('Bookmark', 'Note')

_euser = import_schema('base').CWUser
_euser.__relations__[0].fulltextindexed = True
