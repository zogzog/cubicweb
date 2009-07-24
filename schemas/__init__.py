
META_ETYPE_PERMS = {
    'read':   ('managers', 'users', 'guests',),
    'add':    ('managers',),
    'delete': ('managers',),
    'update': ('managers', 'owners',),
    }

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
