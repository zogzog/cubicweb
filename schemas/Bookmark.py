
class Bookmark(MetaUserEntityType):
    """define an entity type, used to build the application schema"""
    title = String(required=True, maxsize=128)
    path  = String(maxsize=512, required=True,
                   description=_("relative url of the bookmarked page"))
    
    bookmarked_by = SubjectRelation('EUser',
                                    description=_("users using this bookmark"))
    

class bookmarked_by(MetaUserRelationType):
    permissions = {'read':   ('managers', 'users', 'guests',),
                   # test user in users group to avoid granting permission to anonymous user
                   'add':    ('managers', RRQLExpression('O identity U, U in_group G, G name "users"')),
                   'delete': ('managers', RRQLExpression('O identity U, U in_group G, G name "users"')),
                   }
