# copyright 2003-2010 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
# contact http://www.logilab.fr/ -- mailto:contact@logilab.fr
#
# This file is part of CubicWeb.
#
# CubicWeb is free software: you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation, either version 2.1 of the License, or (at your option)
# any later version.
#
# CubicWeb is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License along
# with CubicWeb.  If not, see <http://www.gnu.org/licenses/>.
"""Integrity checking tool for instances:

* integrity of a CubicWeb repository. Hum actually only the system database is
  checked.

* consistency of multi-sources instance mapping file
"""

from __future__ import with_statement

__docformat__ = "restructuredtext en"

import sys
from datetime import datetime

from logilab.common.shellutils import ProgressBar

from cubicweb.schema import META_RTYPES, VIRTUAL_RTYPES, PURE_VIRTUAL_RTYPES
from cubicweb.server.sqlutils import SQL_PREFIX
from cubicweb.server.session import security_enabled

def has_eid(session, sqlcursor, eid, eids):
    """return true if the eid is a valid eid"""
    if eid in eids:
        return eids[eid]
    sqlcursor.execute('SELECT type, source FROM entities WHERE eid=%s' % eid)
    try:
        etype, source = sqlcursor.fetchone()
    except:
        eids[eid] = False
        return False
    if source and source != 'system':
        try:
            # insert eid *and* etype to attempt checking entity has not been
            # replaced by another subsquently to a restore of an old dump
            if session.execute('Any X WHERE X is %s, X eid %%(x)s' % etype,
                               {'x': eid}):
                eids[eid] = True
                return True
        except: # TypeResolverError, Unauthorized...
            pass
        eids[eid] = False
        return False
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

def reindex_entities(schema, session, withpb=True, etypes=None):
    """reindex all entities in the repository"""
    # deactivate modification_date hook since we don't want them
    # to be updated due to the reindexation
    repo = session.repo
    cursor = session.pool['system']
    dbhelper = session.repo.system_source.dbhelper
    if not dbhelper.has_fti_table(cursor):
        print 'no text index table'
        dbhelper.init_fti(cursor)
    repo.system_source.do_fti = True  # ensure full-text indexation is activated
    if etypes is None:
        print 'Reindexing entities'
        etypes = set()
        for eschema in schema.entities():
            if eschema.final:
                continue
            indexable_attrs = tuple(eschema.indexable_attributes()) # generator
            if not indexable_attrs:
                continue
            for container in etype_fti_containers(eschema):
                etypes.add(container)
        # clear fti table first
        session.system_sql('DELETE FROM %s' % dbhelper.fti_table)
    else:
        print 'Reindexing entities of type %s' % \
              ', '.join(sorted(str(e) for e in etypes))
        # clear fti table first. Use subquery for sql compatibility
        session.system_sql("DELETE FROM %s WHERE EXISTS(SELECT 1 FROM ENTITIES "
                           "WHERE eid=%s AND type IN (%s))" % (
                               dbhelper.fti_table, dbhelper.fti_uid_attr,
                               ','.join("'%s'" % etype for etype in etypes)))
    if withpb:
        pb = ProgressBar(len(etypes) + 1)
        pb.update()
    # reindex entities by generating rql queries which set all indexable
    # attribute to their current value
    source = repo.system_source
    for eschema in etypes:
        for entity in session.execute('Any X WHERE X is %s' % eschema).entities():
            source.fti_index_entity(session, entity)
        if withpb:
            pb.update()


def check_schema(schema, session, eids, fix=1):
    """check serialized schema"""
    print 'Checking serialized schema'
    unique_constraints = ('SizeConstraint', 'FormatConstraint',
                          'VocabularyConstraint',
                          'RQLVocabularyConstraint')
    rql = ('Any COUNT(X),RN,SN,ON,CTN GROUPBY RN,SN,ON,CTN ORDERBY 1 '
           'WHERE X is CWConstraint, R constrained_by X, '
           'R relation_type RT, RT name RN, R from_entity ST, ST name SN, '
           'R to_entity OT, OT name ON, X cstrtype CT, CT name CTN')
    for count, rn, sn, on, cstrname in session.execute(rql):
        if count == 1:
            continue
        if cstrname in unique_constraints:
            print "ERROR: got %s %r constraints on relation %s.%s.%s" % (
                count, cstrname, sn, rn, on)
            if fix:
                print 'dunno how to fix, do it yourself'



def check_text_index(schema, session, eids, fix=1):
    """check all entities registered in the text index"""
    print 'Checking text index'
    cursor = session.system_sql('SELECT uid FROM appears;')
    for row in cursor.fetchall():
        eid = row[0]
        if not has_eid(session, cursor, eid, eids):
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
        if not has_eid(session, cursor, eid, eids):
            msg = '  Entity with eid %s exists in the system table but in no source'
            print >> sys.stderr, msg % eid,
            if fix:
                session.system_sql('DELETE FROM entities WHERE eid=%s;' % eid)
                print >> sys.stderr, ' [FIXED]'
            else:
                print >> sys.stderr
    print 'Checking entities tables'
    for eschema in schema.entities():
        if eschema.final:
            continue
        table = SQL_PREFIX + eschema.type
        column = SQL_PREFIX +  'eid'
        cursor = session.system_sql('SELECT %s FROM %s;' % (column, table))
        for row in cursor.fetchall():
            eid = row[0]
            # eids is full since we have fetched everything from the entities table,
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
        if rschema.final or rschema in PURE_VIRTUAL_RTYPES:
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
                    if not has_eid(session, cursor, eid, eids):
                        bad_related_msg(rschema, 'object', eid, fix)
                        if fix:
                            sql = 'UPDATE %s SET %s=NULL WHERE %s=%s;' % (
                                table, column, column, eid)
                            session.system_sql(sql)
            continue
        try:
            cursor = session.system_sql('SELECT eid_from FROM %s_relation;' % rschema)
        except Exception, ex:
            # usually because table doesn't exist
            print 'ERROR', ex
            continue
        for row in cursor.fetchall():
            eid = row[0]
            if not has_eid(session, cursor, eid, eids):
                bad_related_msg(rschema, 'subject', eid, fix)
                if fix:
                    sql = 'DELETE FROM %s_relation WHERE eid_from=%s;' % (
                        rschema, eid)
                    session.system_sql(sql)
        cursor = session.system_sql('SELECT eid_to FROM %s_relation;' % rschema)
        for row in cursor.fetchall():
            eid = row[0]
            if not has_eid(session, cursor, eid, eids):
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
    cursor = session.system_sql('SELECT MIN(%s) FROM %sCWUser;' % (eidcolumn,
                                                                  SQL_PREFIX))
    default_user_eid = cursor.fetchone()[0]
    assert default_user_eid is not None, 'no user defined !'
    for rel, default in ( ('owned_by', default_user_eid), ):
        cursor = session.system_sql("SELECT eid, type FROM entities "
                                    "WHERE source='system' AND NOT EXISTS "
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


def check(repo, cnx, checks, reindex, fix, withpb=True):
    """check integrity of instance's repository,
    using given user and password to locally connect to the repository
    (no running cubicweb server needed)
    """
    session = repo._get_session(cnx.sessionid, setpool=True)
    # yo, launch checks
    if checks:
        eids_cache = {}
        with security_enabled(session, read=False): # ensure no read security
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
        reindex_entities(repo.schema, session, withpb=withpb)
        cnx.commit()


def info(msg, *args):
    if args:
        msg = msg % args
    print 'INFO: %s' % msg

def warning(msg, *args):
    if args:
        msg = msg % args
    print 'WARNING: %s' % msg

def error(msg, *args):
    if args:
        msg = msg % args
    print 'ERROR: %s' % msg

def check_mapping(schema, mapping, warning=warning, error=error):
    # first check stuff found in mapping file exists in the schema
    for attr in ('support_entities', 'support_relations'):
        for ertype in mapping[attr].keys():
            try:
                mapping[attr][ertype] = erschema = schema[ertype]
            except KeyError:
                error('reference to unknown type %s in %s', ertype, attr)
                del mapping[attr][ertype]
            else:
                if erschema.final or erschema in META_RTYPES:
                    error('type %s should not be mapped in %s', ertype, attr)
                    del mapping[attr][ertype]
    for attr in ('dont_cross_relations', 'cross_relations'):
        for rtype in list(mapping[attr]):
            try:
                rschema = schema.rschema(rtype)
            except KeyError:
                error('reference to unknown relation type %s in %s', rtype, attr)
                mapping[attr].remove(rtype)
            else:
                if rschema.final or rschema in VIRTUAL_RTYPES:
                    error('relation type %s should not be mapped in %s',
                          rtype, attr)
                    mapping[attr].remove(rtype)
    # check relation in dont_cross_relations aren't in support_relations
    for rschema in mapping['dont_cross_relations']:
        if rschema in mapping['support_relations']:
            info('relation %s is in dont_cross_relations and in support_relations',
                 rschema)
    # check relation in cross_relations are in support_relations
    for rschema in mapping['cross_relations']:
        if rschema not in mapping['support_relations']:
            info('relation %s is in cross_relations but not in support_relations',
                 rschema)
    # check for relation in both cross_relations and dont_cross_relations
    for rschema in mapping['cross_relations'] & mapping['dont_cross_relations']:
        error('relation %s is in both cross_relations and dont_cross_relations',
              rschema)
    # now check for more handy things
    seen = set()
    for eschema in mapping['support_entities'].values():
        for rschema, ttypes, role in eschema.relation_definitions():
            if rschema in META_RTYPES:
                continue
            ttypes = [ttype for ttype in ttypes if ttype in mapping['support_entities']]
            if not rschema in mapping['support_relations']:
                somethingprinted = False
                for ttype in ttypes:
                    rdef = rschema.role_rdef(eschema, ttype, role)
                    seen.add(rdef)
                    if rdef.role_cardinality(role) in '1+':
                        error('relation %s with %s as %s and target type %s is '
                              'mandatory but not supported',
                              rschema, eschema, role, ttype)
                        somethingprinted = True
                    elif ttype in mapping['support_entities']:
                        if rdef not in seen:
                            warning('%s could be supported', rdef)
                        somethingprinted = True
                if rschema not in mapping['dont_cross_relations']:
                    if role == 'subject' and rschema.inlined:
                        error('inlined relation %s of %s should be supported',
                              rschema, eschema)
                    elif not somethingprinted and rschema not in seen and rschema not in mapping['cross_relations']:
                        print 'you may want to specify something for %s' % rschema
                        seen.add(rschema)
            else:
                if not ttypes:
                    warning('relation %s with %s as %s is supported but no target '
                            'type supported', rschema, role, eschema)
                if rschema in mapping['cross_relations'] and rschema.inlined:
                    error('you should unline relation %s which is supported and '
                          'may be crossed ', rschema)
    for rschema in mapping['support_relations'].values():
        if rschema in META_RTYPES:
            continue
        for subj, obj in rschema.rdefs:
            if subj in mapping['support_entities'] and obj in mapping['support_entities']:
                break
        else:
            error('relation %s is supported but none if its definitions '
                  'matches supported entities', rschema)
