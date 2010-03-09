"""Base class for entity objects manipulated in clients

:organization: Logilab
:copyright: 2001-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

from warnings import warn

from logilab.common import interface
from logilab.common.compat import all
from logilab.common.decorators import cached
from logilab.mtconverter import TransformData, TransformError, xml_escape

from rql.utils import rqlvar_maker

from cubicweb import Unauthorized, typed_eid
from cubicweb.rset import ResultSet
from cubicweb.selectors import yes
from cubicweb.appobject import AppObject
from cubicweb.req import _check_cw_unsafe
from cubicweb.schema import RQLVocabularyConstraint, RQLConstraint
from cubicweb.rqlrewrite import RQLRewriter

from cubicweb.uilib import printable_value, soup2xhtml
from cubicweb.mixins import MI_REL_TRIGGERS
from cubicweb.mttransforms import ENGINE

_marker = object()

def greater_card(rschema, subjtypes, objtypes, index):
    for subjtype in subjtypes:
        for objtype in objtypes:
            card = rschema.rdef(subjtype, objtype).cardinality[index]
            if card in '+*':
                return card
    return '1'


class Entity(AppObject, dict):
    """an entity instance has e_schema automagically set on
    the class and instances has access to their issuing cursor.

    A property is set for each attribute and relation on each entity's type
    class. Becare that among attributes, 'eid' is *NEITHER* stored in the
    dict containment (which acts as a cache for other attributes dynamically
    fetched)

    :type e_schema: `cubicweb.schema.EntitySchema`
    :ivar e_schema: the entity's schema

    :type rest_var: str
    :cvar rest_var: indicates which attribute should be used to build REST urls
                    If None is specified, the first non-meta attribute will
                    be used

    :type skip_copy_for: list
    :cvar skip_copy_for: a list of relations that should be skipped when copying
                         this kind of entity. Note that some relations such
                         as composite relations or relations that have '?1' as object
                         cardinality are always skipped. 
    """
    __registry__ = 'etypes'
    __select__ = yes()

    # class attributes that must be set in class definition
    rest_attr = None
    fetch_attrs = None
    skip_copy_for = ('in_state',)
    # class attributes set automatically at registration time
    e_schema = None

    @classmethod
    def __initialize__(cls, schema):
        """initialize a specific entity class by adding descriptors to access
        entity type's attributes and relations
        """
        etype = cls.__regid__
        assert etype != 'Any', etype
        cls.e_schema = eschema = schema.eschema(etype)
        for rschema, _ in eschema.attribute_definitions():
            if rschema.type == 'eid':
                continue
            setattr(cls, rschema.type, Attribute(rschema.type))
        mixins = []
        for rschema, _, role in eschema.relation_definitions():
            if (rschema, role) in MI_REL_TRIGGERS:
                mixin = MI_REL_TRIGGERS[(rschema, role)]
                if not (issubclass(cls, mixin) or mixin in mixins): # already mixed ?
                    mixins.append(mixin)
                for iface in getattr(mixin, '__implements__', ()):
                    if not interface.implements(cls, iface):
                        interface.extend(cls, iface)
            if role == 'subject':
                setattr(cls, rschema.type, SubjectRelation(rschema))
            else:
                attr = 'reverse_%s' % rschema.type
                setattr(cls, attr, ObjectRelation(rschema))
        if mixins:
            # see etype class instantation in cwvreg.ETypeRegistry.etype_class method:
            # due to class dumping, cls is the generated top level class with actual
            # user class as (only) parent. Since we want to be able to override mixins
            # method from this user class, we have to take care to insert mixins after that
            # class
            #
            # note that we don't plug mixins as user class parent since it causes pb
            # with some cases of entity classes inheritance.
            mixins.insert(0, cls.__bases__[0])
            mixins += cls.__bases__[1:]
            cls.__bases__ = tuple(mixins)
            cls.info('plugged %s mixins on %s', mixins, cls)

    @classmethod
    def fetch_rql(cls, user, restriction=None, fetchattrs=None, mainvar='X',
                  settype=True, ordermethod='fetch_order'):
        """return a rql to fetch all entities of the class type"""
        restrictions = restriction or []
        if settype:
            restrictions.append('%s is %s' % (mainvar, cls.__regid__))
        if fetchattrs is None:
            fetchattrs = cls.fetch_attrs
        selection = [mainvar]
        orderby = []
        # start from 26 to avoid possible conflicts with X
        varmaker = rqlvar_maker(index=26)
        cls._fetch_restrictions(mainvar, varmaker, fetchattrs, selection,
                                orderby, restrictions, user, ordermethod)
        rql = 'Any %s' % ','.join(selection)
        if orderby:
            rql +=  ' ORDERBY %s' % ','.join(orderby)
        rql += ' WHERE %s' % ', '.join(restrictions)
        return rql

    @classmethod
    def _fetch_restrictions(cls, mainvar, varmaker, fetchattrs,
                            selection, orderby, restrictions, user,
                            ordermethod='fetch_order', visited=None):
        eschema = cls.e_schema
        if visited is None:
            visited = set((eschema.type,))
        elif eschema.type in visited:
            # avoid infinite recursion
            return
        else:
            visited.add(eschema.type)
        _fetchattrs = []
        for attr in fetchattrs:
            try:
                rschema = eschema.subjrels[attr]
            except KeyError:
                cls.warning('skipping fetch_attr %s defined in %s (not found in schema)',
                            attr, cls.__regid__)
                continue
            rdef = eschema.rdef(attr)
            if not user.matching_groups(rdef.get_groups('read')):
                continue
            var = varmaker.next()
            selection.append(var)
            restriction = '%s %s %s' % (mainvar, attr, var)
            restrictions.append(restriction)
            if not rschema.final:
                # XXX this does not handle several destination types
                desttype = rschema.objects(eschema.type)[0]
                card = rdef.cardinality[0]
                if card not in '?1':
                    cls.warning('bad relation %s specified in fetch attrs for %s',
                                 attr, cls)
                    selection.pop()
                    restrictions.pop()
                    continue
                # XXX we need outer join in case the relation is not mandatory
                # (card == '?')  *or if the entity is being added*, since in
                # that case the relation may still be missing. As we miss this
                # later information here, systematically add it.
                restrictions[-1] += '?'
                # XXX user._cw.vreg iiiirk
                destcls = user._cw.vreg['etypes'].etype_class(desttype)
                destcls._fetch_restrictions(var, varmaker, destcls.fetch_attrs,
                                            selection, orderby, restrictions,
                                            user, ordermethod, visited=visited)
            orderterm = getattr(cls, ordermethod)(attr, var)
            if orderterm:
                orderby.append(orderterm)
        return selection, orderby, restrictions

    @classmethod
    @cached
    def _rest_attr_info(cls):
        mainattr, needcheck = 'eid', True
        if cls.rest_attr:
            mainattr = cls.rest_attr
            needcheck = not cls.e_schema.has_unique_values(mainattr)
        else:
            for rschema in cls.e_schema.subject_relations():
                if rschema.final and rschema != 'eid' and cls.e_schema.has_unique_values(rschema):
                    mainattr = str(rschema)
                    needcheck = False
                    break
        if mainattr == 'eid':
            needcheck = False
        return mainattr, needcheck

    def __init__(self, req, rset=None, row=None, col=0):
        AppObject.__init__(self, req, rset=rset, row=row, col=col)
        dict.__init__(self)
        self._related_cache = {}
        if rset is not None:
            self.eid = rset[row][col]
        else:
            self.eid = None
        self._is_saved = True

    def __repr__(self):
        return '<Entity %s %s %s at %s>' % (
            self.e_schema, self.eid, self.keys(), id(self))

    def __nonzero__(self):
        return True

    def __hash__(self):
        return id(self)

    def __cmp__(self, other):
        raise NotImplementedError('comparison not implemented for %s' % self.__class__)

    def pre_add_hook(self):
        """hook called by the repository before doing anything to add the entity
        (before_add entity hooks have not been called yet). This give the
        occasion to do weird stuff such as autocast (File -> Image for instance).

        This method must return the actual entity to be added.
        """
        return self

    def set_eid(self, eid):
        self.eid = self['eid'] = eid

    def has_eid(self):
        """return True if the entity has an attributed eid (False
        meaning that the entity has to be created
        """
        try:
            typed_eid(self.eid)
            return True
        except (ValueError, TypeError):
            return False

    def is_saved(self):
        """during entity creation, there is some time during which the entity
        has an eid attributed though it's not saved (eg during before_add_entity
        hooks). You can use this method to ensure the entity has an eid *and* is
        saved in its source.
        """
        return self.has_eid() and self._is_saved

    @cached
    def metainformation(self):
        res = dict(zip(('type', 'source', 'extid'), self._cw.describe(self.eid)))
        res['source'] = self._cw.source_defs()[res['source']]
        return res

    def clear_local_perm_cache(self, action):
        for rqlexpr in self.e_schema.get_rqlexprs(action):
            self._cw.local_perm_cache.pop((rqlexpr.eid, (('x', self.eid),)), None)

    def check_perm(self, action):
        self.e_schema.check_perm(self._cw, action, eid=self.eid)

    def has_perm(self, action):
        return self.e_schema.has_perm(self._cw, action, eid=self.eid)

    def view(self, __vid, __registry='views', **kwargs):
        """shortcut to apply a view on this entity"""
        view = self._cw.vreg[__registry].select(__vid, self._cw, rset=self.cw_rset,
                                                row=self.cw_row, col=self.cw_col,
                                                **kwargs)
        return view.render(row=self.cw_row, col=self.cw_col, **kwargs)

    def absolute_url(self, *args, **kwargs):
        """return an absolute url to view this entity"""
        # use *args since we don't want first argument to be "anonymous" to
        # avoid potential clash with kwargs
        if args:
            assert len(args) == 1, 'only 0 or 1 non-named-argument expected'
            method = args[0]
        else:
            method = None
        # in linksearch mode, we don't want external urls else selecting
        # the object for use in the relation is tricky
        # XXX search_state is web specific
        if getattr(self._cw, 'search_state', ('normal',))[0] == 'normal':
            kwargs['base_url'] = self.metainformation()['source'].get('base-url')
        if method in (None, 'view'):
            try:
                kwargs['_restpath'] = self.rest_path(kwargs.get('base_url'))
            except TypeError:
                warn('[3.4] %s: rest_path() now take use_ext_eid argument, '
                     'please update' % self.__regid__, DeprecationWarning)
                kwargs['_restpath'] = self.rest_path()
        else:
            kwargs['rql'] = 'Any X WHERE X eid %s' % self.eid
        return self._cw.build_url(method, **kwargs)

    def rest_path(self, use_ext_eid=False):
        """returns a REST-like (relative) path for this entity"""
        mainattr, needcheck = self._rest_attr_info()
        etype = str(self.e_schema)
        path = etype.lower()
        if mainattr != 'eid':
            value = getattr(self, mainattr)
            if value is None or unicode(value) == u'':
                mainattr = 'eid'
                path += '/eid'
            elif needcheck:
                # make sure url is not ambiguous
                try:
                    nbresults = self.__unique
                except AttributeError:
                    rql = 'Any COUNT(X) WHERE X is %s, X %s %%(value)s' % (
                        etype, mainattr)
                    nbresults = self.__unique = self._cw.execute(rql, {'value' : value})[0][0]
                if nbresults != 1: # ambiguity?
                    mainattr = 'eid'
                    path += '/eid'
        if mainattr == 'eid':
            if use_ext_eid:
                value = self.metainformation()['extid']
            else:
                value = self.eid
        return '%s/%s' % (path, self._cw.url_quote(value))

    def attr_metadata(self, attr, metadata):
        """return a metadata for an attribute (None if unspecified)"""
        value = getattr(self, '%s_%s' % (attr, metadata), None)
        if value is None and metadata == 'encoding':
            value = self._cw.vreg.property_value('ui.encoding')
        return value

    def printable_value(self, attr, value=_marker, attrtype=None,
                        format='text/html', displaytime=True):
        """return a displayable value (i.e. unicode string) which may contains
        html tags
        """
        attr = str(attr)
        if value is _marker:
            value = getattr(self, attr)
        if isinstance(value, basestring):
            value = value.strip()
        if value is None or value == '': # don't use "not", 0 is an acceptable value
            return u''
        if attrtype is None:
            attrtype = self.e_schema.destination(attr)
        props = self.e_schema.rdef(attr)
        if attrtype == 'String':
            # internalinalized *and* formatted string such as schema
            # description...
            if props.internationalizable:
                value = self._cw._(value)
            attrformat = self.attr_metadata(attr, 'format')
            if attrformat:
                return self.mtc_transform(value, attrformat, format,
                                          self._cw.encoding)
        elif attrtype == 'Bytes':
            attrformat = self.attr_metadata(attr, 'format')
            if attrformat:
                encoding = self.attr_metadata(attr, 'encoding')
                return self.mtc_transform(value.getvalue(), attrformat, format,
                                          encoding)
            return u''
        value = printable_value(self._cw, attrtype, value, props,
                                displaytime=displaytime)
        if format == 'text/html':
            value = xml_escape(value)
        return value

    def mtc_transform(self, data, format, target_format, encoding,
                      _engine=ENGINE):
        trdata = TransformData(data, format, encoding, appobject=self)
        data = _engine.convert(trdata, target_format).decode()
        if format == 'text/html':
            data = soup2xhtml(data, self._cw.encoding)
        return data

    # entity cloning ##########################################################

    def copy_relations(self, ceid):
        """copy relations of the object with the given eid on this
        object (this method is called on the newly created copy, and
        ceid designates the original entity).

        By default meta and composite relations are skipped.
        Overrides this if you want another behaviour
        """
        assert self.has_eid()
        execute = self._cw.execute
        for rschema in self.e_schema.subject_relations():
            if rschema.final or rschema.meta:
                continue
            # skip already defined relations
            if getattr(self, rschema.type):
                continue
            if rschema.type in self.skip_copy_for:
                continue
            # skip composite relation
            rdef = self.e_schema.rdef(rschema)
            if rdef.composite:
                continue
            # skip relation with card in ?1 else we either change the copied
            # object (inlined relation) or inserting some inconsistency
            if rdef.cardinality[1] in '?1':
                continue
            rql = 'SET X %s V WHERE X eid %%(x)s, Y eid %%(y)s, Y %s V' % (
                rschema.type, rschema.type)
            execute(rql, {'x': self.eid, 'y': ceid}, ('x', 'y'))
            self.clear_related_cache(rschema.type, 'subject')
        for rschema in self.e_schema.object_relations():
            if rschema.meta:
                continue
            # skip already defined relations
            if self.related(rschema.type, 'object'):
                continue
            rdef = self.e_schema.rdef(rschema, 'object')
            # skip composite relation
            if rdef.composite:
                continue
            # skip relation with card in ?1 else we either change the copied
            # object (inlined relation) or inserting some inconsistency
            if rdef.cardinality[0] in '?1':
                continue
            rql = 'SET V %s X WHERE X eid %%(x)s, Y eid %%(y)s, V %s Y' % (
                rschema.type, rschema.type)
            execute(rql, {'x': self.eid, 'y': ceid}, ('x', 'y'))
            self.clear_related_cache(rschema.type, 'object')

    # data fetching methods ###################################################

    @cached
    def as_rset(self):
        """returns a resultset containing `self` information"""
        rset = ResultSet([(self.eid,)], 'Any X WHERE X eid %(x)s',
                         {'x': self.eid}, [(self.__regid__,)])
        return self._cw.decorate_rset(rset)

    def to_complete_relations(self):
        """by default complete final relations to when calling .complete()"""
        for rschema in self.e_schema.subject_relations():
            if rschema.final:
                continue
            targets = rschema.objects(self.e_schema)
            if len(targets) > 1:
                # ambigous relations, the querier doesn't handle
                # outer join correctly in this case
                continue
            if rschema.inlined:
                matching_groups = self._cw.user.matching_groups
                rdef = rschema.rdef(self.e_schema, targets[0])
                if matching_groups(rdef.get_groups('read')) and \
                   all(matching_groups(e.get_groups('read')) for e in targets):
                    yield rschema, 'subject'

    def to_complete_attributes(self, skip_bytes=True):
        for rschema, attrschema in self.e_schema.attribute_definitions():
            # skip binary data by default
            if skip_bytes and attrschema.type == 'Bytes':
                continue
            attr = rschema.type
            if attr == 'eid':
                continue
            # password retreival is blocked at the repository server level
            rdef = rschema.rdef(self.e_schema, attrschema)
            if not self._cw.user.matching_groups(rdef.get_groups('read')) \
                   or attrschema.type == 'Password':
                self[attr] = None
                continue
            yield attr

    _cw_completed = False
    def complete(self, attributes=None, skip_bytes=True):
        """complete this entity by adding missing attributes (i.e. query the
        repository to fill the entity)

        :type skip_bytes: bool
        :param skip_bytes:
          if true, attribute of type Bytes won't be considered
        """
        assert self.has_eid()
        if self._cw_completed:
            return
        if attributes is None:
            self._cw_completed = True
        varmaker = rqlvar_maker()
        V = varmaker.next()
        rql = ['WHERE %s eid %%(x)s' % V]
        selected = []
        for attr in (attributes or self.to_complete_attributes(skip_bytes)):
            # if attribute already in entity, nothing to do
            if self.has_key(attr):
                continue
            # case where attribute must be completed, but is not yet in entity
            var = varmaker.next()
            rql.append('%s %s %s' % (V, attr, var))
            selected.append((attr, var))
        # +1 since this doen't include the main variable
        lastattr = len(selected) + 1
        if attributes is None:
            # fetch additional relations (restricted to 0..1 relations)
            for rschema, role in self.to_complete_relations():
                rtype = rschema.type
                if self.relation_cached(rtype, role):
                    continue
                var = varmaker.next()
                targettype = rschema.targets(self.e_schema, role)[0]
                rdef = rschema.role_rdef(self.e_schema, targettype, role)
                card = rdef.role_cardinality(role)
                assert card in '1?', '%s %s %s %s' % (self.e_schema, rtype,
                                                      role, card)
                if role == 'subject':
                    if card == '1':
                        rql.append('%s %s %s' % (V, rtype, var))
                    else:
                        rql.append('%s %s %s?' % (V, rtype, var))
                else:
                    if card == '1':
                        rql.append('%s %s %s' % (var, rtype, V))
                    else:
                        rql.append('%s? %s %s' % (var, rtype, V))
                selected.append(((rtype, role), var))
        if selected:
            # select V, we need it as the left most selected variable
            # if some outer join are included to fetch inlined relations
            rql = 'Any %s,%s %s' % (V, ','.join(var for attr, var in selected),
                                    ','.join(rql))
            rset = self._cw.execute(rql, {'x': self.eid}, 'x',
                                    build_descr=False)[0]
            # handle attributes
            for i in xrange(1, lastattr):
                self[str(selected[i-1][0])] = rset[i]
            # handle relations
            for i in xrange(lastattr, len(rset)):
                rtype, role = selected[i-1][0]
                value = rset[i]
                if value is None:
                    rrset = ResultSet([], rql, {'x': self.eid})
                    self._cw.decorate_rset(rrset)
                else:
                    rrset = self._cw.eid_rset(value)
                self.set_related_cache(rtype, role, rrset)

    def get_value(self, name):
        """get value for the attribute relation <name>, query the repository
        to get the value if necessary.

        :type name: str
        :param name: name of the attribute to get
        """
        try:
            value = self[name]
        except KeyError:
            if not self.is_saved():
                return None
            rql = "Any A WHERE X eid %%(x)s, X %s A" % name
            try:
                rset = self._cw.execute(rql, {'x': self.eid}, 'x')
            except Unauthorized:
                self[name] = value = None
            else:
                assert rset.rowcount <= 1, (self, rql, rset.rowcount)
                try:
                    self[name] = value = rset.rows[0][0]
                except IndexError:
                    # probably a multisource error
                    self.critical("can't get value for attribute %s of entity with eid %s",
                                  name, self.eid)
                    if self.e_schema.destination(name) == 'String':
                        # XXX (syt) imo emtpy string is better
                        self[name] = value = self._cw._('unaccessible')
                    else:
                        self[name] = value = None
        return value

    def related(self, rtype, role='subject', limit=None, entities=False):
        """returns a resultset of related entities

        :param role: is the role played by 'self' in the relation ('subject' or 'object')
        :param limit: resultset's maximum size
        :param entities: if True, the entites are returned; if False, a result set is returned
        """
        try:
            return self.related_cache(rtype, role, entities, limit)
        except KeyError:
            pass
        assert self.has_eid()
        rql = self.related_rql(rtype, role)
        rset = self._cw.execute(rql, {'x': self.eid}, 'x')
        self.set_related_cache(rtype, role, rset)
        return self.related(rtype, role, limit, entities)

    def related_rql(self, rtype, role='subject', targettypes=None):
        rschema = self._cw.vreg.schema[rtype]
        if role == 'subject':
            restriction = 'E eid %%(x)s, E %s X' % rtype
            if targettypes is None:
                targettypes = rschema.objects(self.e_schema)
            else:
                restriction += ', X is IN (%s)' % ','.join(targettypes)
            card = greater_card(rschema, (self.e_schema,), targettypes, 0)
        else:
            restriction = 'E eid %%(x)s, X %s E' % rtype
            if targettypes is None:
                targettypes = rschema.subjects(self.e_schema)
            else:
                restriction += ', X is IN (%s)' % ','.join(targettypes)
            card = greater_card(rschema, targettypes, (self.e_schema,), 1)
        if len(targettypes) > 1:
            fetchattrs_list = []
            for ttype in targettypes:
                etypecls = self._cw.vreg['etypes'].etype_class(ttype)
                fetchattrs_list.append(set(etypecls.fetch_attrs))
            fetchattrs = reduce(set.intersection, fetchattrs_list)
            rql = etypecls.fetch_rql(self._cw.user, [restriction], fetchattrs,
                                     settype=False)
        else:
            etypecls = self._cw.vreg['etypes'].etype_class(targettypes[0])
            rql = etypecls.fetch_rql(self._cw.user, [restriction], settype=False)
        # optimisation: remove ORDERBY if cardinality is 1 or ? (though
        # greater_card return 1 for those both cases)
        if card == '1':
            if ' ORDERBY ' in rql:
                rql = '%s WHERE %s' % (rql.split(' ORDERBY ', 1)[0],
                                       rql.split(' WHERE ', 1)[1])
        elif not ' ORDERBY ' in rql:
            args = rql.split(' WHERE ', 1)
            # if modification_date already retreived, we should use it instead
            # of adding another variable for sort. This should be be problematic
            # but it's actually with sqlserver, see ticket #694445
            if 'X modification_date ' in args[1]:
                var = args[1].split('X modification_date ', 1)[1].split(',', 1)[0]
                args.insert(1, var.strip())
                rql = '%s ORDERBY %s DESC WHERE %s' % tuple(args)
            else:
                rql = '%s ORDERBY Z DESC WHERE X modification_date Z, %s' % \
                      tuple(args)
        return rql

    # generic vocabulary methods ##############################################

    def unrelated_rql(self, rtype, targettype, role, ordermethod=None,
                      vocabconstraints=True):
        """build a rql to fetch `targettype` entities unrelated to this entity
        using (rtype, role) relation.

        Consider relation permissions so that returned entities may be actually
        linked by `rtype`.
        """
        ordermethod = ordermethod or 'fetch_unrelated_order'
        if isinstance(rtype, basestring):
            rtype = self._cw.vreg.schema.rschema(rtype)
        if role == 'subject':
            evar, searchedvar = 'S', 'O'
            subjtype, objtype = self.e_schema, targettype
        else:
            searchedvar, evar = 'S', 'O'
            objtype, subjtype = self.e_schema, targettype
        if self.has_eid():
            restriction = ['NOT S %s O' % rtype, '%s eid %%(x)s' % evar]
            args = {'x': self.eid}
            if role == 'subject':
                securitycheck_args = {'fromeid': self.eid}
            else:
                securitycheck_args = {'toeid': self.eid}
        else:
            restriction = []
            args = {}
            securitycheck_args = {}
        rdef = rtype.role_rdef(self.e_schema, targettype, role)
        insertsecurity = (rdef.has_local_role('add') and not
                          rdef.has_perm(self._cw, 'add', **securitycheck_args))
        # XXX consider constraint.mainvars to check if constraint apply
        if vocabconstraints:
            # RQLConstraint is a subclass for RQLVocabularyConstraint, so they
            # will be included as well
            restriction += [cstr.restriction for cstr in rdef.constraints
                            if isinstance(cstr, RQLVocabularyConstraint)]
        else:
            restriction += [cstr.restriction for cstr in rdef.constraints
                            if isinstance(cstr, RQLConstraint)]
        etypecls = self._cw.vreg['etypes'].etype_class(targettype)
        rql = etypecls.fetch_rql(self._cw.user, restriction,
                                 mainvar=searchedvar, ordermethod=ordermethod)
        # ensure we have an order defined
        if not ' ORDERBY ' in rql:
            before, after = rql.split(' WHERE ', 1)
            rql = '%s ORDERBY %s WHERE %s' % (before, searchedvar, after)
        if insertsecurity:
            rqlexprs = rdef.get_rqlexprs('add')
            rewriter = RQLRewriter(self._cw)
            rqlst = self._cw.vreg.parse(self._cw, rql, args)
            if not self.has_eid():
                existant = searchedvar
            else:
                existant = None # instead of 'SO', improve perfs
            for select in rqlst.children:
                rewriter.rewrite(select, [((searchedvar, searchedvar), rqlexprs)],
                                 select.solutions, args, existant)
            rql = rqlst.as_string()
        return rql, args

    def unrelated(self, rtype, targettype, role='subject', limit=None,
                  ordermethod=None):
        """return a result set of target type objects that may be related
        by a given relation, with self as subject or object
        """
        try:
            rql, args = self.unrelated_rql(rtype, targettype, role, ordermethod)
        except Unauthorized:
            return self._cw.empty_rset()
        if limit is not None:
            before, after = rql.split(' WHERE ', 1)
            rql = '%s LIMIT %s WHERE %s' % (before, limit, after)
        return self._cw.execute(rql, args, tuple(args))

    # relations cache handling ################################################

    def relation_cached(self, rtype, role):
        """return true if the given relation is already cached on the instance
        """
        return self._related_cache.get('%s_%s' % (rtype, role))

    def related_cache(self, rtype, role, entities=True, limit=None):
        """return values for the given relation if it's cached on the instance,
        else raise `KeyError`
        """
        res = self._related_cache['%s_%s' % (rtype, role)][entities]
        if limit is not None and limit < len(res):
            if entities:
                res = res[:limit]
            else:
                res = res.limit(limit)
        return res

    def set_related_cache(self, rtype, role, rset, col=0):
        """set cached values for the given relation"""
        if rset:
            related = list(rset.entities(col))
            rschema = self._cw.vreg.schema.rschema(rtype)
            if role == 'subject':
                rcard = rschema.rdef(self.e_schema, related[0].e_schema).cardinality[1]
                target = 'object'
            else:
                rcard = rschema.rdef(related[0].e_schema, self.e_schema).cardinality[0]
                target = 'subject'
            if rcard in '?1':
                for rentity in related:
                    rentity._related_cache['%s_%s' % (rtype, target)] = (
                        self.as_rset(), (self,))
        else:
            related = ()
        self._related_cache['%s_%s' % (rtype, role)] = (rset, related)

    def clear_related_cache(self, rtype=None, role=None):
        """clear cached values for the given relation or the entire cache if
        no relation is given
        """
        if rtype is None:
            self._related_cache = {}
        else:
            assert role
            self._related_cache.pop('%s_%s' % (rtype, role), None)

    def clear_all_caches(self):
        """flush all caches on this entity. Further attributes/relations access
        will triggers new database queries to get back values.

        If you use custom caches on your entity class (take care to @cached!),
        you should override this method to clear them as well.
        """
        # clear attributes cache
        haseid = 'eid' in self
        self._cw_completed = False
        self.clear()
        # set eid if it was in, else we may get nasty error while editing this
        # entity if it's bound to a repo session
        if haseid:
            self['eid'] = self.eid
        # clear relations cache
        for rschema, _, role in self.e_schema.relation_definitions():
            self.clear_related_cache(rschema.type, role)
        # rest path unique cache
        try:
            del self.__unique
        except AttributeError:
            pass

    # raw edition utilities ###################################################

    def set_attributes(self, **kwargs):
        assert kwargs
        _check_cw_unsafe(kwargs)
        relations = []
        for key in kwargs:
            relations.append('X %s %%(%s)s' % (key, key))
        # update current local object
        self.update(kwargs)
        # and now update the database
        kwargs['x'] = self.eid
        self._cw.execute('SET %s WHERE X eid %%(x)s' % ','.join(relations),
                         kwargs, 'x')

    def set_relations(self, **kwargs):
        """add relations to the given object. To set a relation where this entity
        is the object of the relation, use 'reverse_'<relation> as argument name.

        Values may be an entity, a list of entity, or None (meaning that all
        relations of the given type from or to this object should be deleted).
        """
        # XXX update cache
        _check_cw_unsafe(kwargs)
        for attr, values in kwargs.iteritems():
            if attr.startswith('reverse_'):
                restr = 'Y %s X' % attr[len('reverse_'):]
            else:
                restr = 'X %s Y' % attr
            if values is None:
                execute('DELETE %s WHERE X eid %%(x)s' % restr,
                        {'x': self.eid}, 'x')
                continue
            if not isinstance(values, (tuple, list, set, frozenset)):
                values = (values,)
            self._cw.execute('SET %s WHERE X eid %%(x)s, Y eid IN (%s)' % (
                restr, ','.join(str(r.eid) for r in values)),
                             {'x': self.eid}, 'x')

    def delete(self, **kwargs):
        assert self.has_eid(), self.eid
        self._cw.execute('DELETE %s X WHERE X eid %%(x)s' % self.e_schema,
                         {'x': self.eid}, **kwargs)

    # server side utilities ###################################################

    def set_defaults(self):
        """set default values according to the schema"""
        self._default_set = set()
        for attr, value in self.e_schema.defaults():
            if not self.has_key(attr):
                self[str(attr)] = value
                self._default_set.add(attr)

    def check(self, creation=False):
        """check this entity against its schema. Only final relation
        are checked here, constraint on actual relations are checked in hooks
        """
        # necessary since eid is handled specifically and yams require it to be
        # in the dictionary
        if self._cw is None:
            _ = unicode
        else:
            _ = self._cw._
        self.e_schema.check(self, creation=creation, _=_)

    def fti_containers(self, _done=None):
        if _done is None:
            _done = set()
        _done.add(self.eid)
        containers = tuple(self.e_schema.fulltext_containers())
        if containers:
            for rschema, target in containers:
                if target == 'object':
                    targets = getattr(self, rschema.type)
                else:
                    targets = getattr(self, 'reverse_%s' % rschema)
                for entity in targets:
                    if entity.eid in _done:
                        continue
                    for container in entity.fti_containers(_done):
                        yield container
                        yielded = True
        else:
            yield self

    def get_words(self):
        """used by the full text indexer to get words to index

        this method should only be used on the repository side since it depends
        on the logilab.db package

        :rtype: list
        :return: the list of indexable word of this entity
        """
        from logilab.db.fti import tokenize
        # take care to cases where we're modyfying the schema
        pending = self._cw.transaction_data.setdefault('pendingrdefs', set())
        words = []
        for rschema in self.e_schema.indexable_attributes():
            if (self.e_schema, rschema) in pending:
                continue
            try:
                value = self.printable_value(rschema, format='text/plain')
            except TransformError:
                continue
            except:
                self.exception("can't add value of %s to text index for entity %s",
                               rschema, self.eid)
                continue
            if value:
                words += tokenize(value)
        for rschema, role in self.e_schema.fulltext_relations():
            if role == 'subject':
                for entity in getattr(self, rschema.type):
                    words += entity.get_words()
            else: # if role == 'object':
                for entity in getattr(self, 'reverse_%s' % rschema.type):
                    words += entity.get_words()
        return words


# attribute and relation descriptors ##########################################

class Attribute(object):
    """descriptor that controls schema attribute access"""

    def __init__(self, attrname):
        assert attrname != 'eid'
        self._attrname = attrname

    def __get__(self, eobj, eclass):
        if eobj is None:
            return self
        return eobj.get_value(self._attrname)

    def __set__(self, eobj, value):
        eobj[self._attrname] = value
        if hasattr(eobj, 'edited_attributes'):
            eobj.edited_attributes.add(self._attrname)

class Relation(object):
    """descriptor that controls schema relation access"""
    _role = None # for pylint

    def __init__(self, rschema):
        self._rschema = rschema
        self._rtype = rschema.type

    def __get__(self, eobj, eclass):
        if eobj is None:
            raise AttributeError('%s cannot be only be accessed from instances'
                                 % self._rtype)
        return eobj.related(self._rtype, self._role, entities=True)

    def __set__(self, eobj, value):
        raise NotImplementedError


class SubjectRelation(Relation):
    """descriptor that controls schema relation access"""
    _role = 'subject'

class ObjectRelation(Relation):
    """descriptor that controls schema relation access"""
    _role = 'object'

from logging import getLogger
from cubicweb import set_log_methods
set_log_methods(Entity, getLogger('cubicweb.entity'))
