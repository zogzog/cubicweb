"""some utilities to define schema permissions

:organization: Logilab
:copyright: 2008-2010 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

from rql.utils import quote
from cubicweb.schema import RO_REL_PERMS, RO_ATTR_PERMS, \
     PUB_SYSTEM_ENTITY_PERMS, PUB_SYSTEM_REL_PERMS, \
     ERQLExpression, RRQLExpression

# permissions for "meta" entity type (readable by anyone, can only be
# added/deleted by managers)
META_ETYPE_PERMS = PUB_SYSTEM_ENTITY_PERMS # XXX deprecates
# permissions for "meta" relation type (readable by anyone, can only be
# added/deleted by managers)
META_RTYPE_PERMS = PUB_SYSTEM_REL_PERMS # XXX deprecates
# permissions for relation type that should only set by hooks using unsafe
# execute, readable by anyone
HOOKS_RTYPE_PERMS = RO_REL_PERMS # XXX deprecates

def _perm(names):
    if isinstance(names, (list, tuple)):
        if len(names) == 1:
            names = quote(names[0])
        else:
            names = 'IN (%s)' % (','.join(quote(name) for name in names))
    else:
        names = quote(names)
    #return u' require_permission P, P name %s, U in_group G, P require_group G' % names
    return u' require_permission P, P name %s, U has_group_permission P' % names


def xperm(*names):
    return 'X' + _perm(names)

def xexpr(*names):
    return ERQLExpression(xperm(*names))

def xrexpr(relation, *names):
    return ERQLExpression('X %s Y, Y %s' % (relation, _perm(names)))

def xorexpr(relation, etype, *names):
    return ERQLExpression('Y %s X, X is %s, Y %s' % (relation, etype, _perm(names)))


def sexpr(*names):
    return RRQLExpression('S' + _perm(names), 'S')

def restricted_sexpr(restriction, *names):
    rql = '%s, %s' % (restriction, 'S' + _perm(names))
    return RRQLExpression(rql, 'S')

def restricted_oexpr(restriction, *names):
    rql = '%s, %s' % (restriction, 'O' + _perm(names))
    return RRQLExpression(rql, 'O')

def oexpr(*names):
    return RRQLExpression('O' + _perm(names), 'O')


# def supdate_perm():
#     return RRQLExpression('U has_update_permission S', 'S')

# def oupdate_perm():
#     return RRQLExpression('U has_update_permission O', 'O')

def relxperm(rel, role, *names):
    assert role in ('subject', 'object')
    if role == 'subject':
        zxrel = ', X %s Z' % rel
    else:
        zxrel = ', Z %s X' % rel
    return 'Z' + _perm(names) + zxrel

def relxexpr(rel, role, *names):
    return ERQLExpression(relxperm(rel, role, *names))
