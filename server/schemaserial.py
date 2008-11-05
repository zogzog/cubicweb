"""functions for schema / permissions (de)serialization using RQL

:organization: Logilab
:copyright: 2001-2008 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

from itertools import chain

from logilab.common.shellutils import ProgressBar

from yams import schema as schemamod, buildobjs as ybo

from cubicweb.schema import CONSTRAINTS, ETYPE_NAME_MAP

def group_mapping(cursor, interactive=True):
    """create a group mapping from an rql cursor

    A group mapping has standard group names as key (managers, owners at least)
    and the actual EGroup entity's eid as associated value.
    In interactive mode (the default), missing groups'eid will be prompted
    from the user.
    """
    res = {}
    for eid, name in cursor.execute('Any G, N WHERE G is EGroup, G name N'):
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

# schema / perms deserialization ##############################################

def deserialize_schema(schema, session):
    """return a schema according to information stored in an rql database
    as ERType and EEType entities
    """
    # print 'reading schema from the database...'
    index = {}
    permsdict = deserialize_ertype_permissions(session)
    schema.reading_from_database = True
    for eid, etype, desc, meta in session.execute('Any X, N, D, M WHERE '
                                                  'X is EEType, X name N, '
                                                  'X description D, X meta M',
                                                  build_descr=False):
        # base types are already in the schema, skip them
        if etype in schemamod.BASE_TYPES:
            # just set the eid
            eschema = schema.eschema(etype)
            eschema.eid = eid
            index[eid] = eschema
            continue
        if etype in ETYPE_NAME_MAP: # XXX <2.45 bw compat
            print 'fixing etype name from %s to %s' % (etype, ETYPE_NAME_MAP[etype])
            # can't use write rql queries at this point, use raw sql
            session.system_sql('UPDATE EEType SET name=%(n)s WHERE eid=%(x)s',
                               {'x': eid, 'n': ETYPE_NAME_MAP[etype]})
            session.system_sql('UPDATE entities SET type=%(n)s WHERE type=%(x)s',
                               {'x': etype, 'n': ETYPE_NAME_MAP[etype]})
            session.commit(False)
            try:
                session.system_sql('UPDATE deleted_entities SET type=%(n)s WHERE type=%(x)s',
                                   {'x': etype, 'n': ETYPE_NAME_MAP[etype]})
            except:
                pass
            tocleanup = [eid]
            tocleanup += (eid for eid, (eidetype, uri, extid) in session.repo._type_source_cache.items()
                          if etype == eidetype)
            session.repo.clear_caches(tocleanup)
            session.commit(False)
            etype = ETYPE_NAME_MAP[etype]
        etype = ybo.EntityType(name=etype, description=desc, meta=meta, eid=eid)
        eschema = schema.add_entity_type(etype)
        index[eid] = eschema
        set_perms(eschema, permsdict.get(eid, {}))
    try:
        rset = session.execute('Any XN, ETN WHERE X is EEType, X name XN, '
                               'X specializes ET, ET name ETN')
    except: # `specializes` relation not available for versions prior to 2.50
        session.rollback(False)
    else:
        for etype, stype in rset:
            eschema = schema.eschema(etype)
            seschema = schema.eschema(stype)
            eschema._specialized_type = stype
            seschema._specialized_by.append(etype)
    for eid, rtype, desc, meta, sym, il in session.execute(
        'Any X,N,D,M,S,I WHERE X is ERType, X name N, X description D, '
        'X meta M, X symetric S, X inlined I', build_descr=False):
        try:
            # bw compat: fulltext_container added in 2.47
            ft_container = session.execute('Any FTC WHERE X eid %(x)s, X fulltext_container FTC',
                                           {'x': eid}).rows[0][0]
        except:
            ft_container = None
            session.rollback(False)
        rtype = ybo.RelationType(name=rtype, description=desc, meta=bool(meta),
                                 symetric=bool(sym), inlined=bool(il),
                                 fulltext_container=ft_container, eid=eid)
        rschema = schema.add_relation_type(rtype)
        index[eid] = rschema
        set_perms(rschema, permsdict.get(eid, {}))        
    cstrsdict = deserialize_rdef_constraints(session)
    for values in session.execute(
        'Any X,SE,RT,OE,CARD,ORD,DESC,IDX,FTIDX,I18N,DFLT WHERE X is EFRDef,'
        'X relation_type RT, X cardinality CARD, X ordernum ORD, X indexed IDX,'
        'X description DESC, X internationalizable I18N, X defaultval DFLT,'
        'X fulltextindexed FTIDX, X from_entity SE, X to_entity OE',
        build_descr=False):
        rdefeid, seid, reid, teid, card, ord, desc, idx, ftidx, i18n, default = values
        constraints = cstrsdict.get(rdefeid, ())
        frometype = index[seid].type
        rtype = index[reid].type
        toetype = index[teid].type
        rdef = ybo.RelationDefinition(frometype, rtype, toetype, cardinality=card,
                                  order=ord, description=desc, 
                                  constraints=constraints,
                                  indexed=idx, fulltextindexed=ftidx,
                                  internationalizable=i18n,
                                  default=default, eid=rdefeid)
        schema.add_relation_def(rdef)
    for values in session.execute(
        'Any X,SE,RT,OE,CARD,ORD,DESC,C WHERE X is ENFRDef, X relation_type RT,'
        'X cardinality CARD, X ordernum ORD, X description DESC, '
        'X from_entity SE, X to_entity OE, X composite C', build_descr=False):
        rdefeid, seid, reid, teid, card, ord, desc, c = values
        frometype = index[seid].type
        rtype = index[reid].type
        toetype = index[teid].type
        constraints = cstrsdict.get(rdefeid, ())
        rdef = ybo.RelationDefinition(frometype, rtype, toetype, cardinality=card,
                                  order=ord, description=desc, 
                                  composite=c, constraints=constraints,
                                  eid=rdefeid)
        schema.add_relation_def(rdef)
    schema.infer_specialization_rules()
    session.commit()
    schema.reading_from_database = False


def deserialize_ertype_permissions(session):
    """return sect action:groups associations for the given
    entity or relation schema with its eid, according to schema's
    permissions stored in the database as [read|add|delete|update]_permission
    relations between EEType/ERType and EGroup entities
    """
    res = {}
    for action in ('read', 'add', 'update', 'delete'):
        rql = 'Any E,N WHERE G is EGroup, G name N, E %s_permission G' % action
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
    for action in erschema.ACTIONS:
        actperms = []
        for something in permsdict.get(action, ()):
            if isinstance(something, tuple):
                actperms.append(erschema.rql_expression(*something))
            else: # group name
                actperms.append(something)
        erschema.set_permissions(action, actperms)            


def deserialize_rdef_constraints(session):
    """return the list of relation definition's constraints as instances"""
    res = {}
    for rdefeid, ceid, ct, val in session.execute(
        'Any E, X,TN,V WHERE E constrained_by X, X is EConstraint, '
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
    print 'serializing the schema, this may take some time'
    eschemas = schema.entities()
    aller = eschemas + schema.relations()
    if not verbose:
        pb_size = len(aller) + len(CONSTRAINTS) + len([x for x in eschemas if x.specializes()])
        pb = ProgressBar(pb_size)
    for cstrtype in CONSTRAINTS:
        rql = 'INSERT EConstraintType X: X name "%s"' % cstrtype
        if verbose:
            print rql
        cursor.execute(rql)
        if not verbose:
            pb.update()
    groupmap = group_mapping(cursor, interactive=False)
    for ertype in aller:
        # skip eid and has_text relations
        if ertype in ('eid', 'identity', 'has_text',):
            pb.update()
            continue
        for rql, kwargs in erschema2rql(schema[ertype]):
            if verbose:
                print rql % kwargs
            cursor.execute(rql, kwargs)
        for rql, kwargs in erperms2rql(schema[ertype], groupmap):
            if verbose:
                print rql
            cursor.execute(rql, kwargs)
        if not verbose:
            pb.update()
    for rql, kwargs in specialize2rql(schema):
        if verbose:
            print rql % kwargs
        cursor.execute(rql, kwargs)
        if not verbose:
            pb.update()
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
        'meta': erschema.meta,
        'final': erschema.is_final(),
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
    values['final'] = rschema.is_final()
    values['symetric'] = rschema.symetric
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
    for prop, default in rschema.rproperty_defs(objtype).iteritems():
        if prop in ('eid', 'constraints', 'uid', 'infered'):
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

    
def __rdef2rql(genmap, rschema, subjtype=None, objtype=None, props=None):
    if subjtype is None:
        assert objtype is None
        assert props is None
        targets = rschema.iter_rdefs()
    else:
        assert not objtype is None
        targets = [(subjtype, objtype)]
    for subjtype, objtype in targets:
        if props is None:
            _props = rschema.rproperties(subjtype, objtype)
        else:
            _props = props
        # don't serialize infered relations
        if _props.get('infered'):
            continue
        gen = genmap[rschema.is_final()]
        for rql, values in gen(rschema, subjtype, objtype, _props):
            yield rql, values


def schema2rql(schema, skip=None, allow=None):
    """return a list of rql insert statements to enter the schema in the
    database as ERType and EEType entities
    """
    assert not (skip is not None and allow is not None), \
           'can\'t use both skip and allow'
    all = schema.entities() + schema.relations()
    if skip is not None:
        return chain(*[erschema2rql(schema[t]) for t in all if not t in skip])
    elif allow is not None:
        return chain(*[erschema2rql(schema[t]) for t in all if t in allow])
    return chain(*[erschema2rql(schema[t]) for t in all])
        
def erschema2rql(erschema):
    if isinstance(erschema, schemamod.EntitySchema):
        return eschema2rql(erschema)
    return rschema2rql(erschema)

def eschema2rql(eschema):
    """return a list of rql insert statements to enter an entity schema
    in the database as an EEType entity
    """
    relations, values = eschema_relations_values(eschema)
    # NOTE: 'specializes' relation can't be inserted here since there's no
    # way to make sure the parent type is inserted before the child type
    yield 'INSERT EEType X: %s' % ','.join(relations) , values

def specialize2rql(schema):
    for eschema in schema.entities():
        for rql, kwargs in eschemaspecialize2rql(eschema):
            yield rql, kwargs

def eschemaspecialize2rql(eschema):
    specialized_type = eschema.specializes()
    if specialized_type:
        values = {'x': eschema.type, 'et': specialized_type.type}
        yield 'SET X specializes ET WHERE X name %(x)s, ET name %(et)s', values

def rschema2rql(rschema, addrdef=True):
    """return a list of rql insert statements to enter a relation schema
    in the database as an ERType entity
    """
    if rschema.type == 'has_text':
        return
    relations, values = rschema_relations_values(rschema)
    yield 'INSERT ERType X: %s' % ','.join(relations), values
    if addrdef:
        for rql, values in rdef2rql(rschema):
            yield rql, values
            
def rdef2rql(rschema, subjtype=None, objtype=None, props=None):
    genmap = {True: frdef2rql, False: nfrdef2rql}
    return __rdef2rql(genmap, rschema, subjtype, objtype, props)


_LOCATE_RDEF_RQL0 = 'X relation_type ER,X from_entity SE,X to_entity OE'
_LOCATE_RDEF_RQL1 = 'SE name %(se)s,ER name %(rt)s,OE name %(oe)s'

def frdef2rql(rschema, subjtype, objtype, props):
    relations, values = frdef_relations_values(rschema, objtype, props)
    relations.append(_LOCATE_RDEF_RQL0)
    values.update({'se': str(subjtype), 'rt': str(rschema), 'oe': str(objtype)})
    yield 'INSERT EFRDef X: %s WHERE %s' % (','.join(relations), _LOCATE_RDEF_RQL1), values
    for rql, values in rdefrelations2rql(rschema, subjtype, objtype, props):
        yield rql + ', EDEF is EFRDef', values
            
def nfrdef2rql(rschema, subjtype, objtype, props):
    relations, values = nfrdef_relations_values(rschema, objtype, props)
    relations.append(_LOCATE_RDEF_RQL0)
    values.update({'se': str(subjtype), 'rt': str(rschema), 'oe': str(objtype)})
    yield 'INSERT ENFRDef X: %s WHERE %s' % (','.join(relations), _LOCATE_RDEF_RQL1), values
    for rql, values in rdefrelations2rql(rschema, subjtype, objtype, props):
        yield rql + ', EDEF is ENFRDef', values
                
def rdefrelations2rql(rschema, subjtype, objtype, props):
    iterators = []
    for constraint in props['constraints']:
        iterators.append(constraint2rql(rschema, subjtype, objtype, constraint))
    return chain(*iterators)

def constraint2rql(rschema, subjtype, objtype, constraint):
    values = {'ctname': unicode(constraint.type()),
              'value': unicode(constraint.serialize()),
              'rt': str(rschema), 'se': str(subjtype), 'oe': str(objtype)}
    yield 'INSERT EConstraint X: X value %(value)s, X cstrtype CT, EDEF constrained_by X WHERE \
CT name %(ctname)s, EDEF relation_type ER, EDEF from_entity SE, EDEF to_entity OE, \
ER name %(rt)s, SE name %(se)s, OE name %(oe)s', values

def perms2rql(schema, groupmapping):
    """return rql insert statements to enter the schema's permissions in
    the database as [read|add|delete|update]_permission relations between
    EEType/ERType and EGroup entities

    groupmapping is a dictionnary mapping standard group names to
    eids
    """
    for etype in sorted(schema.entities()):
        yield erperms2rql(schema[etype], groupmapping)
    for rtype in sorted(schema.relations()):
        yield erperms2rql(schema[rtype], groupmapping)

def erperms2rql(erschema, groupmapping):
    """return rql insert statements to enter the entity or relation
    schema's permissions in the database as
    [read|add|delete|update]_permission relations between EEType/ERType
    and EGroup entities
    """
    etype = isinstance(erschema, schemamod.EntitySchema) and 'EEType' or 'ERType'
    for action in erschema.ACTIONS:
        for group in sorted(erschema.get_groups(action)):
            try:
                yield ('SET X %s_permission Y WHERE X is %s, X name "%s", Y eid %s'
                       % (action, etype, erschema, groupmapping[group]), None)
            except KeyError:
                continue
        for rqlexpr in sorted(erschema.get_rqlexprs(action)):
            yield ('INSERT RQLExpression E: E expression %%(e)s, E exprtype %%(t)s, '
                   'E mainvars %%(v)s, X %s_permission E '
                   'WHERE X is %s, X name "%s"' % (action, etype, erschema),
                   {'e': unicode(rqlexpr.expression), 'v': unicode(rqlexpr.mainvars),
                    't': unicode(rqlexpr.__class__.__name__)})


def updateeschema2rql(eschema):
    relations, values = eschema_relations_values(eschema)
    values['et'] = eschema.type
    yield 'SET %s WHERE X is EEType, X name %%(et)s' % ','.join(relations), values

def updaterschema2rql(rschema):
    relations, values = rschema_relations_values(rschema)
    values['rt'] = rschema.type
    yield 'SET %s WHERE X is ERType, X name %%(rt)s' % ','.join(relations), values
            
def updaterdef2rql(rschema, subjtype=None, objtype=None, props=None):
    genmap = {True: updatefrdef2rql, False: updatenfrdef2rql}
    return __rdef2rql(genmap, rschema, subjtype, objtype, props)

def updatefrdef2rql(rschema, subjtype, objtype, props):
    relations, values = frdef_relations_values(rschema, objtype, props)
    values.update({'se': subjtype, 'rt': str(rschema), 'oe': objtype})
    yield 'SET %s WHERE %s, %s, X is EFRDef' % (','.join(relations),
                                                 _LOCATE_RDEF_RQL0,
                                                 _LOCATE_RDEF_RQL1), values
            
def updatenfrdef2rql(rschema, subjtype, objtype, props):
    relations, values = nfrdef_relations_values(rschema, objtype, props)
    values.update({'se': subjtype, 'rt': str(rschema), 'oe': objtype})
    yield 'SET %s WHERE %s, %s, X is ENFRDef' % (','.join(relations),
                                                 _LOCATE_RDEF_RQL0,
                                                 _LOCATE_RDEF_RQL1), values
