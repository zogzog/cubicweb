# copyright 2003-2012 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""
__docformat__ = "restructuredtext en"

import sys
from datetime import datetime

from logilab.common.shellutils import ProgressBar

from cubicweb.schema import PURE_VIRTUAL_RTYPES, VIRTUAL_RTYPES
from cubicweb.server.sqlutils import SQL_PREFIX

def notify_fixed(fix):
    if fix:
        sys.stderr.write(' [FIXED]')
    sys.stderr.write('\n')

def has_eid(session, sqlcursor, eid, eids):
    """return true if the eid is a valid eid"""
    if eid in eids:
        return eids[eid]
    sqlcursor.execute('SELECT type, source FROM entities WHERE eid=%s' % eid)
    try:
        etype, source = sqlcursor.fetchone()
    except Exception:
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
        except Exception: # TypeResolverError, Unauthorized...
            pass
        eids[eid] = False
        return False
    if etype not in session.vreg.schema:
        eids[eid] = False
        return False
    sqlcursor.execute('SELECT * FROM %s%s WHERE %seid=%s' % (SQL_PREFIX, etype,
                                                             SQL_PREFIX, eid))
    result = sqlcursor.fetchall()
    if len(result) == 0:
        eids[eid] = False
        return False
    elif len(result) > 1:
        msg = ('  More than one entity with eid %s exists in source!\n'
               '  WARNING : Unable to fix this, do it yourself!\n')
        sys.stderr.write(msg % eid)
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
    cursor = session.cnxset['system']
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
        etype_class = session.vreg['etypes'].etype_class(str(eschema))
        for fti_rql in etype_class.cw_fti_index_rql_queries(session):
            rset = session.execute(fti_rql)
            source.fti_index_entities(session, rset.entities())
            # clear entity cache to avoid high memory consumption on big tables
            session.drop_entity_cache()
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
    msg = '  Entity with eid %s exists in the text index but in no source (autofix will remove from text index)'
    cursor = session.system_sql('SELECT uid FROM appears;')
    for row in cursor.fetchall():
        eid = row[0]
        if not has_eid(session, cursor, eid, eids):
            sys.stderr.write(msg % eid)
            if fix:
                session.system_sql('DELETE FROM appears WHERE uid=%s;' % eid)
            notify_fixed(fix)


def check_entities(schema, session, eids, fix=1):
    """check all entities registered in the repo system table"""
    print 'Checking entities system table'
    # system table but no source
    msg = '  Entity %s with eid %s exists in the system table but in no source (autofix will delete the entity)'
    cursor = session.system_sql('SELECT eid,type FROM entities;')
    for row in cursor.fetchall():
        eid, etype = row
        if not has_eid(session, cursor, eid, eids):
            sys.stderr.write(msg % (etype, eid))
            if fix:
                session.system_sql('DELETE FROM entities WHERE eid=%s;' % eid)
            notify_fixed(fix)
    # source in entities, but no relation cw_source
    applcwversion = session.repo.get_versions().get('cubicweb')
    if applcwversion >= (3,13,1): # entities.asource appeared in 3.13.1
        cursor = session.system_sql('SELECT e.eid FROM entities as e, cw_CWSource as s '
                                    'WHERE s.cw_name=e.asource AND '
                                    'NOT EXISTS(SELECT 1 FROM cw_source_relation as cs '
                                    '  WHERE cs.eid_from=e.eid AND cs.eid_to=s.cw_eid) '
                                    'ORDER BY e.eid')
        msg = ('  Entity with eid %s refers to source in entities table, '
               'but is missing relation cw_source (autofix will create the relation)\n')
        for row in cursor.fetchall():
            sys.stderr.write(msg % row[0])
        if fix:
            session.system_sql('INSERT INTO cw_source_relation (eid_from, eid_to) '
                               'SELECT e.eid, s.cw_eid FROM entities as e, cw_CWSource as s '
                               'WHERE s.cw_name=e.asource AND NOT EXISTS(SELECT 1 FROM cw_source_relation as cs '
                               '  WHERE cs.eid_from=e.eid AND cs.eid_to=s.cw_eid)')
            notify_fixed(True)
    # inconsistencies for 'is'
    msg = '  %s #%s is missing relation "is" (autofix will create the relation)\n'
    cursor = session.system_sql('SELECT e.type, e.eid FROM entities as e, cw_CWEType as s '
                                'WHERE s.cw_name=e.type AND NOT EXISTS(SELECT 1 FROM is_relation as cs '
                                '  WHERE cs.eid_from=e.eid AND cs.eid_to=s.cw_eid) '
                                'ORDER BY e.eid')
    for row in cursor.fetchall():
        sys.stderr.write(msg % row)
    if fix:
        session.system_sql('INSERT INTO is_relation (eid_from, eid_to) '
                           'SELECT e.eid, s.cw_eid FROM entities as e, cw_CWEType as s '
                           'WHERE s.cw_name=e.type AND NOT EXISTS(SELECT 1 FROM is_relation as cs '
                           '  WHERE cs.eid_from=e.eid AND cs.eid_to=s.cw_eid)')
        notify_fixed(True)
    # inconsistencies for 'is_instance_of'
    msg = '  %s #%s is missing relation "is_instance_of" (autofix will create the relation)\n'
    cursor = session.system_sql('SELECT e.type, e.eid FROM entities as e, cw_CWEType as s '
                                'WHERE s.cw_name=e.type AND NOT EXISTS(SELECT 1 FROM is_instance_of_relation as cs '
                                '  WHERE cs.eid_from=e.eid AND cs.eid_to=s.cw_eid) '
                                'ORDER BY e.eid')
    for row in cursor.fetchall():
        sys.stderr.write(msg % row)
    if fix:
        session.system_sql('INSERT INTO is_instance_of_relation (eid_from, eid_to) '
                           'SELECT e.eid, s.cw_eid FROM entities as e, cw_CWEType as s '
                           'WHERE s.cw_name=e.type AND NOT EXISTS(SELECT 1 FROM is_instance_of_relation as cs '
                           '  WHERE cs.eid_from=e.eid AND cs.eid_to=s.cw_eid)')
        notify_fixed(True)
    print 'Checking entities tables'
    msg = '  Entity with eid %s exists in the %s table but not in the system table (autofix will delete the entity)'
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
                sys.stderr.write(msg % (eid, eschema.type))
                if fix:
                    session.system_sql('DELETE FROM %s WHERE %s=%s;' % (table, column, eid))
                notify_fixed(fix)


def bad_related_msg(rtype, target, eid, fix):
    msg = '  A relation %s with %s eid %s exists but no such entity in sources'
    sys.stderr.write(msg % (rtype, target, eid))
    notify_fixed(fix)

def bad_inlined_msg(rtype, parent_eid, eid, fix):
    msg = ('  An inlined relation %s from %s to %s exists but the latter '
           'entity does not exist')
    sys.stderr.write(msg % (rtype, parent_eid, eid))
    notify_fixed(fix)


def check_relations(schema, session, eids, fix=1):
    """check that eids referenced by relations are registered in the repo system
    table
    """
    print 'Checking relations'
    for rschema in schema.relations():
        if rschema.final or rschema.type in PURE_VIRTUAL_RTYPES:
            continue
        if rschema.inlined:
            for subjtype in rschema.subjects():
                table = SQL_PREFIX + str(subjtype)
                column = SQL_PREFIX +  str(rschema)
                sql = 'SELECT cw_eid,%s FROM %s WHERE %s IS NOT NULL;' % (
                    column, table, column)
                cursor = session.system_sql(sql)
                for row in cursor.fetchall():
                    parent_eid, eid = row
                    if not has_eid(session, cursor, eid, eids):
                        bad_inlined_msg(rschema, parent_eid, eid, fix)
                        if fix:
                            sql = 'UPDATE %s SET %s=NULL WHERE %s=%s;' % (
                                table, column, column, eid)
                            session.system_sql(sql)
            continue
        try:
            cursor = session.system_sql('SELECT eid_from FROM %s_relation;' % rschema)
        except Exception as ex:
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


def check_mandatory_relations(schema, session, eids, fix=1):
    """check entities missing some mandatory relation"""
    print 'Checking mandatory relations'
    msg = '%s #%s is missing mandatory %s relation %s (autofix will delete the entity)'
    for rschema in schema.relations():
        if rschema.final or rschema in PURE_VIRTUAL_RTYPES or rschema in ('is', 'is_instance_of'):
            continue
        smandatory = set()
        omandatory = set()
        for rdef in rschema.rdefs.itervalues():
            if rdef.cardinality[0] in '1+':
                smandatory.add(rdef.subject)
            if rdef.cardinality[1] in '1+':
                omandatory.add(rdef.object)
        for role, etypes in (('subject', smandatory), ('object', omandatory)):
            for etype in etypes:
                if role == 'subject':
                    rql = 'Any X WHERE NOT X %s Y, X is %s' % (rschema, etype)
                else:
                    rql = 'Any X WHERE NOT Y %s X, X is %s' % (rschema, etype)
                for entity in session.execute(rql).entities():
                    sys.stderr.write(msg % (entity.cw_etype, entity.eid, role, rschema))
                    if fix:
                        #if entity.cw_describe()['source']['uri'] == 'system': XXX
                        entity.cw_delete() # XXX this is BRUTAL!
                    notify_fixed(fix)


def check_mandatory_attributes(schema, session, eids, fix=1):
    """check for entities stored in the system source missing some mandatory
    attribute
    """
    print 'Checking mandatory attributes'
    msg = '%s #%s is missing mandatory attribute %s (autofix will delete the entity)'
    for rschema in schema.relations():
        if not rschema.final or rschema in VIRTUAL_RTYPES:
            continue
        for rdef in rschema.rdefs.itervalues():
            if rdef.cardinality[0] in '1+':
                rql = 'Any X WHERE X %s NULL, X is %s, X cw_source S, S name "system"' % (
                    rschema, rdef.subject)
                for entity in session.execute(rql).entities():
                    sys.stderr.write(msg % (entity.cw_etype, entity.eid, rschema))
                    if fix:
                        entity.cw_delete()
                    notify_fixed(fix)


def check_metadata(schema, session, eids, fix=1):
    """check entities has required metadata

    FIXME: rewrite using RQL queries ?
    """
    print 'Checking metadata'
    cursor = session.system_sql("SELECT DISTINCT type FROM entities;")
    eidcolumn = SQL_PREFIX + 'eid'
    msg = '  %s with eid %s has no %s (autofix will set it to now)'
    for etype, in cursor.fetchall():
        if etype not in session.vreg.schema:
            sys.stderr.write('entities table references unknown type %s\n' %
                             etype)
            if fix:
                session.system_sql("DELETE FROM entities WHERE type = %(type)s",
                                   {'type': etype})
            continue
        table = SQL_PREFIX + etype
        for rel, default in ( ('creation_date', datetime.now()),
                              ('modification_date', datetime.now()), ):
            column = SQL_PREFIX + rel
            cursor = session.system_sql("SELECT %s FROM %s WHERE %s is NULL"
                                        % (eidcolumn, table, column))
            for eid, in cursor.fetchall():
                sys.stderr.write(msg % (etype, eid, rel))
                if fix:
                    session.system_sql("UPDATE %s SET %s=%%(v)s WHERE %s=%s ;"
                                       % (table, column, eidcolumn, eid),
                                       {'v': default})
                notify_fixed(fix)


def check(repo, cnx, checks, reindex, fix, withpb=True):
    """check integrity of instance's repository,
    using given user and password to locally connect to the repository
    (no running cubicweb server needed)
    """
    session = repo._get_session(cnx.sessionid, setcnxset=True)
    # yo, launch checks
    if checks:
        eids_cache = {}
        with session.security_enabled(read=False, write=False): # ensure no read security
            for check in checks:
                check_func = globals()['check_%s' % check]
                check_func(repo.schema, session, eids_cache, fix=fix)
        if fix:
            session.commit()
        else:
            print
        if not fix:
            print 'WARNING: Diagnostic run, nothing has been corrected'
    if reindex:
        session.rollback()
        session.set_cnxset()
        reindex_entities(repo.schema, session, withpb=withpb)
        session.commit()
