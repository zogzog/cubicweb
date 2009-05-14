"""some utility functions for datastore initialization.

:organization: Logilab
:copyright: 2008-2009 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

from google.appengine.api.datastore import Key, Entity, Put, Get, Query
from google.appengine.api import datastore_errors

_GROUP_CACHE = {} # XXX use memcache

def _get_group(groupname):
    try:
        return _GROUP_CACHE[groupname]
    except KeyError:
        key = Key.from_path('CWGroup', 'key_' + groupname, parent=None)
        try:
            group = Get(key)
        except datastore_errors.EntityNotFoundError:
            raise Exception('can\'t find required group %s, is your application '
                            'correctly initialized (eg did you run the '
                            'initialization script) ?' % groupname)
        _GROUP_CACHE[groupname] = group
        return group


def create_user(login, password, groups):
    """create a cubicweb user"""
    from cubicweb.server.utils import crypt_password
    user = Entity('CWUser', name=login)
    user['s_login'] = unicode(login)
    user['s_upassword'] = crypt_password(password)
    set_user_groups(user, groups)
    Put(user)
    return user

def create_groups():
    """create initial cubicweb groups"""
    for groupname in ('managers', 'users', 'guests'):
        group = Entity('CWGroup', name='key_' + groupname)
        group['s_name'] = unicode(groupname)
        Put(group)
        _GROUP_CACHE[groupname] = group

def set_user_groups(user, groups):
    """set user in the given groups (as string). The given user entity
    (datastore.Entity) is not putted back to the repository, this is the caller
    responsability.
    """
    groups = [_get_group(g) for g in groups]
    user['s_in_group'] = [g.key() for g in groups] or None
    for group in groups:
        try:
            group['o_in_group'].append(user.key())
        except (KeyError, AttributeError):
            group['o_in_group'] = [user.key()]
        Put(group)

def init_relations(gaeentity, eschema):
    """set None for every subject relations which is not yet defined"""
    for rschema in eschema.subject_relations():
        if rschema in ('identity', 'has_text'):
            continue
        dsrelation = 's_' + rschema.type
        if not dsrelation in gaeentity:
            gaeentity[dsrelation] = None
    for rschema in eschema.object_relations():
        if rschema == 'identity':
            continue
        dsrelation = 'o_' + rschema.type
        if not dsrelation in gaeentity:
            gaeentity[dsrelation] = None

def fix_entities(schema):
    for etype in ('CWUser', 'CWGroup'):
        eschema = schema.eschema(etype)
        for gaeentity in Query(etype).Run():
            init_relations(gaeentity, eschema)
            # XXX o_is on CWEType entity
            gaeentity['s_is'] = Key.from_path('CWEType', 'key_' + etype, parent=None)
            Put(gaeentity)

def init_persistent_schema(ssession, schema):
    execute = ssession.unsafe_execute
    rql = ('INSERT CWEType X: X name %(name)s, X description %(descr)s,'
           'X final FALSE, X meta %(meta)s')
    eschema = schema.eschema('CWEType')
    execute(rql, {'name': u'CWEType', 'descr': unicode(eschema.description),
                  'meta': eschema.meta})
    for eschema in schema.entities():
        if eschema.is_final() or eschema == 'CWEType':
            continue
        execute(rql, {'name': unicode(eschema), 'meta': eschema.meta,
                      'descr': unicode(eschema.description)})

def insert_versions(ssession, config):
    execute = ssession.unsafe_execute
    # insert versions
    execute('INSERT CWProperty X: X pkey %(pk)s, X value%(v)s',
            {'pk': u'system.version.cubicweb',
             'v': unicode(config.cubicweb_version())})
    for cube in config.cubes():
        execute('INSERT CWProperty X: X pkey %(pk)s, X value%(v)s',
                {'pk': u'system.version.%s' % cube,
                 'v': unicode(config.cube_version(cube))})
