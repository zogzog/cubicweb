from cubicweb.schema import format_constraint

class Affaire(EntityType):
    permissions = {
        'read':   ('managers', 
                   ERQLExpression('X owned_by U'), ERQLExpression('X concerne S?, S owned_by U')),
        'add':    ('managers', ERQLExpression('X concerne S, S owned_by U')),
        'update': ('managers', 'owners', ERQLExpression('X in_state S, S name in ("pitetre", "en cours")')),
        'delete': ('managers', 'owners', ERQLExpression('X concerne S, S owned_by U')),
        }
    
    ref = String(fulltextindexed=True, indexed=True,
                 constraints=[SizeConstraint(16)])
    sujet = String(fulltextindexed=True,
                   constraints=[SizeConstraint(256)])
    in_state = SubjectRelation('State', cardinality='1*',
                               constraints=[RQLConstraint('O state_of ET, ET name "Affaire"')],
                               description=_('account state'))
    descr_format = String(meta=True, internationalizable=True,
                                default='text/rest', constraints=[format_constraint])
    descr = String(fulltextindexed=True,
                   description=_('more detailed description'))

    duration = Int()
    invoiced = Int()
        
    wf_info_for = ObjectRelation('TrInfo', cardinality='1*', composite='object')
    depends_on = SubjectRelation('Affaire')
    require_permission = SubjectRelation('EPermission')
    
class concerne(RelationType):
    permissions = {
        'read':   ('managers', 'users', 'guests'),
        'add':    ('managers', RRQLExpression('U has_update_permission S')),
        'delete': ('managers', RRQLExpression('O owned_by U')),
        }
    

