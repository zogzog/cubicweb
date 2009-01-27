"""Base class for entity objects manipulated in clients

:organization: Logilab
:copyright: 2001-2008 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

from logilab.common import interface
from logilab.common.compat import all
from logilab.common.decorators import cached
from logilab.mtconverter import TransformData, TransformError
from rql.utils import rqlvar_maker

from cubicweb import Unauthorized
from cubicweb.vregistry import autoselectors
from cubicweb.rset import ResultSet
from cubicweb.common.appobject import AppRsetObject
from cubicweb.common.registerers import id_registerer
from cubicweb.common.selectors import yes
from cubicweb.common.uilib import printable_value, html_escape, soup2xhtml
from cubicweb.common.mixins import MI_REL_TRIGGERS
from cubicweb.common.mttransforms import ENGINE
from cubicweb.schema import RQLVocabularyConstraint, RQLConstraint, bw_normalize_etype

_marker = object()

def greater_card(rschema, subjtypes, objtypes, index):
    for subjtype in subjtypes:
        for objtype in objtypes:
            card = rschema.rproperty(subjtype, objtype, 'cardinality')[index]
            if card in '+*':
                return card
    return '1'


class RelationTags(object):
    
    MODE_TAGS = frozenset(('link', 'create'))
    CATEGORY_TAGS = frozenset(('primary', 'secondary', 'generic', 'generated',
                               'inlineview'))

    def __init__(self, eclass, tagdefs):
        self.eclass = eclass
        self._tagdefs = {}
        for relation, tags in tagdefs.iteritems():
            # tags must become a set
            if isinstance(tags, basestring):
                tags = set((tags,))
            elif not isinstance(tags, set):
                tags = set(tags)
            # relation must become a 3-uple (rtype, targettype, role)
            if isinstance(relation, basestring):
                self._tagdefs[(relation, '*', 'subject')] = tags
                self._tagdefs[(relation, '*', 'object')] = tags
            elif len(relation) == 1: # useful ?
                self._tagdefs[(relation[0], '*', 'subject')] = tags
                self._tagdefs[(relation[0], '*', 'object')] = tags
            elif len(relation) == 2:
                rtype, ttype = relation
                ttype = bw_normalize_etype(ttype) # XXX bw compat
                self._tagdefs[rtype, ttype, 'subject'] = tags
                self._tagdefs[rtype, ttype, 'object'] = tags
            elif len(relation) == 3:
                relation = list(relation)  # XXX bw compat
                relation[1] = bw_normalize_etype(relation[1])
                self._tagdefs[tuple(relation)] = tags
            else:
                raise ValueError('bad rtag definition (%r)' % (relation,))
        

    def __initialize__(self):
        # eclass.[*]schema are only set when registering
        self.schema = self.eclass.schema
        eschema = self.eschema = self.eclass.e_schema
        rtags = self._tagdefs
        # expand wildcards in rtags and add automatic tags
        for rschema, tschemas, role in sorted(eschema.relation_definitions(True)):
            rtype = rschema.type
            star_tags = rtags.pop((rtype, '*', role), set())
            for tschema in tschemas:
                tags = rtags.setdefault((rtype, tschema.type, role), set(star_tags))
                if role == 'subject':
                    X, Y = eschema, tschema
                    card = rschema.rproperty(X, Y, 'cardinality')[0]
                    composed = rschema.rproperty(X, Y, 'composite') == 'object'
                else:
                    X, Y = tschema, eschema
                    card = rschema.rproperty(X, Y, 'cardinality')[1]
                    composed = rschema.rproperty(X, Y, 'composite') == 'subject'
                # set default category tags if needed
                if not tags & self.CATEGORY_TAGS:
                    if card in '1+':
                        if not rschema.is_final() and composed:
                            category = 'generated'
                        elif rschema.is_final() and (
                            rschema.type.endswith('_format')
                            or rschema.type.endswith('_encoding')):
                            category = 'generated'
                        else:
                            category = 'primary'
                    elif rschema.is_final():
                        if (rschema.type.endswith('_format')
                            or rschema.type.endswith('_encoding')):
                            category = 'generated'
                        else:
                            category = 'secondary'
                    else: 
                        category = 'generic'
                    tags.add(category)
                if not tags & self.MODE_TAGS:
                    if card in '?1':
                        # by default, suppose link mode if cardinality doesn't allow
                        # more than one relation
                        mode = 'link'
                    elif rschema.rproperty(X, Y, 'composite') == role:
                        # if self is composed of the target type, create mode
                        mode = 'create'
                    else:
                        # link mode by default
                        mode = 'link'
                    tags.add(mode)

    def _default_target(self, rschema, role='subject'):
        eschema = self.eschema
        if role == 'subject':
            return eschema.subject_relation(rschema).objects(eschema)[0]
        else:
            return eschema.object_relation(rschema).subjects(eschema)[0]

    # dict compat
    def __getitem__(self, key):
        if isinstance(key, basestring):
            key = (key,)
        return self.get_tags(*key)

    __contains__ = __getitem__
    
    def get_tags(self, rtype, targettype=None, role='subject'):
        rschema = self.schema.rschema(rtype)
        if targettype is None:
            tschema = self._default_target(rschema, role)
        else:
            tschema = self.schema.eschema(targettype)
        return self._tagdefs[(rtype, tschema.type, role)]

    __call__ = get_tags
    
    def get_mode(self, rtype, targettype=None, role='subject'):
        # XXX: should we make an assertion on rtype not being final ?
        # assert not rschema.is_final()
        tags = self.get_tags(rtype, targettype, role)
        # do not change the intersection order !
        modes = tags & self.MODE_TAGS
        assert len(modes) == 1
        return modes.pop()

    def get_category(self, rtype, targettype=None, role='subject'):
        tags = self.get_tags(rtype, targettype, role)
        categories = tags & self.CATEGORY_TAGS
        assert len(categories) == 1
        return categories.pop()

    def is_inlined(self, rtype, targettype=None, role='subject'):
        # return set(('primary', 'secondary')) & self.get_tags(rtype, targettype)
        return 'inlineview' in self.get_tags(rtype, targettype, role)


class metaentity(autoselectors):
    """this metaclass sets the relation tags on the entity class
    and deals with the `widgets` attribute
    """
    def __new__(mcs, name, bases, classdict):
        # collect baseclass' rtags
        tagdefs = {}
        widgets = {}
        for base in bases:
            tagdefs.update(getattr(base, '__rtags__', {}))
            widgets.update(getattr(base, 'widgets', {}))
        # update with the class' own rtgas
        tagdefs.update(classdict.get('__rtags__', {}))
        widgets.update(classdict.get('widgets', {}))
        # XXX decide whether or not it's a good idea to replace __rtags__
        #     good point: transparent support for inheritance levels >= 2
        #     bad point: we loose the information of which tags are specific
        #                to this entity class
        classdict['__rtags__'] = tagdefs
        classdict['widgets'] = widgets
        eclass = super(metaentity, mcs).__new__(mcs, name, bases, classdict)
        # adds the "rtags" attribute
        eclass.rtags = RelationTags(eclass, tagdefs)
        return eclass


class Entity(AppRsetObject, dict):
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
                         cardinality
    """
    __metaclass__ = metaentity
    __registry__ = 'etypes'
    __registerer__ = id_registerer
    __selectors__ = (yes,)
    widgets = {}
    id = None
    e_schema = None
    eid = None
    rest_attr = None
    skip_copy_for = ()

    @classmethod
    def registered(cls, registry):
        """build class using descriptor at registration time"""
        assert cls.id is not None
        super(Entity, cls).registered(registry)
        if cls.id != 'Any':
            cls.__initialize__()
        return cls
                
    MODE_TAGS = set(('link', 'create'))
    CATEGORY_TAGS = set(('primary', 'secondary', 'generic', 'generated')) # , 'metadata'))
    @classmethod
    def __initialize__(cls):
        """initialize a specific entity class by adding descriptors to access
        entity type's attributes and relations
        """
        etype = cls.id
        assert etype != 'Any', etype
        cls.e_schema = eschema = cls.schema.eschema(etype)
        for rschema, _ in eschema.attribute_definitions():
            if rschema.type == 'eid':
                continue
            setattr(cls, rschema.type, Attribute(rschema.type))
        mixins = []
        for rschema, _, x in eschema.relation_definitions():
            if (rschema, x) in MI_REL_TRIGGERS:
                mixin = MI_REL_TRIGGERS[(rschema, x)]
                if not (issubclass(cls, mixin) or mixin in mixins): # already mixed ?
                    mixins.append(mixin)
                for iface in getattr(mixin, '__implements__', ()):
                    if not interface.implements(cls, iface):
                        interface.extend(cls, iface)
            if x == 'subject':
                setattr(cls, rschema.type, SubjectRelation(rschema))
            else:
                attr = 'reverse_%s' % rschema.type
                setattr(cls, attr, ObjectRelation(rschema))
        if mixins:
            cls.__bases__ = tuple(mixins + [p for p in cls.__bases__ if not p is object])
            cls.debug('plugged %s mixins on %s', mixins, etype)
        cls.rtags.__initialize__()
    
    @classmethod
    def fetch_rql(cls, user, restriction=None, fetchattrs=None, mainvar='X',
                  settype=True, ordermethod='fetch_order'):
        """return a rql to fetch all entities of the class type"""
        restrictions = restriction or []
        if settype:
            restrictions.append('%s is %s' % (mainvar, cls.id))
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
                rschema = eschema.subject_relation(attr)
            except KeyError:
                cls.warning('skipping fetch_attr %s defined in %s (not found in schema)',
                            attr, cls.id)
                continue
            if not user.matching_groups(rschema.get_groups('read')):
                continue
            var = varmaker.next()
            selection.append(var)
            restriction = '%s %s %s' % (mainvar, attr, var)
            restrictions.append(restriction)
            if not rschema.is_final():
                # XXX this does not handle several destination types
                desttype = rschema.objects(eschema.type)[0]
                card = rschema.rproperty(eschema, desttype, 'cardinality')[0]
                if card not in '?1':
                    selection.pop()
                    restrictions.pop()
                    continue
                if card == '?':
                    restrictions[-1] += '?' # left outer join if not mandatory
                destcls = cls.vreg.etype_class(desttype)
                destcls._fetch_restrictions(var, varmaker, destcls.fetch_attrs,
                                            selection, orderby, restrictions,
                                            user, ordermethod, visited=visited)
            orderterm = getattr(cls, ordermethod)(attr, var)
            if orderterm:
                orderby.append(orderterm)
        return selection, orderby, restrictions

    def __init__(self, req, rset, row=None, col=0):
        AppRsetObject.__init__(self, req, rset)
        dict.__init__(self)
        self.row, self.col = row, col
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
            int(self.eid)
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
        res = dict(zip(('type', 'source', 'extid'), self.req.describe(self.eid)))
        res['source'] = self.req.source_defs()[res['source']]
        return res

    def clear_local_perm_cache(self, action):
        for rqlexpr in self.e_schema.get_rqlexprs(action):
            self.req.local_perm_cache.pop((rqlexpr.eid, (('x', self.eid),)), None)

    def check_perm(self, action):
        self.e_schema.check_perm(self.req, action, self.eid)

    def has_perm(self, action):
        return self.e_schema.has_perm(self.req, action, self.eid)
        
    def view(self, vid, __registry='views', **kwargs):
        """shortcut to apply a view on this entity"""
        return self.vreg.render(__registry, vid, self.req, rset=self.rset,
                                row=self.row, col=self.col, **kwargs)

    def absolute_url(self, method=None, **kwargs):
        """return an absolute url to view this entity"""
        # in linksearch mode, we don't want external urls else selecting
        # the object for use in the relation is tricky
        # XXX search_state is web specific
        if getattr(self.req, 'search_state', ('normal',))[0] == 'normal':
            kwargs['base_url'] = self.metainformation()['source'].get('base-url')
        if method is None or method == 'view':
            kwargs['_restpath'] = self.rest_path()
        else:
            kwargs['rql'] = 'Any X WHERE X eid %s' % self.eid
        return self.build_url(method, **kwargs)

    def rest_path(self):
        """returns a REST-like (relative) path for this entity"""
        mainattr, needcheck = self._rest_attr_info()
        etype = str(self.e_schema)
        if mainattr == 'eid':
            value = self.eid
        else:
            value = getattr(self, mainattr)
            if value is None:
                return '%s/eid/%s' % (etype.lower(), self.eid)
        if needcheck:
            # make sure url is not ambiguous
            rql = 'Any COUNT(X) WHERE X is %s, X %s %%(value)s' % (etype, mainattr)
            if value is not None:
                nbresults = self.req.execute(rql, {'value' : value})[0][0]
                # may an assertion that nbresults is not 0 would be a good idea
                if nbresults != 1: # no ambiguity
                    return '%s/eid/%s' % (etype.lower(), self.eid)
        return '%s/%s' % (etype.lower(), self.req.url_quote(value))

    @classmethod
    def _rest_attr_info(cls):
        mainattr, needcheck = 'eid', True
        if cls.rest_attr:
            mainattr = cls.rest_attr
            needcheck = not cls.e_schema.has_unique_values(mainattr)
        else:
            for rschema in cls.e_schema.subject_relations():
                if rschema.is_final() and rschema != 'eid' and cls.e_schema.has_unique_values(rschema):
                    mainattr = str(rschema)
                    needcheck = False
                    break
        if mainattr == 'eid':
            needcheck = False
        return mainattr, needcheck

    @cached
    def formatted_attrs(self):
        """returns the list of attributes which have some format information
        (i.e. rich text strings)
        """
        attrs = []
        for rschema, attrschema in self.e_schema.attribute_definitions():
            if attrschema.type == 'String' and self.has_format(rschema):
                attrs.append(rschema.type)
        return attrs
        
    def format(self, attr):
        """return the mime type format for an attribute (if specified)"""
        return getattr(self, '%s_format' % attr, None)
    
    def text_encoding(self, attr):
        """return the text encoding for an attribute, default to site encoding
        """
        encoding = getattr(self, '%s_encoding' % attr, None)
        return encoding or self.vreg.property_value('ui.encoding')

    def has_format(self, attr):
        """return true if this entity's schema has a format field for the given
        attribute
        """
        return self.e_schema.has_subject_relation('%s_format' % attr)
    
    def has_text_encoding(self, attr):
        """return true if this entity's schema has ab encoding field for the
        given attribute
        """
        return self.e_schema.has_subject_relation('%s_encoding' % attr)

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
        props = self.e_schema.rproperties(attr)
        if attrtype == 'String':
            # internalinalized *and* formatted string such as schema
            # description...
            if props.get('internationalizable'):
                value = self.req._(value)
            attrformat = self.format(attr)
            if attrformat:
                return self.mtc_transform(value, attrformat, format,
                                          self.req.encoding)
        elif attrtype == 'Bytes':
            attrformat = self.format(attr)
            if attrformat:
                try:
                    encoding = getattr(self, '%s_encoding' % attr)
                except AttributeError:
                    encoding = self.req.encoding
                return self.mtc_transform(value.getvalue(), attrformat, format,
                                          encoding)
            return u''
        value = printable_value(self.req, attrtype, value, props, displaytime)
        if format == 'text/html':
            value = html_escape(value)
        return value

    def mtc_transform(self, data, format, target_format, encoding,
                      _engine=ENGINE):
        trdata = TransformData(data, format, encoding, appobject=self)
        data = _engine.convert(trdata, target_format).decode()
        if format == 'text/html':
            data = soup2xhtml(data, self.req.encoding)                
        return data
    
    # entity cloning ##########################################################

    def copy_relations(self, ceid):
        """copy relations of the object with the given eid on this object

        By default meta and composite relations are skipped.
        Overrides this if you want another behaviour
        """
        assert self.has_eid()
        execute = self.req.execute
        for rschema in self.e_schema.subject_relations():
            if rschema.meta or rschema.is_final():
                continue
            # skip already defined relations
            if getattr(self, rschema.type):
                continue
            if rschema.type in self.skip_copy_for:
                continue
            if rschema.type == 'in_state':
                # if the workflow is defining an initial state (XXX AND we are
                # not in the managers group? not done to be more consistent)
                # don't try to copy in_state
                if execute('Any S WHERE S state_of ET, ET initial_state S,'
                           'ET name %(etype)s', {'etype': str(self.e_schema)}):
                    continue
            # skip composite relation
            if self.e_schema.subjrproperty(rschema, 'composite'):
                continue
            # skip relation with card in ?1 else we either change the copied
            # object (inlined relation) or inserting some inconsistency
            if self.e_schema.subjrproperty(rschema, 'cardinality')[1] in '?1':
                continue
            rql = 'SET X %s V WHERE X eid %%(x)s, Y eid %%(y)s, Y %s V' % (
                rschema.type, rschema.type)
            execute(rql, {'x': self.eid, 'y': ceid}, ('x', 'y'))
            self.clear_related_cache(rschema.type, 'subject')
        for rschema in self.e_schema.object_relations():
            if rschema.meta:
                continue
            # skip already defined relations
            if getattr(self, 'reverse_%s' % rschema.type):
                continue
            # skip composite relation
            if self.e_schema.objrproperty(rschema, 'composite'):
                continue
            # skip relation with card in ?1 else we either change the copied
            # object (inlined relation) or inserting some inconsistency
            if self.e_schema.objrproperty(rschema, 'cardinality')[0] in '?1':
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
                         {'x': self.eid}, [(self.id,)])
        return self.req.decorate_rset(rset)
                       
    def to_complete_relations(self):
        """by default complete final relations to when calling .complete()"""
        for rschema in self.e_schema.subject_relations():
            if rschema.is_final():
                continue
            if len(rschema.objects(self.e_schema)) > 1:
                # ambigous relations, the querier doesn't handle
                # outer join correctly in this case
                continue
            if rschema.inlined:
                matching_groups = self.req.user.matching_groups
                if matching_groups(rschema.get_groups('read')) and \
                   all(matching_groups(es.get_groups('read'))
                       for es in rschema.objects(self.e_schema)):
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
            if not self.req.user.matching_groups(rschema.get_groups('read')) \
                   or attrschema.type == 'Password':
                self[attr] = None
                continue
            yield attr
            
    def complete(self, attributes=None, skip_bytes=True):
        """complete this entity by adding missing attributes (i.e. query the
        repository to fill the entity)

        :type skip_bytes: bool
        :param skip_bytes:
          if true, attribute of type Bytes won't be considered
        """
        assert self.has_eid()
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
                if role == 'subject':
                    targettype = rschema.objects(self.e_schema)[0]
                    card = rschema.rproperty(self.e_schema, targettype,
                                             'cardinality')[0]
                    if card == '1':
                        rql.append('%s %s %s' % (V, rtype, var))
                    else: # '?"
                        rql.append('%s %s %s?' % (V, rtype, var))
                else:
                    targettype = rschema.subjects(self.e_schema)[1]
                    card = rschema.rproperty(self.e_schema, targettype,
                                             'cardinality')[1]
                    if card == '1':
                        rql.append('%s %s %s' % (var, rtype, V))
                    else: # '?"
                        rql.append('%s? %s %s' % (var, rtype, V))
                assert card in '1?', '%s %s %s %s' % (self.e_schema, rtype,
                                                      role, card)
                selected.append(((rtype, role), var))
        if selected:
            # select V, we need it as the left most selected variable
            # if some outer join are included to fetch inlined relations
            rql = 'Any %s,%s %s' % (V, ','.join(var for attr, var in selected),
                                    ','.join(rql))
            execute = getattr(self.req, 'unsafe_execute', self.req.execute)
            rset = execute(rql, {'x': self.eid}, 'x', build_descr=False)[0]
            # handle attributes
            for i in xrange(1, lastattr):
                self[str(selected[i-1][0])] = rset[i]
            # handle relations
            for i in xrange(lastattr, len(rset)):
                rtype, x = selected[i-1][0]
                value = rset[i]
                if value is None:
                    rrset = ResultSet([], rql, {'x': self.eid})
                    self.req.decorate_rset(rrset)
                else:
                    rrset = self.req.eid_rset(value)
                self.set_related_cache(rtype, x, rrset)
                
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
            # XXX should we really use unsafe_execute here??
            execute = getattr(self.req, 'unsafe_execute', self.req.execute)
            try:
                rset = execute(rql, {'x': self.eid}, 'x')
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
                        self[name] = value = self.req._('unaccessible')
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
        rset = self.req.execute(rql, {'x': self.eid}, 'x')
        self.set_related_cache(rtype, role, rset)
        return self.related(rtype, role, limit, entities)

    def related_rql(self, rtype, role='subject'):
        rschema = self.schema[rtype]
        if role == 'subject':
            targettypes = rschema.objects(self.e_schema)
            restriction = 'E eid %%(x)s, E %s X' % rtype
            card = greater_card(rschema, (self.e_schema,), targettypes, 0)
        else:
            targettypes = rschema.subjects(self.e_schema)
            restriction = 'E eid %%(x)s, X %s E' % rtype
            card = greater_card(rschema, targettypes, (self.e_schema,), 1)
        if len(targettypes) > 1:
            fetchattrs_list = []
            for ttype in targettypes:
                etypecls = self.vreg.etype_class(ttype)
                fetchattrs_list.append(set(etypecls.fetch_attrs))
            fetchattrs = reduce(set.intersection, fetchattrs_list)
            rql = etypecls.fetch_rql(self.req.user, [restriction], fetchattrs,
                                     settype=False)
        else:
            etypecls = self.vreg.etype_class(targettypes[0])
            rql = etypecls.fetch_rql(self.req.user, [restriction], settype=False)
        # optimisation: remove ORDERBY if cardinality is 1 or ? (though
        # greater_card return 1 for those both cases)
        if card == '1':
            if ' ORDERBY ' in rql:
                rql = '%s WHERE %s' % (rql.split(' ORDERBY ', 1)[0],
                                       rql.split(' WHERE ', 1)[1])
        elif not ' ORDERBY ' in rql:
            args = tuple(rql.split(' WHERE ', 1))
            rql = '%s ORDERBY Z DESC WHERE X modification_date Z, %s' % args
        return rql
    
    # generic vocabulary methods ##############################################

    def vocabulary(self, rtype, role='subject', limit=None):
        """vocabulary functions must return a list of couples
        (label, eid) that will typically be used to fill the
        edition view's combobox.
        
        If `eid` is None in one of these couples, it should be
        interpreted as a separator in case vocabulary results are grouped
        """
        try:
            vocabfunc = getattr(self, '%s_%s_vocabulary' % (role, rtype))
        except AttributeError:
            vocabfunc = getattr(self, '%s_relation_vocabulary' % role)
        # NOTE: it is the responsibility of `vocabfunc` to sort the result
        #       (direclty through RQL or via a python sort). This is also
        #       important because `vocabfunc` might return a list with
        #       couples (label, None) which act as separators. In these
        #       cases, it doesn't make sense to sort results afterwards.
        return vocabfunc(rtype, limit)
            
    def subject_relation_vocabulary(self, rtype, limit=None):
        """defaut vocabulary method for the given relation, looking for
        relation's object entities (i.e. self is the subject)
        """
        if isinstance(rtype, basestring):
            rtype = self.schema.rschema(rtype)
        done = None
        assert not rtype.is_final(), rtype
        if self.has_eid():
            done = set(e.eid for e in getattr(self, str(rtype)))
        result = []
        rsetsize = None
        for objtype in rtype.objects(self.e_schema):
            if limit is not None:
                rsetsize = limit - len(result)
            result += self.relation_vocabulary(rtype, objtype, 'subject',
                                               rsetsize, done)
            if limit is not None and len(result) >= limit:
                break
        return result

    def object_relation_vocabulary(self, rtype, limit=None):
        """defaut vocabulary method for the given relation, looking for
        relation's subject entities (i.e. self is the object)
        """
        if isinstance(rtype, basestring):
            rtype = self.schema.rschema(rtype)
        done = None
        if self.has_eid():
            done = set(e.eid for e in getattr(self, 'reverse_%s' % rtype))
        result = []
        rsetsize = None
        for subjtype in rtype.subjects(self.e_schema):
            if limit is not None:
                rsetsize = limit - len(result)
            result += self.relation_vocabulary(rtype, subjtype, 'object',
                                               rsetsize, done)
            if limit is not None and len(result) >= limit:
                break
        return result

    def relation_vocabulary(self, rtype, targettype, role,
                            limit=None, done=None):
        if done is None:
            done = set()
        req = self.req
        rset = self.unrelated(rtype, targettype, role, limit)
        res = []
        for entity in rset.entities():
            if entity.eid in done:
                continue
            done.add(entity.eid)
            res.append((entity.view('combobox'), entity.eid))
        return res

    def unrelated_rql(self, rtype, targettype, role, ordermethod=None,
                      vocabconstraints=True):
        """build a rql to fetch `targettype` entities unrelated to this entity
        using (rtype, role) relation
        """
        ordermethod = ordermethod or 'fetch_unrelated_order'
        if isinstance(rtype, basestring):
            rtype = self.schema.rschema(rtype)
        if role == 'subject':
            evar, searchedvar = 'S', 'O'
            subjtype, objtype = self.e_schema, targettype
        else:
            searchedvar, evar = 'S', 'O'
            objtype, subjtype = self.e_schema, targettype
        if self.has_eid():
            restriction = ['NOT S %s O' % rtype, '%s eid %%(x)s' % evar]
        else:
            restriction = []
        constraints = rtype.rproperty(subjtype, objtype, 'constraints')
        if vocabconstraints:
            # RQLConstraint is a subclass for RQLVocabularyConstraint, so they
            # will be included as well
            restriction += [cstr.restriction for cstr in constraints
                            if isinstance(cstr, RQLVocabularyConstraint)]
        else:
            restriction += [cstr.restriction for cstr in constraints
                            if isinstance(cstr, RQLConstraint)]
        etypecls = self.vreg.etype_class(targettype)
        rql = etypecls.fetch_rql(self.req.user, restriction,
                                 mainvar=searchedvar, ordermethod=ordermethod)
        # ensure we have an order defined
        if not ' ORDERBY ' in rql:
            before, after = rql.split(' WHERE ', 1)
            rql = '%s ORDERBY %s WHERE %s' % (before, searchedvar, after)
        return rql
    
    def unrelated(self, rtype, targettype, role='subject', limit=None,
                  ordermethod=None):
        """return a result set of target type objects that may be related
        by a given relation, with self as subject or object
        """
        rql = self.unrelated_rql(rtype, targettype, role, ordermethod)
        if limit is not None:
            before, after = rql.split(' WHERE ', 1)
            rql = '%s LIMIT %s WHERE %s' % (before, limit, after)
        if self.has_eid():
            return self.req.execute(rql, {'x': self.eid})
        return self.req.execute(rql)
        
    # relations cache handling ################################################
    
    def relation_cached(self, rtype, role):
        """return true if the given relation is already cached on the instance
        """
        return '%s_%s' % (rtype, role) in self._related_cache
    
    def related_cache(self, rtype, role, entities=True, limit=None):
        """return values for the given relation if it's cached on the instance,
        else raise `KeyError`
        """
        res = self._related_cache['%s_%s' % (rtype, role)][entities]
        if limit:
            if entities:
                res = res[:limit]
            else:
                res = res.limit(limit)
        return res
    
    def set_related_cache(self, rtype, role, rset, col=0):
        """set cached values for the given relation"""
        if rset:
            related = list(rset.entities(col))
            rschema = self.schema.rschema(rtype)
            if role == 'subject':
                rcard = rschema.rproperty(self.e_schema, related[0].e_schema,
                                          'cardinality')[1]
                target = 'object'
            else:
                rcard = rschema.rproperty(related[0].e_schema, self.e_schema,
                                          'cardinality')[0]
                target = 'subject'
            if rcard in '?1':
                for rentity in related:
                    rentity._related_cache['%s_%s' % (rtype, target)] = (self.as_rset(), [self])
        else:
            related = []
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
        
    # raw edition utilities ###################################################
    
    def set_attributes(self, **kwargs):
        assert kwargs
        relations = []
        for key in kwargs:
            relations.append('X %s %%(%s)s' % (key, key))
        # update current local object
        self.update(kwargs)
        # and now update the database
        kwargs['x'] = self.eid
        self.req.execute('SET %s WHERE X eid %%(x)s' % ','.join(relations),
                         kwargs, 'x')
            
    def delete(self):
        assert self.has_eid(), self.eid
        self.req.execute('DELETE %s X WHERE X eid %%(x)s' % self.e_schema,
                         {'x': self.eid})
    
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
        if self.req is None:
            _ = unicode
        else:
            _ = self.req._
        self.e_schema.check(self, creation=creation, _=_)

    def fti_containers(self, _done=None):
        if _done is None:
            _done = set()
        _done.add(self.eid)
        containers = tuple(self.e_schema.fulltext_containers())
        if containers:
            yielded = False
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
            if not yielded:
                yield self
        else:
            yield self
                    
    def get_words(self):
        """used by the full text indexer to get words to index

        this method should only be used on the repository side since it depends
        on the indexer package
        
        :rtype: list
        :return: the list of indexable word of this entity
        """
        from indexer.query_objects import tokenize
        words = []
        for rschema in self.e_schema.indexable_attributes():
            try:
                value = self.printable_value(rschema, format='text/plain')
            except TransformError, ex:
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
        # XXX bw compat
        # would be better to generate UPDATE queries than the current behaviour
        eobj.warning("deprecated usage, don't use 'entity.attr = val' notation)")
        eobj[self._attrname] = value


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
