class Salesterm(EntityType):
    described_by_test = SubjectRelation('File', cardinality='1*', composite='subject')
    amount = Int(constraints=[IntervalBoundConstraint(0, 100)])

class tags(RelationDefinition):
    subject = 'Tag'
    object = ('BlogEntry', 'CWUser')

class checked_by(RelationType):
    subject = 'BlogEntry'
    object = 'CWUser'
    cardinality = '?*'
    permissions = {
        'add': ('managers',),
        'read': ('managers', 'users'),
        'delete': ('managers',),
        }
