# copyright 2003-2015 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""
Stores are responsible to insert properly formatted entities and relations into the database. They
have the following API::

    >>> user_eid = store.prepare_insert_entity('CWUser', login=u'johndoe')
    >>> group_eid = store.prepare_insert_entity('CWUser', name=u'unknown')
    >>> store.relate(user_eid, 'in_group', group_eid)
    >>> store.flush()
    >>> store.commit()
    >>> store.finish()

Some store **requires a flush** to copy data in the database, so if you want to have store
independant code you should explicitly call it. (There may be multiple flushes during the
process, or only one at the end if there is no memory issue). This is different from the
commit which validates the database transaction. At last, the `finish()` method should be called in
case the store requires additional work once everything is done.

* ``prepare_insert_entity(<entity type>, **kwargs) -> eid``: given an entity
  type, attributes and inlined relations, return the eid of the entity to be
  inserted, *with no guarantee that anything has been inserted in database*,

* ``prepare_update_entity(<entity type>, eid, **kwargs) -> None``: given an
  entity type and eid, promise for update given attributes and inlined
  relations *with no guarantee that anything has been inserted in database*,

* ``prepare_insert_relation(eid_from, rtype, eid_to) -> None``: indicate that a
  relation ``rtype`` should be added between entities with eids ``eid_from``
  and ``eid_to``. Similar to ``prepare_insert_entity()``, *there is no
  guarantee that the relation will be inserted in database*,

* ``flush() -> None``: flush any temporary data to database. May be called
  several times during an import,

* ``commit() -> None``: commit the database transaction,

* ``finish() -> None``: additional stuff to do after import is terminated.

.. autoclass:: cubicweb.dataimport.stores.RQLObjectStore
.. autoclass:: cubicweb.dataimport.stores.NoHookRQLObjectStore
.. autoclass:: cubicweb.dataimport.stores.MetaGenerator
"""
import inspect
import warnings
from datetime import datetime
from copy import copy

from logilab.common.deprecation import deprecated
from logilab.common.decorators import cached

from cubicweb.schema import META_RTYPES, VIRTUAL_RTYPES
from cubicweb.server.edition import EditedEntity


class RQLObjectStore(object):
    """Store that works by making RQL queries, hence with all the cubicweb's machinery activated.
    """

    def __init__(self, cnx, commit=None):
        if commit is not None:
            warnings.warn('[3.19] commit argument should not be specified '
                          'as the cnx object already provides it.',
                          DeprecationWarning, stacklevel=2)
        self._cnx = cnx
        self._commit = commit or cnx.commit
        # XXX 3.21 deprecated attributes
        self.eids = {}
        self.types = {}

    def rql(self, *args):
        """Execute a RQL query. This is NOT part of the store API."""
        return self._cnx.execute(*args)

    def prepare_insert_entity(self, *args, **kwargs):
        """Given an entity type, attributes and inlined relations, returns the inserted entity's
        eid.
        """
        entity = self._cnx.create_entity(*args, **kwargs)
        self.eids[entity.eid] = entity
        self.types.setdefault(args[0], []).append(entity.eid)
        return entity.eid

    def prepare_update_entity(self, etype, eid, **kwargs):
        """Given an entity type and eid, updates the corresponding entity with specified attributes
        and inlined relations.
        """
        entity = self._cnx.entity_from_eid(eid)
        assert entity.cw_etype == etype, 'Trying to update with wrong type {}'.format(etype)
        # XXX some inlined relations may already exists
        entity.cw_set(**kwargs)

    def prepare_insert_relation(self, eid_from, rtype, eid_to, **kwargs):
        """Insert into the database a  relation ``rtype`` between entities with eids ``eid_from``
        and ``eid_to``.
        """
        self.rql('SET X %s Y WHERE X eid %%(x)s, Y eid %%(y)s' % rtype,
                 {'x': int(eid_from), 'y': int(eid_to)})

    def flush(self):
        """Nothing to flush for this store."""
        pass

    def commit(self):
        """Commit the database transaction."""
        return self._commit()

    @property
    def session(self):
        warnings.warn('[3.19] deprecated property.', DeprecationWarning, stacklevel=2)
        return self._cnx.repo._get_session(self._cnx.sessionid)

    @deprecated("[3.19] use cnx.find(*args, **kwargs).entities() instead")
    def find_entities(self, *args, **kwargs):
        return self._cnx.find(*args, **kwargs).entities()

    @deprecated("[3.19] use cnx.find(*args, **kwargs).one() instead")
    def find_one_entity(self, *args, **kwargs):
        return self._cnx.find(*args, **kwargs).one()

    @deprecated('[3.21] use prepare_insert_entity instead')
    def create_entity(self, *args, **kwargs):
        eid = self.prepare_insert_entity(*args, **kwargs)
        return self._cnx.entity_from_eid(eid)

    @deprecated('[3.21] use prepare_insert_relation instead')
    def relate(self, eid_from, rtype, eid_to, **kwargs):
        self.prepare_insert_relation(eid_from, rtype, eid_to, **kwargs)


class NoHookRQLObjectStore(RQLObjectStore):
    """Store that works by accessing low-level CubicWeb's source API, with all hooks deactivated. It
    must be given a metadata generator object to handle metadata which are usually handled by hooks
    (see :class:`MetaGenerator`).
    """

    def __init__(self, cnx, metagen=None):
        super(NoHookRQLObjectStore, self).__init__(cnx)
        self.source = cnx.repo.system_source
        self.rschema = cnx.repo.schema.rschema
        self.add_relation = self.source.add_relation
        if metagen is None:
            metagen = MetaGenerator(cnx)
        self.metagen = metagen
        self._nb_inserted_entities = 0
        self._nb_inserted_types = 0
        self._nb_inserted_relations = 0
        # deactivate security
        cnx.read_security = False
        cnx.write_security = False

    def prepare_insert_entity(self, etype, **kwargs):
        """Given an entity type, attributes and inlined relations, returns the inserted entity's
        eid.
        """
        for k, v in kwargs.iteritems():
            kwargs[k] = getattr(v, 'eid', v)
        entity, rels = self.metagen.base_etype_dicts(etype)
        # make a copy to keep cached entity pristine
        entity = copy(entity)
        entity.cw_edited = copy(entity.cw_edited)
        entity.cw_clear_relation_cache()
        entity.cw_edited.update(kwargs, skipsec=False)
        entity_source, extid = self.metagen.init_entity(entity)
        cnx = self._cnx
        self.source.add_info(cnx, entity, entity_source, extid)
        self.source.add_entity(cnx, entity)
        kwargs = dict()
        if inspect.getargspec(self.add_relation).keywords:
            kwargs['subjtype'] = entity.cw_etype
        for rtype, targeteids in rels.iteritems():
            # targeteids may be a single eid or a list of eids
            inlined = self.rschema(rtype).inlined
            try:
                for targeteid in targeteids:
                    self.add_relation(cnx, entity.eid, rtype, targeteid,
                                      inlined, **kwargs)
            except TypeError:
                self.add_relation(cnx, entity.eid, rtype, targeteids,
                                  inlined, **kwargs)
        self._nb_inserted_entities += 1
        return entity.eid

    # XXX: prepare_update_entity is inherited from RQLObjectStore, it should be reimplemented to
    # actually skip hooks as prepare_insert_entity

    def prepare_insert_relation(self, eid_from, rtype, eid_to, **kwargs):
        """Insert into the database a  relation ``rtype`` between entities with eids ``eid_from``
        and ``eid_to``.
        """
        assert not rtype.startswith('reverse_')
        self.add_relation(self._cnx, eid_from, rtype, eid_to,
                          self.rschema(rtype).inlined)
        if self.rschema(rtype).symmetric:
            self.add_relation(self._cnx, eid_to, rtype, eid_from,
                              self.rschema(rtype).inlined)
        self._nb_inserted_relations += 1

    @property
    @deprecated('[3.21] deprecated')
    def nb_inserted_entities(self):
        return self._nb_inserted_entities

    @property
    @deprecated('[3.21] deprecated')
    def nb_inserted_types(self):
        return self._nb_inserted_types

    @property
    @deprecated('[3.21] deprecated')
    def nb_inserted_relations(self):
        return self._nb_inserted_relations


class MetaGenerator(object):
    """Class responsible for generating standard metadata for imported entities. You may want to
    derive it to add application specific's metadata.

    Parameters:
    * `cnx`: connection to the repository
    * `baseurl`: optional base URL to be used for `cwuri` generation - default to config['base-url']
    * `source`: optional source to be used as `cw_source` for imported entities
    """
    META_RELATIONS = (META_RTYPES
                      - VIRTUAL_RTYPES
                      - set(('eid', 'cwuri',
                             'is', 'is_instance_of', 'cw_source')))

    def __init__(self, cnx, baseurl=None, source=None):
        self._cnx = cnx
        if baseurl is None:
            config = cnx.vreg.config
            baseurl = config['base-url'] or config.default_base_url()
        if not baseurl[-1] == '/':
            baseurl += '/'
        self.baseurl = baseurl
        if source is None:
            source = cnx.repo.system_source
        self.source = source
        self.create_eid = cnx.repo.system_source.create_eid
        self.time = datetime.now()
        # attributes/relations shared by all entities of the same type
        self.etype_attrs = []
        self.etype_rels = []
        # attributes/relations specific to each entity
        self.entity_attrs = ['cwuri']
        #self.entity_rels = [] XXX not handled (YAGNI?)
        schema = cnx.vreg.schema
        rschema = schema.rschema
        for rtype in self.META_RELATIONS:
            # skip owned_by / created_by if user is the internal manager
            if cnx.user.eid == -1 and rtype in ('owned_by', 'created_by'):
                continue
            if rschema(rtype).final:
                self.etype_attrs.append(rtype)
            else:
                self.etype_rels.append(rtype)

    @cached
    def base_etype_dicts(self, etype):
        entity = self._cnx.vreg['etypes'].etype_class(etype)(self._cnx)
        # entity are "surface" copied, avoid shared dict between copies
        del entity.cw_extra_kwargs
        entity.cw_edited = EditedEntity(entity)
        for attr in self.etype_attrs:
            genfunc = self.generate(attr)
            if genfunc:
                entity.cw_edited.edited_attribute(attr, genfunc(entity))
        rels = {}
        for rel in self.etype_rels:
            genfunc = self.generate(rel)
            if genfunc:
                rels[rel] = genfunc(entity)
        return entity, rels

    def init_entity(self, entity):
        entity.eid = self.create_eid(self._cnx)
        extid = entity.cw_edited.get('cwuri')
        for attr in self.entity_attrs:
            if attr in entity.cw_edited:
                # already set, skip this attribute
                continue
            genfunc = self.generate(attr)
            if genfunc:
                entity.cw_edited.edited_attribute(attr, genfunc(entity))
        if isinstance(extid, unicode):
            extid = extid.encode('utf-8')
        return self.source, extid

    def generate(self, rtype):
        return getattr(self, 'gen_%s' % rtype, None)

    def gen_cwuri(self, entity):
        assert self.baseurl, 'baseurl is None while generating cwuri'
        return u'%s%s' % (self.baseurl, entity.eid)

    def gen_creation_date(self, entity):
        return self.time

    def gen_modification_date(self, entity):
        return self.time

    def gen_created_by(self, entity):
        return self._cnx.user.eid

    def gen_owned_by(self, entity):
        return self._cnx.user.eid

