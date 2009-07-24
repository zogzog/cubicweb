# permissions for "meta" entity type (readable by anyone, can only be
# added/deleted by managers)
META_ETYPE_PERMS = {
    'read':   ('managers', 'users', 'guests',),
    'add':    ('managers',),
    'delete': ('managers',),
    'update': ('managers', 'owners',),
    }

# permissions for "meta" relation type (readable by anyone, can only be
# added/deleted by managers)
META_RTYPE_PERMS = {
    'read':   ('managers', 'users', 'guests',),
    'add':    ('managers',),
    'delete': ('managers',),
    }

# permissions for relation type that should only set by hooks using unsafe
# execute, readable by anyone
HOOKS_RTYPE_PERMS = {
    'read':   ('managers', 'users', 'guests',),
    'add':    (),
    'delete': (),
    }
