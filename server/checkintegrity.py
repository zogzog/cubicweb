"""Check integrity of a CubicWeb repository. Hum actually only the system database
is checked.

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

import sys
from datetime import datetime

from logilab.common.shellutils import ProgressBar

from cubicweb.server.sqlutils import SQL_PREFIX

def has_eid(sqlcursor, eid, eids):
    """return true if the eid is a valid eid"""
    if eids.has_key(eid):
        return eids[eid]
    sqlcursor.execute('SELECT type, source FROM entities WHERE eid=%s' % eid)
    try:
        etype, source = sqlcursor.fetchone()
    except:
        eids[eid] = False
        return False
    if source and source != 'system':
        # XXX what to do...
        eids[eid] = True
        return True
    sqlcursor.execute('SELECT * FROM %s%s WHERE %seid=%s' % (SQL_PREFIX, etype,
                                                             SQL_PREFIX, eid))
    result = sqlcursor.fetchall()
    if len(result) == 0:
        eids[eid] = False
        return False
    elif len(result) > 1:
        msg = '  More than one entity with eid %s exists in source !'
        print >> sys.stderr, msg % eid
        print >> sys.stderr, '  WARNING : Unable to fix this, do it yourself !'
    eids[eid] = True
    return True

# XXX move to yams?
def etype_fti_containers(eschema, _done=None):
    if _done is None:
        _done = set()
    _done.add(eschema)
    containers = tuple(eschema.fulltext_containers())
    if containers:
        for rschema, target in containers:
            if target == 'object':
                targets = rschema.objects(eschema)
            else:
                targets = rschema.subjects(eschema)
            for targeteschema in targets:
                if targeteschema in _done:
                    continue
                _done.add(targeteschema)
                for container in etype_fti_containers(targeteschema, _done):
                    yield container
    else:
        yield eschema
    
def reindex_entities(schema, session):
    """reindex all entities in the repository"""
    # deactivate modification_date hook since we don't want them
    # to be updated due to the reindexation
    from cubicweb.server.hooks import (setmtime_before_update_entity,
                                       uniquecstrcheck_before_modification)
    from cubicweb.server.repository import FTIndexEntityOp
    repo = session.repo
    repo.hm.unregister_hook(setmtime_before_update_entity,
                            'before_update_entity', '')
    repo.hm.unregister_hook(uniquecstrcheck_before_modification,
                            'before_update_entity', '')
    repo.do_fti = True  # ensure full-text indexation is activated
    etypes = set()
    for eschema in schema.entities():
        if eschema.is_final():
            continue
        indexable_attrs = tuple(eschema.indexable_attributes()) # generator
        if not indexable_attrs:
            continue
        for container in etype_fti_containers(eschema):
            etypes.add(container)
    print 'Reindexing entities of type %s' % \
          ', '.join(sorted(str(e) for e in etypes))
    pb = ProgressBar(len(etypes) + 1)
    # first monkey patch Entity.check to disable validation
    from cubicweb.entity import Entity
    _check = Entity.check
    Entity.check = lambda self, creation=False: True
    # clear fti table first
    session.system_sql('DELETE FROM %s' % session.repo.system_source.dbhelper.fti_table)
    pb.update()
    # reindex entities by generating rql queries which set all indexable
    # attribute to their current value
    for eschema in etypes:
        for entity in session.execute('Any X WHERE X is %s' % eschema).entities():
            FTIndexEntityOp(session, entity=entity)
        pb.update()
    # restore Entity.check
    Entity.check = _check

    
def check_schema(schema, session, eids, fix=1):
    """check serialized schema"""
    print 'Checking serialized schema'
    unique_constraints = ('SizeConstraint', 'FormatConstraint',
                          'VocabularyConstraint', 'RQLConstraint',
                          'RQLVocabularyConstraint')
    rql = ('Any COUNT(X),RN,EN,ECTN GROUPBY RN,EN,ECTN ORDERBY 1 '
           'WHERE X is EConstraint, R constrained_by X, '
           'R relation_type RT, R from_entity ET, RT name RN, '
           'ET name EN, X cstrtype ECT, ECT name ECTN')
    for count, rn, en, cstrname in session.execute(rql):
        if count == 1:
            continue
        if cstrname in unique_constraints:
            print "ERROR: got %s %r constraints on relation %s.%s" % (
                count, cstrname, en, rn)


    
def check_text_index(schema, session, eids, fix=1):
    """check all entities registered in the text index"""
    print 'Checking text index'
    cursor = session.system_sql('SELECT uid FROM appears;')
    for row in cursor.fetchall():
        eid = row[0]
        if not has_eid(cursor, eid, eids):
            msg = '  Entity with eid %s exists in the text index but in no source'
            print >> sys.stderr, msg % eid,
            if fix:
                session.system_sql('DELETE FROM appears WHERE uid=%s;' % eid)
                print >> sys.stderr, ' [FIXED]'
            else:
                print >> sys.stderr


def check_entities(schema, session, eids, fix=1):
    """check all entities registered in the repo system table"""
    print 'Checking entities system table'
    cursor = session.system_sql('SELECT eid FROM entities;')
    for row in cursor.fetchall():
        eid = row[0]
        if not has_eid(cursor, eid, eids):
            msg = '  Entity with eid %s exists in the system table but in no source'
            print >> sys.stderr, msg % eid,
            if fix:
                session.system_sql('DELETE FROM entities WHERE eid=%s;' % eid)
                print >> sys.stderr, ' [FIXED]'
            else:
                print >> sys.stderr
    print 'Checking entities tables'
    for eschema in schema.entities():
        if eschema.is_final():
            continue
        table = SQL_PREFIX + eschema.type
        column = SQL_PREFIX +  'eid'
        cursor = session.system_sql('SELECT %s FROM %s;' % (column, table))
        for row in cursor.fetchall():
            eid = row[0]
            # eids is full since we have fetched everyting from the entities table,
            # no need to call has_eid
            if not eid in eids or not eids[eid]:
                msg = '  Entity with eid %s exists in the %s table but not in the system table'
                print >> sys.stderr, msg % (eid, eschema.type),
                if fix:
                    session.system_sql('DELETE FROM %s WHERE %s=%s;' % (table, column, eid))
                    print >> sys.stderr, ' [FIXED]'
                else:
                    print >> sys.stderr
                
            
def bad_related_msg(rtype, target, eid, fix):
    msg = '  A relation %s with %s eid %s exists but no such entity in sources'
    print >> sys.stderr, msg % (rtype, target, eid),
    if fix:
        print >> sys.stderr, ' [FIXED]'
    else:
        print >> sys.stderr
    
    
def check_relations(schema, session, eids, fix=1):
    """check all relations registered in the repo system table"""
    print 'Checking relations'
    for rschema in schema.relations():
        if rschema.is_final():
            continue
        if rschema == 'identity':
            continue
        if rschema.inlined:
            for subjtype in rschema.subjects():
                table = SQL_PREFIX + str(subjtype)
                column = SQL_PREFIX +  str(rschema)
                sql = 'SELECT %s FROM %s WHERE %s IS NOT NULL;' % (
                    column, table, column)
                cursor = session.system_sql(sql)
                for row in cursor.fetchall():
                    eid = row[0]
                    if not has_eid(cursor, eid, eids):
                        bad_related_msg(rschema, 'object', eid, fix)
                        if fix:
                            sql = 'UPDATE %s SET %s = NULL WHERE %seid=%s;' % (
                                table, column, SQL_PREFIX, eid)
                            session.system_sql(sql)
            continue
        cursor = session.system_sql('SELECT eid_from FROM %s_relation;' % rschema)
        for row in cursor.fetchall():
            eid = row[0]
            if not has_eid(cursor, eid, eids):
                bad_related_msg(rschema, 'subject', eid, fix)
                if fix:
                    sql = 'DELETE FROM %s_relation WHERE eid_from=%s;' % (
                        rschema, eid)
                    session.system_sql(sql)
        cursor = session.system_sql('SELECT eid_to FROM %s_relation;' % rschema)
        for row in cursor.fetchall():
            eid = row[0]
            if not has_eid(cursor, eid, eids):
                bad_related_msg(rschema, 'object', eid, fix)
                if fix:
                    sql = 'DELETE FROM %s_relation WHERE eid_to=%s;' % (
                        rschema, eid)
                    session.system_sql(sql)


def check_metadata(schema, session, eids, fix=1):
    """check entities has required metadata

    FIXME: rewrite using RQL queries ?
    """
    print 'Checking metadata'
    cursor = session.system_sql("SELECT DISTINCT type FROM entities;")
    eidcolumn = SQL_PREFIX + 'eid'
    for etype, in cursor.fetchall():
        table = SQL_PREFIX + etype
        for rel, default in ( ('creation_date', datetime.now()),
                              ('modification_date', datetime.now()), ):
            column = SQL_PREFIX + rel
            cursor = session.system_sql("SELECT %s FROM %s WHERE %s is NULL"
                                        % (eidcolumn, table, column))
            for eid, in cursor.fetchall():
                msg = '  %s with eid %s has no %s'
                print >> sys.stderr, msg % (etype, eid, rel),
                if fix:
                    session.system_sql("UPDATE %s SET %s=%%(v)s WHERE %s=%s ;"
                                       % (table, column, eidcolumn, eid),
                                       {'v': default})
                    print >> sys.stderr, ' [FIXED]'
                else:
                    print >> sys.stderr
    cursor = session.system_sql('SELECT MIN(%s) FROM %sEUser;' % (eidcolumn,
                                                                  SQL_PREFIX))
    default_user_eid = cursor.fetchone()[0]
    assert default_user_eid is not None, 'no user defined !'
    for rel, default in ( ('owned_by', default_user_eid), ):
        cursor = session.system_sql("SELECT eid, type FROM entities "
                                    "WHERE NOT EXISTS "
                                    "(SELECT 1 FROM %s_relation WHERE eid_from=eid);"
                                    % rel)
        for eid, etype in cursor.fetchall():
            msg = '  %s with eid %s has no %s relation'
            print >> sys.stderr, msg % (etype, eid, rel),
            if fix:
                session.system_sql('INSERT INTO %s_relation VALUES (%s, %s) ;'
                                   % (rel, eid, default))
                print >> sys.stderr, ' [FIXED]'
            else:
                print >> sys.stderr


def check(repo, cnx, checks, reindex, fix):
    """check integrity of application's repository,
    using given user and password to locally connect to the repository
    (no running cubicweb server needed)
    """
    session = repo._get_session(cnx.sessionid, setpool=True)
    # yo, launch checks
    if checks:
        eids_cache = {}
        for check in checks:
            check_func = globals()['check_%s' % check]
            check_func(repo.schema, session, eids_cache, fix=fix)
        if fix:
            cnx.commit()
        else:
            print
        if not fix:
            print 'WARNING: Diagnostic run, nothing has been corrected'
    if reindex:
        cnx.rollback()
        session.set_pool()
        reindex_entities(repo.schema, session)
        cnx.commit()
