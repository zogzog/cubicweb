"""provide replacement classes for gae db module, so that a gae model can be
used as base for a cubicweb application by simply replacing ::

  from google.appengine.ext import db

by

  from cubicweb.goa import db

The db.model api should be fully featured by replacement classes, with the
following differences:

* all methods returning `google.appengine.ext.db.Model` instance(s) will return
  `cubicweb.goa.db.Model` instance instead (though you should see almost no
  difference since those instances have the same api)

* class methods returning model instance take a `req` as first argument, unless
  they are called through an instance, representing the current request
  (accessible through `self.req` on almost all objects)

* XXX no instance.<modelname>_set attributes, use instance.reverse_<attr name>
      instead
* XXX reference property always return a list of objects, not the instance
* XXX name/collection_name argument of properties constructor are ignored
* XXX ListProperty

:organization: Logilab
:copyright: 2008-2009 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

from copy import deepcopy

from logilab.common.decorators import cached, iclassmethod

from cubicweb import RequestSessionMixIn, Binary, entities
from cubicweb.rset import ResultSet
from cubicweb.entity import metaentity
from cubicweb.server.utils import crypt_password
from cubicweb.goa import MODE
from cubicweb.goa.dbinit import init_relations

from google.appengine.api.datastore import Get, Put, Key, Entity, Query
from google.appengine.api.datastore import NormalizeAndTypeCheck, RunInTransaction
from google.appengine.api.datastore_types import Text, Blob
from google.appengine.api.datastore_errors import BadKeyError

# XXX remove this dependancy
from google.appengine.ext import db


def rset_from_objs(req, objs, attrs=('eid',), rql=None, args=None):
    """return a ResultSet instance for list of objects"""
    if objs is None:
        objs = ()
    elif isinstance(objs, Entity):
        objs = (objs,)
    if rql is None:
        rql = 'Any X'
    rows = []
    description = []
    rset = ResultSet(rows, rql, args, description=description)
    vreg = req.vreg
    for i, obj in enumerate(objs):
        line = []
        linedescr = []
        eschema = vreg.schema.eschema(obj.kind())
        for j, attr in enumerate(attrs):
            if attr == 'eid':
                value = obj.key()
                obj.row, obj.col = i, j
                descr = eschema.type
                value = str(value)
            else:
                value = obj[attr]
                descr = str(eschema.destination(attr))
            line.append(value)
            linedescr.append(descr)
        rows.append(line)
        description.append(linedescr)
        for j, attr in enumerate(attrs):
            if attr == 'eid':
                entity = vreg.etype_class(eschema.type)(req, rset, i, j)
                rset._get_entity_cache_ = {(i, j): entity}
    rset.rowcount = len(rows)
    req.decorate_rset(rset)
    return rset


def needrequest(wrapped):
    def wrapper(cls, *args, **kwargs):
        req = kwargs.pop('req', None)
        if req is None and args and isinstance(args[0], RequestSessionMixIn):
            args = list(args)
            req = args.pop(0)
        if req is None:
            req = getattr(cls, 'req', None)
            if req is None:
                raise Exception('either call this method on an instance or '
                                'specify the req argument')
        return wrapped(cls, req, *args, **kwargs)
    return iclassmethod(wrapper)


class gaedbmetaentity(metaentity):
    """metaclass for goa.db.Model classes: filter entity / db model part,
    put aside the db model part for later creation of db model class.
    """
    def __new__(mcs, name, bases, classdict):
        if not 'id' in classdict:
            classdict['id'] = name
        entitycls = super(gaedbmetaentity, mcs).__new__(mcs, name, bases, classdict)
        return entitycls


TEST_MODELS = {}

def extract_dbmodel(entitycls):
    if MODE == 'test' and entitycls in TEST_MODELS:
        dbclassdict = TEST_MODELS[entitycls]
    else:
        dbclassdict = {}
        for attr, value in entitycls.__dict__.items():
            if isinstance(value, db.Property) or isinstance(value, ReferencePropertyStub):
                dbclassdict[attr] = value
                # don't remove attr from entitycls, this make tests fail, and it's anyway
                # overwritten by descriptor at class initialization time
                #delattr(entitycls, attr)
    if MODE == 'test':
        TEST_MODELS[entitycls] = dbclassdict
        dbclassdict = deepcopy(dbclassdict)
        for propname, prop in TEST_MODELS[entitycls].iteritems():
            if getattr(prop, 'reference_class', None) is db._SELF_REFERENCE:
                dbclassdict[propname].reference_class = db._SELF_REFERENCE
    return dbclassdict


class Model(entities.AnyEntity):
    id = 'Any'
    __metaclass__ = gaedbmetaentity

    row = col = 0

    @classmethod
    def __initialize__(cls):
        super(Model, cls).__initialize__()
        cls._attributes = frozenset(rschema for rschema in cls.e_schema.subject_relations()
                                    if rschema.is_final())

    def __init__(self, *args, **kwargs):
        # db.Model prototype:
        #   __init__(self, parent=None, key_name=None, **kw)
        #
        # Entity prototype:
        #   __init__(self, req, rset, row=None, col=0)
        if args and isinstance(args[0], RequestSessionMixIn) or 'req' in kwargs:
            super(Model, self).__init__(*args, **kwargs)
            self._gaeinitargs = None
        else:
            super(Model, self).__init__(None, None)
            # if Model instances are given in kwargs, turn them into db model
            for key, val in kwargs.iteritems():
                if key in self.e_schema.subject_relations() and not self.e_schema.schema[key].is_final():
                    if isinstance(kwargs, (list, tuple)):
                        val = [isinstance(x, Model) and x._dbmodel or x for x in val]
                    elif isinstance(val, Model):
                        val = val._dbmodel
                    kwargs[key] = val.key()
            self._gaeinitargs = (args, kwargs)

    def __repr__(self):
        return '<ModelEntity %s %s %s at %s>' % (
            self.e_schema, self.eid, self.keys(), id(self))

    def _cubicweb_to_datastore(self, attr, value):
        attr = attr[2:] # remove 's_' / 'o_' prefix
        if attr in self._attributes:
            tschema = self.e_schema.destination(attr)
            if tschema == 'String':
                if len(value) > 500:
                    value = Text(value)
            elif tschema == 'Password':
                # if value is a Binary instance, this mean we got it
                # from a query result and so it is already encrypted
                if isinstance(value, Binary):
                    value = value.getvalue()
                else:
                    value = crypt_password(value)
            elif tschema == 'Bytes':
                if isinstance(value, Binary):
                    value = value.getvalue()
                value = Blob(value)
        else:
            value = Key(value)
        return value

    def _to_gae_dict(self, convert=True):
        gaedict = {}
        for attr, value in self.iteritems():
            attr = 's_' + attr
            if value is not None and convert:
                value = self._cubicweb_to_datastore(attr, value)
            gaedict[attr] = value
        return gaedict

    def to_gae_model(self):
        dbmodel = self._dbmodel
        dbmodel.update(self._to_gae_dict())
        return dbmodel

    @property
    @cached
    def _dbmodel(self):
        if self.has_eid():
            assert self._gaeinitargs is None
            try:
                return self.req.datastore_get(self.eid)
            except AttributeError: # self.req is not a server session
                return Get(self.eid)
        self.set_defaults()
        values = self._to_gae_dict(convert=False)
        parent = key_name = _app = None
        if self._gaeinitargs is not None:
            args, kwargs = self._gaeinitargs
            args = list(args)
            if args:
                parent = args.pop(0)
            if args:
                key_name = args.pop(0)
            if args:
                _app = args.pop(0)
            assert not args
            if 'parent' in kwargs:
                assert parent is None
                parent = kwargs.pop('parent')
            if 'key_name' in kwargs:
                assert key_name is None
                key_name = kwargs.pop('key_name')
            if '_app' in kwargs:
                assert _app is None
                _app = kwargs.pop('_app')

            for key, value in kwargs.iteritems():
                if key in self._attributes:
                    values['s_'+key] = value
        else:
            kwargs = None
        if key_name is None:
            key_name = self.db_key_name()
            if key_name is not None:
                key_name = 'key_' + key_name
        for key, value in values.iteritems():
            if value is None:
                continue
            values[key] = self._cubicweb_to_datastore(key, value)
        entity = Entity(self.id, parent, _app, key_name)
        entity.update(values)
        init_relations(entity, self.e_schema)
        return entity

    def db_key_name(self):
        """override this method to control datastore key name that should be
        used at entity creation.

        Note that if this function return something else than None, the returned
        value will be prefixed by 'key_' to build the actual key name.
        """
        return None

    def metainformation(self):
        return {'type': self.id, 'source': {'uri': 'system'}, 'extid': None}

    def view(self, vid, __registry='views', **kwargs):
        """shortcut to apply a view on this entity"""
        return self.vreg.render(__registry, vid, self.req, rset=self.rset,
                                row=self.row, col=self.col, **kwargs)

    @classmethod
    def _rest_attr_info(cls):
        mainattr, needcheck = super(Model, cls)._rest_attr_info()
        if needcheck:
            return 'eid', False
        return mainattr, needcheck

    def get_value(self, name):
        try:
            value = self[name]
        except KeyError:
            if not self.has_eid():
                return None
            value = self._dbmodel.get('s_'+name)
            if value is not None:
                if isinstance(value, Text):
                    value = unicode(value)
                elif isinstance(value, Blob):
                    value = Binary(str(value))
            self[name] = value
        return value

    def has_eid(self):
        if self.eid is None:
            return False
        try:
            Key(self.eid)
            return True
        except BadKeyError:
            return False

    def complete(self, skip_bytes=True):
        pass

    def unrelated(self, rtype, targettype, role='subject', limit=None,
                  ordermethod=None):
        # XXX dumb implementation
        if limit is not None:
            objs = Query(str(targettype)).Get(limit)
        else:
            objs = Query(str(targettype)).Run()
        return rset_from_objs(self.req, objs, ('eid',),
                              'Any X WHERE X is %s' % targettype)

    def key(self):
        return Key(self.eid)

    def put(self, req=None):
        if req is not None and self.req is None:
            self.req = req
        dbmodel = self.to_gae_model()
        key = Put(dbmodel)
        self.set_eid(str(key))
        if self.req is not None and self.rset is None:
            self.rset = rset_from_objs(self.req, dbmodel, ('eid',),
                                       'Any X WHERE X eid %(x)s', {'x': self.eid})
            self.row = self.col = 0
        return dbmodel

    @needrequest
    def get(cls, req, keys):
        # if check if this is a dict.key call
        if isinstance(cls, Model) and keys in cls._attributes:
            return super(Model, cls).get(keys)
        rset = rset_from_objs(req, Get(keys), ('eid',),
                              'Any X WHERE X eid IN %(x)s', {'x': keys})
        return list(rset.entities())

    @needrequest
    def get_by_id(cls, req, ids, parent=None):
        if isinstance(parent, Model):
            parent = parent.key()
        ids, multiple = NormalizeAndTypeCheck(ids, (int, long))
        keys = [Key.from_path(cls.kind(), id, parent=parent)
                for id in ids]
        rset = rset_from_objs(req, Get(keys))
        return list(rset.entities())

    @classmethod
    def get_by_key_name(cls, req, key_names, parent=None):
        if isinstance(parent, Model):
            parent = parent.key()
        key_names, multiple = NormalizeAndTypeCheck(key_names, basestring)
        keys = [Key.from_path(cls.kind(), name, parent=parent)
                for name in key_names]
        rset = rset_from_objs(req, Get(keys))
        return list(rset.entities())

    @classmethod
    def get_or_insert(cls, req, key_name, **kwds):
        def txn():
            entity = cls.get_by_key_name(key_name, parent=kwds.get('parent'))
            if entity is None:
                entity = cls(key_name=key_name, **kwds)
                entity.put()
            return entity
        return RunInTransaction(txn)

    @classmethod
    def all(cls, req):
        rset = rset_from_objs(req, Query(cls.id).Run())
        return list(rset.entities())

    @classmethod
    def gql(cls, req, query_string, *args, **kwds):
        raise NotImplementedError('use rql')

    @classmethod
    def kind(cls):
        return cls.id

    @classmethod
    def properties(cls):
        raise NotImplementedError('use eschema')

    def dynamic_properties(self):
        raise NotImplementedError('use eschema')

    def is_saved(self):
        return self.has_eid()

    def parent(self):
        parent = self._dbmodel.parent()
        if not parent is None:
            rset = rset_from_objs(self.req, (parent,), ('eid',),
                                  'Any X WHERE X eid %(x)s', {'x': parent.key()})
            parent = rset.get_entity(0, 0)
        return parent

    def parent_key(self):
        return self.parent().key()

    def to_xml(self):
        return self._dbmodel.ToXml()

# hijack AnyEntity class
entities.AnyEntity = Model

BooleanProperty = db.BooleanProperty
URLProperty = db.URLProperty
DateProperty = db.DateProperty
DateTimeProperty = db.DateTimeProperty
TimeProperty = db.TimeProperty
StringProperty = db.StringProperty
TextProperty = db.TextProperty
BlobProperty = db.BlobProperty
IntegerProperty = db.IntegerProperty
FloatProperty = db.FloatProperty
ListProperty = db.ListProperty
SelfReferenceProperty = db.SelfReferenceProperty
UserProperty = db.UserProperty


class ReferencePropertyStub(object):
    def __init__(self, cls, args, kwargs):
        self.cls = cls
        self.args = args
        self.kwargs = kwargs
        self.required = False
        self.__dict__.update(kwargs)
        self.creation_counter = db.Property.creation_counter
        db.Property.creation_counter += 1

    @property
    def data_type(self):
        class FakeDataType(object):
            @staticmethod
            def kind():
                return self.cls.__name__
        return FakeDataType

def ReferenceProperty(cls, *args, **kwargs):
    if issubclass(cls, db.Model):
        cls = db.class_for_kind(cls.__name__)
        return db.ReferenceProperty(cls, *args, **kwargs)
    return ReferencePropertyStub(cls, args, kwargs)
