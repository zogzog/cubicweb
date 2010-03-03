"""functions for schema / permissions (de)serialization using RQL

:organization: Logilab
:copyright: 2001-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

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

def cstrtype_mapping(cursor):
    """cached constraint types mapping"""
    return dict(cursor.execute('Any T, X WHERE X is CWConstraintType, X name T'))

# schema / perms deserialization ##############################################
def deserialize_schema(schema, session):
    """return a schema according to information stored in an rql database
    as CWRType and CWEType entities
    """
    repo = session.repo
    dbhelper = repo.system_source.dbhelper
    # 3.6 migration
    sqlcu = session.pool['system']
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

def set_perms(erschema, permsdict):
    """set permissions on the given erschema according to the permission
    definition dictionary as built by deserialize_ertype_permissions for a
    given erschema's eid
    """
    # reset erschema permissions here to avoid getting yams default anyway
    erschema.permissions = dict((action, ()) for action in erschema.ACTIONS)
    try:
        thispermsdict = permsdict[erschema.eid]
    except KeyError:
        return
    for action, somethings in thispermsdict.iteritems():
        # XXX cw < 3.6.1 bw compat
        if isinstance(erschema, schemamod.RelationDefinitionSchema) and erschema.final and action == 'add':
            action = 'update'
        erschema.permissions[action] = tuple(
            isinstance(p, tuple) and erschema.rql_expression(*p) or p
            for p in somethings)


# schema / perms serialization ################################################

def serialize_schema(cursor, schema):
    """synchronize schema and permissions in the database according to
    current schema
    """
    quiet = os.environ.get('APYCOT_ROOT')
    if not quiet:
        _title = '-> storing the schema in the database '
        print _title,
    execute = cursor.unsafe_execute
    eschemas = schema.entities()
    aller = eschemas + schema.relations()
    if not quiet:
        pb_size = len(aller) + len(CONSTRAINTS) + len([x for x in eschemas if x.specializes()])
        pb = ProgressBar(pb_size, title=_title)
    else:
        pb = None
    groupmap = group_mapping(cursor, interactive=False)
    # serialize all entity types, assuring CWEType is serialized first
    eschemas.remove(schema.eschema('CWEType'))
    eschemas.insert(0, schema.eschema('CWEType'))
    for eschema in eschemas:
        execschemarql(execute, eschema, eschema2rql(eschema, groupmap))
        if pb is not None:
            pb.update()
    # serialize constraint types
    cstrtypemap = {}
    rql = 'INSERT CWConstraintType X: X name %(ct)s'
    for cstrtype in CONSTRAINTS:
        cstrtypemap[cstrtype] = execute(rql, {'ct': unicode(cstrtype)},
                                        build_descr=False)[0][0]
        if pb is not None:
            pb.update()
    # serialize relations
    for rschema in schema.relations():
        # skip virtual relations such as eid, has_text and identity
        if rschema in VIRTUAL_RTYPES:
            if pb is not None:
                pb.update()
            continue
        execschemarql(execute, rschema, rschema2rql(rschema, addrdef=False))
        if rschema.symmetric:
            rdefs = [rdef for k, rdef in rschema.rdefs.iteritems()
                     if (rdef.subject, rdef.object) == k]
        else:
            rdefs = rschema.rdefs.itervalues()
        for rdef in rdefs:
            execschemarql(execute, rdef,
                          rdef2rql(rdef, cstrtypemap, groupmap))
        if pb is not None:
            pb.update()
    for rql, kwargs in specialize2rql(schema):
        assert execute(rql, kwargs, build_descr=False)
        if pb is not None:
            pb.update()
    if not quiet:
        print


# high level serialization functions

def execschemarql(execute, schema, rqls):
    for rql, kwargs in rqls:
        kwargs['x'] = schema.eid
        rset = execute(rql, kwargs, build_descr=False)
        if schema.eid is None:
            schema.eid = rset[0][0]
        else:
            assert rset

def erschema2rql(erschema, groupmap):
    if isinstance(erschema, schemamod.EntitySchema):
        return eschema2rql(erschema, groupmap=groupmap)
    return rschema2rql(erschema, groupmap=groupmap)

def specialize2rql(schema):
    for eschema in schema.entities():
        if eschema.final:
            continue
        for rql, kwargs in eschemaspecialize2rql(eschema):
            yield rql, kwargs

# etype serialization

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
            yield rql, args

def eschema_relations_values(eschema):
    values = _ervalues(eschema)
    relations = ['X %s %%(%s)s' % (attr, attr) for attr in sorted(values)]
    return relations, values

def eschemaspecialize2rql(eschema):
    specialized_type = eschema.specializes()
    if specialized_type:
        values = {'x': eschema.eid, 'et': specialized_type.eid}
        yield 'SET X specializes ET WHERE X eid %(x)s, ET eid %(et)s', values

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

# rtype serialization

def rschema2rql(rschema, cstrtypemap=None, addrdef=True, groupmap=None):
    """return a list of rql insert statements to enter a relation schema
    in the database as an CWRType entity
    """
    if rschema.type == 'has_text':
        return
    relations, values = rschema_relations_values(rschema)
    yield 'INSERT CWRType X: %s' % ','.join(relations), values
    if addrdef:
        assert cstrtypemap
        # sort for testing purpose
        for rdef in sorted(rschema.rdefs.itervalues(),
                           key=lambda x: (x.subject, x.object)):
            for rql, values in rdef2rql(rdef, cstrtypemap, groupmap):
                yield rql, values

def rschema_relations_values(rschema):
    values = _ervalues(rschema)
    values['final'] = rschema.final
    values['symmetric'] = rschema.symmetric
    values['inlined'] = rschema.inlined
    if isinstance(rschema.fulltext_container, str):
        values['fulltext_container'] = unicode(rschema.fulltext_container)
    else:
        values['fulltext_container'] = rschema.fulltext_container
    relations = ['X %s %%(%s)s' % (attr, attr) for attr in sorted(values)]
    return relations, values

# rdef serialization

def rdef2rql(rdef, cstrtypemap, groupmap=None):
    # don't serialize infered relations
    if rdef.infered:
        return
    relations, values = _rdef_values(rdef)
    relations.append('X relation_type ER,X from_entity SE,X to_entity OE')
    values.update({'se': rdef.subject.eid, 'rt': rdef.rtype.eid, 'oe': rdef.object.eid})
    if rdef.final:
        etype = 'CWAttribute'
    else:
        etype = 'CWRelation'
    yield 'INSERT %s X: %s WHERE SE eid %%(se)s,ER eid %%(rt)s,OE eid %%(oe)s' % (
        etype, ','.join(relations), ), values
    for rql, values in constraints2rql(cstrtypemap, rdef.constraints):
        yield rql, values
    # no groupmap means "no security insertion"
    if groupmap:
        for rql, args in _erperms2rql(rdef, groupmap):
            yield rql, args

def _rdef_values(rdef):
    amap = {'order': 'ordernum', 'default': 'defaultval'}
    values = {}
    for prop, default in rdef.rproperty_defs(rdef.object).iteritems():
        if prop in ('eid', 'constraints', 'uid', 'infered', 'permissions'):
            continue
        value = getattr(rdef, prop)
        # XXX type cast really necessary?
        if prop in ('indexed', 'fulltextindexed', 'internationalizable'):
            value = bool(value)
        elif prop == 'ordernum':
            value = int(value)
        elif isinstance(value, str):
            value = unicode(value)
        if value is not None and prop == 'default':
            if value is False:
                value = u''
            if not isinstance(value, unicode):
                value = unicode(value)
        values[amap.get(prop, prop)] = value
    relations = ['X %s %%(%s)s' % (attr, attr) for attr in sorted(values)]
    return relations, values

def constraints2rql(cstrtypemap, constraints, rdefeid=None):
    for constraint in constraints:
        values = {'ct': cstrtypemap[constraint.type()],
                  'value': unicode(constraint.serialize()),
                  'x': rdefeid} # when not specified, will have to be set by the caller
        yield 'INSERT CWConstraint X: X value %(value)s, X cstrtype CT, EDEF constrained_by X WHERE \
CT eid %(ct)s, EDEF eid %(x)s', values


def _erperms2rql(erschema, groupmap):
    """return rql insert statements to enter the entity or relation
    schema's permissions in the database as
    [read|add|delete|update]_permission relations between CWEType/CWRType
    and CWGroup entities
    """
    for action in erschema.ACTIONS:
        try:
            grantedto = erschema.action_permissions(action)
        except KeyError:
            # may occurs when modifying persistent schema
            continue
        for group_or_rqlexpr in grantedto:
            if isinstance(group_or_rqlexpr, basestring):
                # group
                try:
                    yield ('SET X %s_permission Y WHERE Y eid %%(g)s, X eid %%(x)s' % action,
                           {'g': groupmap[group_or_rqlexpr]})
                except KeyError:
                    continue
            else:
                # rqlexpr
                rqlexpr = group_or_rqlexpr
                yield ('INSERT RQLExpression E: E expression %%(e)s, E exprtype %%(t)s, '
                       'E mainvars %%(v)s, X %s_permission E WHERE X eid %%(x)s' % action,
                       {'e': unicode(rqlexpr.expression),
                        'v': unicode(rqlexpr.mainvars),
                        't': unicode(rqlexpr.__class__.__name__)})

# update functions

def updateeschema2rql(eschema, eid):
    relations, values = eschema_relations_values(eschema)
    values['x'] = eid
    yield 'SET %s WHERE X eid %%(x)s' % ','.join(relations), values

def updaterschema2rql(rschema, eid):
    relations, values = rschema_relations_values(rschema)
    values['x'] = eid
    yield 'SET %s WHERE X eid %%(x)s' % ','.join(relations), values

def updaterdef2rql(rdef, eid):
    relations, values = _rdef_values(rdef)
    values['x'] = eid
    yield 'SET %s WHERE X eid %%(x)s' % ','.join(relations), values
