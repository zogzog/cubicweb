# copyright 2015-2016 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
# contact http://www.logilab.fr -- mailto:contact@logilab.fr
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by the Free
# Software Foundation, either version 2.1 of the License, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License along
# with this program. If not, see <http://www.gnu.org/licenses/>.
"""Data import of external entities.

Main entry points:

.. autoclass:: ExtEntitiesImporter
.. autoclass:: ExtEntity

Utilities:

.. autofunction:: cwuri2eid
.. autoclass:: RelationMapping
.. autofunction:: cubicweb.dataimport.importer.use_extid_as_cwuri
"""

from collections import defaultdict
import logging

from logilab.mtconverter import xml_escape

from cubicweb import Binary


def cwuri2eid(cnx, etypes, source_eid=None):
    """Return a dictionary mapping cwuri to eid for entities of the given entity types and / or
    source.
    """
    assert source_eid or etypes, 'no entity types nor source specified'
    rql = 'Any U, X WHERE X cwuri U'
    args = {}
    if len(etypes) == 1:
        rql += ', X is %s' % etypes[0]
    elif etypes:
        rql += ', X is IN (%s)' % ','.join(etypes)
    if source_eid is not None:
        rql += ', X cw_source S, S eid %(s)s'
        args['s'] = source_eid
    return dict(cnx.execute(rql, args))


def use_extid_as_cwuri(extid2eid):
    """Return a generator of :class:`ExtEntity` objects that will set `cwuri`
    using entity's extid if the entity does not exist yet and has no `cwuri`
    defined.

    `extid2eid` is an extid to eid dictionary coming from an
    :class:`ExtEntitiesImporter` instance.

    Example usage:

    .. code-block:: python

        importer = ExtEntitiesImporter(cnx, store, import_log)
        set_cwuri = use_extid_as_cwuri(importer.extid2eid)
        importer.import_entities(set_cwuri(extentities))
    """
    def use_extid_as_cwuri_filter(extentities):
        for extentity in extentities:
            if extentity.extid not in extid2eid:
                extentity.values.setdefault('cwuri', set([extentity.extid.decode('utf-8')]))
            yield extentity
    return use_extid_as_cwuri_filter


def drop_extra_values(extentities, schema, import_log):
    """Return a generator of :class:`ExtEntity` objects that will ensure their attributes and
    inlined relations have a single value. When it's not the case, a warning will be recorded in
    the import log and one value among other will be kept (randomly).

    `schema` is the instance's schema, `import_log` is an instance of a class implementing the
    :class:`SimpleImportLog` interface.

    Example usage:

    .. code-block:: python

        importer = ExtEntitiesImporter(schema, store, import_log)
        importer.import_entities(drop_extra_values(extentities, schema, import_log))

    """
    _get_rschema = schema.rschema
    for extentity in extentities:
        entity_dict = extentity.values
        for key, rtype, role in extentity.iter_rdefs():
            rschema = _get_rschema(rtype)
            if (rschema.final or (rschema.inlined and role == 'subject')) \
               and len(entity_dict[key]) > 1:
                values = ', '.join(repr(v) for v in entity_dict[key])
                import_log.record_warning(
                    "more than one value for attribute %r, only one will be kept: %s"
                    % (rtype, values), path=extentity.extid)
                entity_dict[key] = set([entity_dict[key].pop()])
        yield extentity


class RelationMapping(object):
    """Read-only mapping from relation type to set of related (subject, object) eids.

    If `source` is specified, only returns relations implying entities from
    this source.
    """

    def __init__(self, cnx, source=None):
        self.cnx = cnx
        self._rql_template = 'Any S,O WHERE S %s O'
        self._kwargs = {}
        if source is not None:
            self._rql_template += ', S cw_source SO, O cw_source SO, SO eid %%(s)s'
            self._kwargs['s'] = source.eid

    def __getitem__(self, rtype):
        """Return a set of (subject, object) eids already related by `rtype`"""
        rql = self._rql_template % rtype
        return set(tuple(x) for x in self.cnx.execute(rql, self._kwargs))


class ExtEntity(object):
    """Transitional representation of an entity for use in data importer.

    An external entity has the following properties:

    * ``extid`` (external id), an identifier for the ext entity,

    * ``etype`` (entity type), a string which must be the name of one entity type in the schema
      (eg. ``'Person'``, ``'Animal'``, ...),

    * ``values``, a dictionary whose keys are attribute or relation names from the schema (eg.
      ``'first_name'``, ``'friend'``), and whose values are *sets*. For
      attributes of type Bytes, byte strings should be inserted in `values`.

    For instance:

    .. code-block:: python

        ext_entity.extid = 'http://example.org/person/debby'
        ext_entity.etype = 'Person'
        ext_entity.values = {'first_name': set([u"Deborah", u"Debby"]),
                            'friend': set(['http://example.org/person/john'])}

    """

    def __init__(self, etype, extid, values=None):
        self.etype = etype
        self.extid = extid
        if values is None:
            values = {}
        self.values = values
        self._schema = None

    def __repr__(self):
        return '<%s %s %s>' % (self.etype, self.extid, self.values)

    def iter_rdefs(self):
        """Yield (key, rtype, role) defined in `.values` dict, with:

        * `key` is the original key in `.values` (i.e. the relation type or a 2-uple (relation type,
          role))

        * `rtype` is a yams relation type, expected to be found in the schema (attribute or
          relation)

        * `role` is the role of the entity in the relation, 'subject' or 'object'

        Iteration is done on a copy of the keys so values may be inserted/deleted during it.
        """
        for key in list(self.values):
            if isinstance(key, tuple):
                rtype, role = key
                assert role in ('subject', 'object'), key
                yield key, rtype, role
            else:
                yield key, key, 'subject'

    def prepare(self, schema):
        """Prepare an external entity for later insertion:

        * ensure attributes and inlined relations have a single value
        * turn set([value]) into value and remove key associated to empty set
        * remove non inlined relations and return them as a [(e1key, relation, e2key)] list

        Return a list of non inlined relations that may be inserted later, each relations defined by
        a 3-tuple (subject extid, relation type, object extid).

        The instance's schema is given as argument.

        Take care the importer may call this method several times.
        """
        assert self._schema is None, 'prepare() has already been called for %s' % self
        self._schema = schema
        eschema = schema.eschema(self.etype)
        deferred = []
        entity_dict = self.values
        for key, rtype, role in self.iter_rdefs():
            rschema = schema.rschema(rtype)
            if rschema.final or (rschema.inlined and role == 'subject'):
                assert len(entity_dict[key]) <= 1, \
                    "more than one value for %s: %s (%s)" % (rtype, entity_dict[key], self.extid)
                if entity_dict[key]:
                    entity_dict[rtype] = entity_dict[key].pop()
                    if key != rtype:
                        del entity_dict[key]
                    if (rschema.final and eschema.has_metadata(rtype, 'format')
                            and not rtype + '_format' in entity_dict):
                        entity_dict[rtype + '_format'] = u'text/plain'
                    if (rschema.final
                            and eschema.rdef(rtype).object.type == 'Bytes'
                            and not isinstance(entity_dict[rtype], Binary)):
                        entity_dict[rtype] = Binary(entity_dict[rtype])
                else:
                    del entity_dict[key]
            else:
                for target_extid in entity_dict.pop(key):
                    if role == 'subject':
                        deferred.append((self.extid, rtype, target_extid))
                    else:
                        deferred.append((target_extid, rtype, self.extid))
        return deferred

    def is_ready(self, extid2eid):
        """Return True if the ext entity is ready, i.e. has all the URIs used in inlined relations
        currently existing.
        """
        assert self._schema, 'prepare() method should be called first on %s' % self
        # as .prepare has been called, we know that .values only contains subject relation *type* as
        # key (no more (rtype, role) tuple)
        schema = self._schema
        entity_dict = self.values
        for rtype in entity_dict:
            rschema = schema.rschema(rtype)
            if not rschema.final:
                # .prepare() should drop other cases from the entity dict
                assert rschema.inlined
                if entity_dict[rtype] not in extid2eid:
                    return False
        # entity is ready, replace all relation's extid by eids
        for rtype in entity_dict:
            rschema = schema.rschema(rtype)
            if rschema.inlined:
                entity_dict[rtype] = extid2eid[entity_dict[rtype]]
        return True

    def why_not_ready(self, extid2eid):
        """Return some text explaining why this ext entity is not ready.
        """
        assert self._schema, 'prepare() method should be called first on %s' % self
        # as .prepare has been called, we know that .values only contains subject relation *type* as
        # key (no more (rtype, role) tuple)
        schema = self._schema
        entity_dict = self.values
        for rtype in entity_dict:
            rschema = schema.rschema(rtype)
            if not rschema.final:
                if entity_dict[rtype] not in extid2eid:
                    return u'inlined relation %s is not present (%s)' % (rtype, entity_dict[rtype])
        raise AssertionError('this external entity seems actually ready for insertion')


class ExtEntitiesImporter(object):
    """This class is responsible for importing externals entities, that is instances of
    :class:`ExtEntity`, into CubicWeb entities.

    :param schema: the CubicWeb's instance schema

    :param store: a CubicWeb `Store`

    :param extid2eid: optional {extid: eid} dictionary giving information on existing entities. It
        will be completed during import. You may want to use :func:`cwuri2eid` to build it.

    :param existing_relations: optional {rtype: set((subj eid, obj eid))} mapping giving information
        on existing relations of a given type. You may want to use :class:`RelationMapping` to build
        it.

    :param etypes_order_hint: optional ordered iterable on entity types, giving an hint on the
        order in which they should be attempted to be imported

    :param import_log: optional object implementing the :class:`SimpleImportLog` interface to
        record events occuring during the import

    :param raise_on_error: optional boolean flag - default to false, indicating whether errors
        should be raised or logged. You usually want them to be raised during test but to be logged
        in production.

    Instances of this class are meant to import external entities through :meth:`import_entities`
    which handles a stream of :class:`ExtEntity`. One may then plug arbitrary filters into the
    external entities stream.

    .. automethod:: import_entities
    """

    def __init__(self, schema, store, extid2eid=None, existing_relations=None,
                 etypes_order_hint=(), import_log=None, raise_on_error=False):
        self.schema = schema
        self.store = store
        self.extid2eid = extid2eid if extid2eid is not None else {}
        self.existing_relations = (existing_relations if existing_relations is not None
                                   else defaultdict(set))
        self.etypes_order_hint = etypes_order_hint
        if import_log is None:
            import_log = SimpleImportLog('<unspecified>')
        self.import_log = import_log
        self.raise_on_error = raise_on_error
        # set of created/updated eids
        self.created = set()
        self.updated = set()

    def import_entities(self, ext_entities):
        """Import given external entities (:class:`ExtEntity`) stream (usually a generator)."""
        # {etype: [etype dict]} of entities that are in the import queue
        queue = {}
        # order entity dictionaries then create/update them
        deferred = self._import_entities(ext_entities, queue)
        # create deferred relations that don't exist already
        missing_relations = self.prepare_insert_deferred_relations(deferred)
        self._warn_about_missing_work(queue, missing_relations)

    def _import_entities(self, ext_entities, queue):
        extid2eid = self.extid2eid
        deferred = {}  # non inlined relations that may be deferred
        self.import_log.record_debug('importing entities')
        for ext_entity in self.iter_ext_entities(ext_entities, deferred, queue):
            try:
                eid = extid2eid[ext_entity.extid]
            except KeyError:
                self.prepare_insert_entity(ext_entity)
            else:
                if ext_entity.values:
                    self.prepare_update_entity(ext_entity, eid)
        return deferred

    def iter_ext_entities(self, ext_entities, deferred, queue):
        """Yield external entities in an order which attempts to satisfy
        schema constraints (inlined / cardinality) and to optimize the import.
        """
        schema = self.schema
        extid2eid = self.extid2eid
        order_hint = list(self.etypes_order_hint)
        for ext_entity in ext_entities:
            # check data in the transitional representation and prepare it for
            # later insertion in the database
            for subject_uri, rtype, object_uri in ext_entity.prepare(schema):
                deferred.setdefault(rtype, set()).add((subject_uri, object_uri))
            if not ext_entity.is_ready(extid2eid):
                queue.setdefault(ext_entity.etype, []).append(ext_entity)
                continue
            yield ext_entity
            if not queue:
                continue
            # check for some entities in the queue that may now be ready. We'll have to restart
            # search for ready entities until no one is generated
            for etype in queue:
                if etype not in order_hint:
                    order_hint.append(etype)
            new = True
            while new:
                new = False
                for etype in order_hint:
                    if etype in queue:
                        new_queue = []
                        for ext_entity in queue[etype]:
                            if ext_entity.is_ready(extid2eid):
                                yield ext_entity
                                # may unlock entity previously handled within this loop
                                new = True
                            else:
                                new_queue.append(ext_entity)
                        if new_queue:
                            queue[etype][:] = new_queue
                        else:
                            del queue[etype]

    def prepare_insert_entity(self, ext_entity):
        """Call the store to prepare insertion of the given external entity"""
        eid = self.store.prepare_insert_entity(ext_entity.etype, **ext_entity.values)
        self.extid2eid[ext_entity.extid] = eid
        self.created.add(eid)
        return eid

    def prepare_update_entity(self, ext_entity, eid):
        """Call the store to prepare update of the given external entity"""
        self.store.prepare_update_entity(ext_entity.etype, eid, **ext_entity.values)
        self.updated.add(eid)

    def prepare_insert_deferred_relations(self, deferred):
        """Call the store to insert deferred relations (not handled during insertion/update for
        entities). Return a list of relations `[(subj ext id, obj ext id)]` that may not be inserted
        because the target entities don't exists yet.
        """
        prepare_insert_relation = self.store.prepare_insert_relation
        rschema = self.schema.rschema
        extid2eid = self.extid2eid
        missing_relations = []
        for rtype, relations in deferred.items():
            self.import_log.record_debug('importing %s %s relations' % (len(relations), rtype))
            symmetric = rschema(rtype).symmetric
            existing = self.existing_relations[rtype]
            for subject_uri, object_uri in relations:
                try:
                    subject_eid = extid2eid[subject_uri]
                    object_eid = extid2eid[object_uri]
                except KeyError as exc:
                    missing_relations.append((subject_uri, rtype, object_uri, exc))
                    continue
                if (subject_eid, object_eid) not in existing:
                    prepare_insert_relation(subject_eid, rtype, object_eid)
                    existing.add((subject_eid, object_eid))
                    if symmetric:
                        existing.add((object_eid, subject_eid))
        return missing_relations

    def _warn_about_missing_work(self, queue, missing_relations):
        error = self.import_log.record_error
        if queue:
            msgs = ["can't create some entities, is there some cycle or "
                    "missing data?"]
            for ext_entities in queue.values():
                for ext_entity in ext_entities:
                    msg = '{}: {}'.format(ext_entity, ext_entity.why_not_ready(self.extid2eid))
                    msgs.append(msg)
            map(error, msgs)
            if self.raise_on_error:
                raise Exception('\n'.join(msgs))
        if missing_relations:
            msgs = ["can't create some relations, is there missing data?"]
            for subject_uri, rtype, object_uri, exc in missing_relations:
                msgs.append("Could not find %s when trying to insert (%s, %s, %s)"
                            % (exc, subject_uri, rtype, object_uri))
            map(error, msgs)
            if self.raise_on_error:
                raise Exception('\n'.join(msgs))


class SimpleImportLog(object):
    """Fake CWDataImport log using a simple text format.

    Useful to display logs in the UI instead of storing them to the
    database.
    """

    def __init__(self, filename):
        self.logs = []
        self.filename = filename

    def record_debug(self, msg, path=None, line=None):
        self._log(logging.DEBUG, msg, path, line)

    def record_info(self, msg, path=None, line=None):
        self._log(logging.INFO, msg, path, line)

    def record_warning(self, msg, path=None, line=None):
        self._log(logging.WARNING, msg, path, line)

    def record_error(self, msg, path=None, line=None):
        self._log(logging.ERROR, msg, path, line)

    def record_fatal(self, msg, path=None, line=None):
        self._log(logging.FATAL, msg, path, line)

    def _log(self, severity, msg, path, line):
        encodedmsg = u'%s\t%s\t%s\t%s' % (severity, self.filename,
                                          line or u'', msg)
        self.logs.append(encodedmsg)


class HTMLImportLog(SimpleImportLog):
    """Fake CWDataImport log using a simple HTML format."""
    def __init__(self, filename):
        super(HTMLImportLog, self).__init__(xml_escape(filename))

    def _log(self, severity, msg, path, line):
        encodedmsg = u'%s\t%s\t%s\t%s<br/>' % (severity, self.filename,
                                               line or u'', xml_escape(msg))
        self.logs.append(encodedmsg)
