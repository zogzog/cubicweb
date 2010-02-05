"""functions for schema / permissions (de)serialization using RQL

:organization: Logilab
:copyright: 2001-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

import os
import sys
import os
from itertools import chain

from logilab.common.shellutils import ProgressBar

from yams import schema as schemamod, buildobjs as ybo

from cubicweb.schema import CONSTRAINTS, ETYPE_NAME_MAP, VIRTUAL_RTYPES
from cubicweb.server import sqlutils

def group_mapping(cursor, interactive=True):
    """create a group mapping from an rql cursor

    A group mapping has standard group names as key (managers, owners at least)
    and the actual CWGroup entity's eid as associated value.
    In interactive mode (the default), missing groups'eid will be prompted
    from the user.
    """
    res = {}
    for eid, name in cursor.execute('Any G, N WHERE G is CWGroup, G name N',
                                    build_descr=False):
        res[name] = eid
    if not interactive:
        return res
    missing = [g for g in ('owners', 'managers', 'users', 'guests') if not g in res]
    if missing:
        print 'some native groups are missing but the following groups have been found:'
        print '\n'.join('* %s (%s)' % (n, eid) for n, eid in res.items())
        print
        print 'enter the eid of a to group to map to each missing native group'
        print 'or just type enter to skip permissions granted to a group'
        for group in missing:
            while True:
                value = raw_input('eid for group %s: ' % group).strip()
                if not value:
                    continue
                try:
                    res[group] = int(value)
                except ValueError:
                    print 'eid should be an integer'
                    continue
    return res

def _set_sql_prefix(prefix):
    """3.2.0 migration function: allow to unset/reset SQL_PREFIX"""
    for module in ('checkintegrity', 'migractions', 'schemahooks',
                   'sources.rql2sql', 'sources.native', 'sqlutils'):
        try:
            sys.modules['cubicweb.server.%s' % module].SQL_PREFIX = prefix
            print 'changed SQL_PREFIX for %s' % module
        except KeyError:
            pass

def _update_database(schema, sqlcu):
    """3.2.0 migration function: update database schema by adding SQL_PREFIX to
    entity type tables and columns
    """
    for etype in schema.entities():
        if etype.final:
            continue
        try:
            sql = 'ALTER TABLE %s RENAME TO cw_%s' % (
                etype, ETYPE_NAME_MAP.get(etype, etype))
            print sql
            sqlcu.execute(sql)
        except:
            pass
        for rschema in etype.subject_relations():
            if rschema == 'has_text':
                continue
            if rschema.final or rschema.inlined:
                sql = 'ALTER TABLE cw_%s RENAME %s TO cw_%s' % (
                    etype, rschema, rschema)
                print sql
                sqlcu.execute(sql)

# schema / perms deserialization ##############################################
OLD_SCHEMA_TYPES = frozenset(('EFRDef', 'ENFRDef', 'ERType', 'EEType',
                              'EConstraintType', 'EConstraint', 'EGroup',
                              'EUser', 'ECache', 'EPermission', 'EProperty'))

def deserialize_schema(schema, session):
    """return a schema according to information stored in an rql database
    as CWRType and CWEType entities
    """
    #
    repo = session.repo
    sqlcu = session.pool['system']
    _3_2_migration = False
    dbhelper = repo.system_source.dbhelper
    tables = set(t.lower() for t in dbhelper.list_tables(sqlcu))
    if 'eetype' in tables:
        _3_2_migration = True
        # 3.2 migration
        _set_sql_prefix('')
        # first rename entity types whose name changed in 3.2 without adding the
        # cw_ prefix
        for etype in OLD_SCHEMA_TYPES:
            if etype.lower() in tables:
                sql = 'ALTER TABLE %s RENAME TO %s' % (etype,
                                                       ETYPE_NAME_MAP[etype])
                print sql
                sqlcu.execute(sql)
        # other table renaming done once schema has been read
    # 3.6 migration
    sqlcu.execute("SELECT * FROM cw_CWRType WHERE cw_name='symetric'")
    if sqlcu.fetchall():
        sql = dbhelper.sql_rename_col('cw_CWRType', 'cw_symetric', 'cw_symmetric',
                                      dbhelper.TYPE_MAPPING['Boolean'], True)
        sqlcu.execute(sql)
        sqlcu.execute("UPDATE cw_CWRType SET cw_name='symmetric' WHERE cw_name='symetric'")
    sidx = {}
    permsdict = deserialize_ertype_permissions(session)
    schema.reading_from_database = True
    for eid, etype, desc in session.execute(
        'Any X, N, D WHERE X is CWEType, X name N, X description D',
        build_descr=False):
        # base types are already in the schema, skip them
        if etype in schemamod.BASE_TYPES:
            # just set the eid
            eschema = schema.eschema(etype)
            eschema.eid = eid
            sidx[eid] = eschema
            continue
        if etype in ETYPE_NAME_MAP:
            netype = ETYPE_NAME_MAP[etype]
            # can't use write rql queries at this point, use raw sql
            session.system_sql('UPDATE %(p)sCWEType SET %(p)sname=%%(n)s WHERE %(p)seid=%%(x)s'
                               % {'p': sqlutils.SQL_PREFIX},
                               {'x': eid, 'n': netype})
            session.system_sql('UPDATE entities SET type=%(n)s WHERE type=%(x)s',
                               {'x': etype, 'n': netype})
            # XXX should be donne as well on sqlite based sources
            if not etype in OLD_SCHEMA_TYPES and \
               (getattr(dbhelper, 'case_sensitive', False)
                or etype.lower() != netype.lower()):
                session.system_sql('ALTER TABLE %s%s RENAME TO %s%s' % (
                    sqlutils.SQL_PREFIX, etype, sqlutils.SQL_PREFIX, netype))
            session.commit(False)
            try:
                session.system_sql('UPDATE deleted_entities SET type=%(n)s WHERE type=%(x)s',
                                   {'x': etype, 'n': netype})
            except:
                pass
            tocleanup = [eid]
            tocleanup += (eid for eid, (eidetype, uri, extid) in repo._type_source_cache.items()
                          if etype == eidetype)
            repo.clear_caches(tocleanup)
            session.commit(False)
            etype = netype
        etype = ybo.EntityType(name=etype, description=desc, eid=eid)
        eschema = schema.add_entity_type(etype)
        sidx[eid] = eschema
        set_perms(eschema, permsdict)
    for etype, stype in session.execute(
        'Any XN, ETN WHERE X is CWEType, X name XN, X specializes ET, ET name ETN',
        build_descr=False):
        schema.eschema(etype)._specialized_type = stype
        schema.eschema(stype)._specialized_by.append(etype)
    for eid, rtype, desc, sym, il, ftc in session.execute(
        'Any X,N,D,S,I,FTC WHERE X is CWRType, X name N, X description D, '
        'X symmetric S, X inlined I, X fulltext_container FTC', build_descr=False):
        rtype = ybo.RelationType(name=rtype, description=desc,
                                 symmetric=bool(sym), inlined=bool(il),
                                 fulltext_container=ftc, eid=eid)
        rschema = schema.add_relation_type(rtype)
        sidx[eid] = rschema
    cstrsdict = deserialize_rdef_constraints(session)
    for values in session.execute(
        'Any X,SE,RT,OE,CARD,ORD,DESC,IDX,FTIDX,I18N,DFLT WHERE X is CWAttribute,'
        'X relation_type RT, X cardinality CARD, X ordernum ORD, X indexed IDX,'
        'X description DESC, X internationalizable I18N, X defaultval DFLT,'
        'X fulltextindexed FTIDX, X from_entity SE, X to_entity OE',
        build_descr=False):
        rdefeid, seid, reid, teid, card, ord, desc, idx, ftidx, i18n, default = values
        rdef = ybo.RelationDefinition(sidx[seid].type, sidx[reid].type, sidx[teid].type,
                                      cardinality=card,
                                      constraints=cstrsdict.get(rdefeid, ()),
                                      order=ord, description=desc,
                                      indexed=idx, fulltextindexed=ftidx,
                                      internationalizable=i18n,
                                      default=default, eid=rdefeid)
        rdefs = schema.add_relation_def(rdef)
        # rdefs can be None on duplicated relation definitions (e.g. symmetrics)
        if rdefs is not None:
            set_perms(rdefs, permsdict)
    for values in session.execute(
        'Any X,SE,RT,OE,CARD,ORD,DESC,C WHERE X is CWRelation, X relation_type RT,'
        'X cardinality CARD, X ordernum ORD, X description DESC, '
        'X from_entity SE, X to_entity OE, X composite C', build_descr=False):
        rdefeid, seid, reid, teid, card, ord, desc, c = values
        rdef = ybo.RelationDefinition(sidx[seid].type, sidx[reid].type, sidx[teid].type,
                                      constraints=cstrsdict.get(rdefeid, ()),
                                      cardinality=card, order=ord, description=desc,
                                      composite=c,  eid=rdefeid)
        rdefs = schema.add_relation_def(rdef)
        # rdefs can be None on duplicated relation definitions (e.g. symmetrics)
        if rdefs is not None:
            set_perms(rdefs, permsdict)
    schema.infer_specialization_rules()
    if _3_2_migration:
        _update_database(schema, sqlcu)
        _set_sql_prefix('cw_')
    session.commit()
    schema.reading_from_database = False


def deserialize_ertype_permissions(session):
    """return sect action:groups associations for the given
    entity or relation schema with its eid, according to schema's
    permissions stored in the database as [read|add|delete|update]_permission
    relations between CWEType/CWRType and CWGroup entities
    """
    res = {}
    for action in ('read', 'add', 'update', 'delete'):
        rql = 'Any E,N WHERE G is CWGroup, G name N, E %s_permission G' % action
        for eid, gname in session.execute(rql, build_descr=False):
            res.setdefault(eid, {}).setdefault(action, []).append(gname)
        rql = ('Any E,X,EXPR,V WHERE X is RQLExpression, X expression EXPR, '
               'E %s_permission X, X mainvars V' % action)
        for eid, expreid, expr, mainvars in session.execute(rql, build_descr=False):
            # we don't know yet if it's a rql expr for an entity or a relation,
            # so append a tuple to differentiate from groups and so we'll be
            # able to instantiate it later
            res.setdefault(eid, {}).setdefault(action, []).append( (expr, mainvars, expreid) )
    return res

def set_perms(erschema, permsdict):
    """set permissions on the given erschema according to the permission
    definition dictionary as built by deserialize_ertype_permissions for a
    given erschema's eid
    """
    try:
        thispermsdict = permsdict[erschema.eid]
    except KeyError:
        return
    permissions = erschema.permissions
    for action, somethings in thispermsdict.iteritems():
        permissions[action] = tuple(
            isinstance(p, tuple) and erschema.rql_expression(*p) or p
            for p in somethings)


def deserialize_rdef_constraints(session):
    """return the list of relation definition's constraints as instances"""
    res = {}
    for rdefeid, ceid, ct, val in session.execute(
        'Any E, X,TN,V WHERE E constrained_by X, X is CWConstraint, '
        'X cstrtype T, T name TN, X value V', build_descr=False):
        cstr = CONSTRAINTS[ct].deserialize(val)
        cstr.eid = ceid
        res.setdefault(rdefeid, []).append(cstr)
    return res


# schema / perms serialization ################################################

def serialize_schema(cursor, schema, verbose=False):
    """synchronize schema and permissions in the database according to
    current schema
    """
    quiet = os.environ.get('APYCOT_ROOT')
    if not quiet:
        _title = '-> storing the schema in the database '
        print _title,
    execute = cursor.execute
    eschemas = schema.entities()
    aller = eschemas + schema.relations()
    if not verbose and not quiet:
        pb_size = len(aller) + len(CONSTRAINTS) + len([x for x in eschemas if x.specializes()])
        pb = ProgressBar(pb_size, title=_title)
    else:
        pb = None
    rql = 'INSERT CWConstraintType X: X name %(ct)s'
    for cstrtype in CONSTRAINTS:
        if verbose:
            print rql
        execute(rql, {'ct': unicode(cstrtype)}, build_descr=False)
        if pb is not None:
            pb.update()
    groupmap = group_mapping(cursor, interactive=False)
    for ertype in aller:
        # skip eid and has_text relations
        if ertype in VIRTUAL_RTYPES:
            if pb is not None:
                pb.update()
            continue
        for rql, kwargs in erschema2rql(schema[ertype], groupmap):
            if verbose:
                print rql % kwargs
            execute(rql, kwargs, build_descr=False)
        if pb is not None:
            pb.update()
    for rql, kwargs in specialize2rql(schema):
        if verbose:
            print rql % kwargs
        execute(rql, kwargs, build_descr=False)
        if pb is not None:
            pb.update()
    if not quiet:
        print


def _ervalues(erschema):
    try:
        type_ = unicode(erschema.type)
    except UnicodeDecodeError, e:
        raise Exception("can't decode %s [was %s]" % (erschema.type, e))
    try:
        desc = unicode(erschema.description) or u''
    except UnicodeDecodeError, e:
        raise Exception("can't decode %s [was %s]" % (erschema.description, e))
    return {
        'name': type_,
        'final': erschema.final,
        'description': desc,
        }

def eschema_relations_values(eschema):
    values = _ervalues(eschema)
    relations = ['X %s %%(%s)s' % (attr, attr) for attr in sorted(values)]
    return relations, values

# XXX 2.47 migration
HAS_FULLTEXT_CONTAINER = True

def rschema_relations_values(rschema):
    values = _ervalues(rschema)
    values['final'] = rschema.final
    values['symmetric'] = rschema.symmetric
    values['inlined'] = rschema.inlined
    if HAS_FULLTEXT_CONTAINER:
        if isinstance(rschema.fulltext_container, str):
            values['fulltext_container'] = unicode(rschema.fulltext_container)
        else:
            values['fulltext_container'] = rschema.fulltext_container
    relations = ['X %s %%(%s)s' % (attr, attr) for attr in sorted(values)]
    return relations, values

def _rdef_values(rschema, objtype, props):
    amap = {'order': 'ordernum'}
    values = {}
    for prop, default in schemamod.RelationDefinitionSchema.rproperty_defs(objtype).iteritems():
        if prop in ('eid', 'constraints', 'uid', 'infered', 'permissions'):
            continue
        value = props.get(prop, default)
        if prop in ('indexed', 'fulltextindexed', 'internationalizable'):
            value = bool(value)
        elif prop == 'ordernum':
            value = int(value)
        elif isinstance(value, str):
            value = unicode(value)
        values[amap.get(prop, prop)] = value
    return values

def nfrdef_relations_values(rschema, objtype, props):
    values = _rdef_values(rschema, objtype, props)
    relations = ['X %s %%(%s)s' % (attr, attr) for attr in sorted(values)]
    return relations, values

def frdef_relations_values(rschema, objtype, props):
    values = _rdef_values(rschema, objtype, props)
    default = values['default']
    del values['default']
    if default is not None:
        if default is False:
            default = u''
        elif not isinstance(default, unicode):
            default = unicode(default)
    values['defaultval'] = default
    relations = ['X %s %%(%s)s' % (attr, attr) for attr in sorted(values)]
    return relations, values


def __rdef2rql(genmap, rschema, subjtype=None, objtype=None, props=None,
               groupmap=None):
    if subjtype is None:
        assert objtype is None
        assert props is None
        targets = sorted(rschema.rdefs)
    else:
        assert not objtype is None
        targets = [(subjtype, objtype)]
    # relation schema
    if rschema.final:
        etype = 'CWAttribute'
    else:
        etype = 'CWRelation'
    for subjtype, objtype in targets:
        if props is None:
            _props = rschema.rdef(subjtype, objtype)
        else:
            _props = props
        # don't serialize infered relations
        if _props.get('infered'):
            continue
        gen = genmap[rschema.final]
        for rql, values in gen(rschema, subjtype, objtype, _props):
            yield rql, values
        # no groupmap means "no security insertion"
        if groupmap:
            for rql, args in _erperms2rql(_props, groupmap):
                args['st'] = str(subjtype)
                args['rt'] = str(rschema)
                args['ot'] = str(objtype)
                yield rql + 'X is %s, X from_entity ST, X to_entity OT, '\
                      'X relation_type RT, RT name %%(rt)s, ST name %%(st)s, '\
                      'OT name %%(ot)s' % etype, args


def schema2rql(schema, skip=None, allow=None):
    """return a list of rql insert statements to enter the schema in the
    database as CWRType and CWEType entities
    """
    assert not (skip is not None and allow is not None), \
           'can\'t use both skip and allow'
    all = schema.entities() + schema.relations()
    if skip is not None:
        return chain(*[erschema2rql(schema[t]) for t in all if not t in skip])
    elif allow is not None:
        return chain(*[erschema2rql(schema[t]) for t in all if t in allow])
    return chain(*[erschema2rql(schema[t]) for t in all])

def erschema2rql(erschema, groupmap):
    if isinstance(erschema, schemamod.EntitySchema):
        return eschema2rql(erschema, groupmap=groupmap)
    return rschema2rql(erschema, groupmap=groupmap)

def eschema2rql(eschema, groupmap=None):
    """return a list of rql insert statements to enter an entity schema
    in the database as an CWEType entity
    """
    relations, values = eschema_relations_values(eschema)
    # NOTE: 'specializes' relation can't be inserted here since there's no
    # way to make sure the parent type is inserted before the child type
    yield 'INSERT CWEType X: %s' % ','.join(relations) , values
    # entity permissions
    if groupmap is not None:
        for rql, args in _erperms2rql(eschema, groupmap):
            args['name'] = str(eschema)
            yield rql + 'X is CWEType, X name %(name)s', args

def specialize2rql(schema):
    for eschema in schema.entities():
        for rql, kwargs in eschemaspecialize2rql(eschema):
            yield rql, kwargs

def eschemaspecialize2rql(eschema):
    specialized_type = eschema.specializes()
    if specialized_type:
        values = {'x': eschema.type, 'et': specialized_type.type}
        yield 'SET X specializes ET WHERE X name %(x)s, ET name %(et)s', values

def rschema2rql(rschema, addrdef=True, groupmap=None):
    """return a list of rql insert statements to enter a relation schema
    in the database as an CWRType entity
    """
    if rschema.type == 'has_text':
        return
    relations, values = rschema_relations_values(rschema)
    yield 'INSERT CWRType X: %s' % ','.join(relations), values
    if addrdef:
        for rql, values in rdef2rql(rschema, groupmap=groupmap):
            yield rql, values

def rdef2rql(rschema, subjtype=None, objtype=None, props=None, groupmap=None):
    genmap = {True: frdef2rql, False: nfrdef2rql}
    return __rdef2rql(genmap, rschema, subjtype, objtype, props, groupmap)


_LOCATE_RDEF_RQL0 = 'X relation_type ER,X from_entity SE,X to_entity OE'
_LOCATE_RDEF_RQL1 = 'SE name %(se)s,ER name %(rt)s,OE name %(oe)s'

def frdef2rql(rschema, subjtype, objtype, props):
    relations, values = frdef_relations_values(rschema, objtype, props)
    relations.append(_LOCATE_RDEF_RQL0)
    values.update({'se': str(subjtype), 'rt': str(rschema), 'oe': str(objtype)})
    yield 'INSERT CWAttribute X: %s WHERE %s' % (','.join(relations), _LOCATE_RDEF_RQL1), values
    for rql, values in rdefrelations2rql(rschema, subjtype, objtype, props):
        yield rql + ', EDEF is CWAttribute', values

def nfrdef2rql(rschema, subjtype, objtype, props):
    relations, values = nfrdef_relations_values(rschema, objtype, props)
    relations.append(_LOCATE_RDEF_RQL0)
    values.update({'se': str(subjtype), 'rt': str(rschema), 'oe': str(objtype)})
    yield 'INSERT CWRelation X: %s WHERE %s' % (','.join(relations), _LOCATE_RDEF_RQL1), values
    for rql, values in rdefrelations2rql(rschema, subjtype, objtype, props):
        yield rql + ', EDEF is CWRelation', values

def rdefrelations2rql(rschema, subjtype, objtype, props):
    iterators = []
    for constraint in props.constraints:
        iterators.append(constraint2rql(rschema, subjtype, objtype, constraint))
    return chain(*iterators)

def constraint2rql(rschema, subjtype, objtype, constraint):
    values = {'ctname': unicode(constraint.type()),
              'value': unicode(constraint.serialize()),
              'rt': str(rschema), 'se': str(subjtype), 'oe': str(objtype)}
    yield 'INSERT CWConstraint X: X value %(value)s, X cstrtype CT, EDEF constrained_by X WHERE \
CT name %(ctname)s, EDEF relation_type ER, EDEF from_entity SE, EDEF to_entity OE, \
ER name %(rt)s, SE name %(se)s, OE name %(oe)s', values


def _erperms2rql(erschema, groupmap):
    """return rql insert statements to enter the entity or relation
    schema's permissions in the database as
    [read|add|delete|update]_permission relations between CWEType/CWRType
    and CWGroup entities
    """
    for action in erschema.ACTIONS:
        for group_or_rqlexpr in erschema.action_permissions(action):
            if isinstance(group_or_rqlexpr, basestring):
                # group
                try:
                    yield ('SET X %s_permission Y WHERE Y eid %%(g)s, ' % action,
                           {'g': groupmap[group_or_rqlexpr]})
                except KeyError:
                    continue
            else:
                # rqlexpr
                rqlexpr = group_or_rqlexpr
                yield ('INSERT RQLExpression E: E expression %%(e)s, E exprtype %%(t)s, '
                       'E mainvars %%(v)s, X %s_permission E WHERE ' % action,
                       {'e': unicode(rqlexpr.expression),
                        'v': unicode(rqlexpr.mainvars),
                        't': unicode(rqlexpr.__class__.__name__)})


def updateeschema2rql(eschema):
    relations, values = eschema_relations_values(eschema)
    values['et'] = eschema.type
    yield 'SET %s WHERE X is CWEType, X name %%(et)s' % ','.join(relations), values

def updaterschema2rql(rschema):
    relations, values = rschema_relations_values(rschema)
    values['rt'] = rschema.type
    yield 'SET %s WHERE X is CWRType, X name %%(rt)s' % ','.join(relations), values

def updaterdef2rql(rschema, subjtype=None, objtype=None, props=None):
    genmap = {True: updatefrdef2rql, False: updatenfrdef2rql}
    return __rdef2rql(genmap, rschema, subjtype, objtype, props)

def updatefrdef2rql(rschema, subjtype, objtype, props):
    relations, values = frdef_relations_values(rschema, objtype, props)
    values.update({'se': subjtype, 'rt': str(rschema), 'oe': objtype})
    yield 'SET %s WHERE %s, %s, X is CWAttribute' % (','.join(relations),
                                                     _LOCATE_RDEF_RQL0,
                                                     _LOCATE_RDEF_RQL1), values

def updatenfrdef2rql(rschema, subjtype, objtype, props):
    relations, values = nfrdef_relations_values(rschema, objtype, props)
    values.update({'se': subjtype, 'rt': str(rschema), 'oe': objtype})
    yield 'SET %s WHERE %s, %s, X is CWRelation' % (','.join(relations),
                                                    _LOCATE_RDEF_RQL0,
                                                    _LOCATE_RDEF_RQL1), values
