class Salesterm(EntityType):
    described_by_test = SubjectRelation('File', cardinality='1*', composite='subject')
    amount = Int(constraints=[IntervalBoundConstraint(0, 100)])
    
class tags(RelationDefinition):
    subject = 'Tag'
    object = ('BlogEntry', 'EUser')

class checked_by(RelationType):
    subject = 'BlogEntry'
    object = 'EUser'
    cardinality = '?*'
    permissions = {
        'add': ('managers',),
        'read': ('managers', 'users'),
        'delete': ('managers',),
        }
