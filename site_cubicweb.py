from logilab.common.configuration import REQUIRED

import cubicweb.schema

cubicweb.schema.INTERNAL_TYPES.add('CWSession')

options = (
    ('pyramid-session-secret', {
        'type': 'string',
        'default': REQUIRED,
        'help': 'Secret phrase to sign the session cookie',
        'group': 'pyramid',
        'level': 3
    }),
)
