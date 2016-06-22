# copyright 2010-2015 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""some basic entity adapter implementations, for interfaces used in the
framework itself.
"""
from cubicweb import _

from itertools import chain
from hashlib import md5

from logilab.mtconverter import TransformError
from logilab.common.decorators import cached

from cubicweb import ValidationError, view, ViolatedConstraint, UniqueTogetherError
from cubicweb.predicates import is_instance, relation_possible, match_exception


class IEmailableAdapter(view.EntityAdapter):
    __regid__ = 'IEmailable'
    __select__ = relation_possible('primary_email') | relation_possible('use_email')

    def get_email(self):
        if getattr(self.entity, 'primary_email', None):
            return self.entity.primary_email[0].address
        if getattr(self.entity, 'use_email', None):
            return self.entity.use_email[0].address
        return None

    def allowed_massmail_keys(self):
        """returns a set of allowed email substitution keys

        The default is to return the entity's attribute list but you might
        override this method to allow extra keys.  For instance, a Person
        class might want to return a `companyname` key.
        """
        return set(rschema.type
                   for rschema, attrtype in self.entity.e_schema.attribute_definitions()
                   if attrtype.type not in ('Password', 'Bytes'))

    def as_email_context(self):
        """returns the dictionary as used by the sendmail controller to
        build email bodies.

        NOTE: the dictionary keys should match the list returned by the
        `allowed_massmail_keys` method.
        """
        return dict((attr, getattr(self.entity, attr))
                    for attr in self.allowed_massmail_keys())


class INotifiableAdapter(view.EntityAdapter):
    __regid__ = 'INotifiable'
    __select__ = is_instance('Any')

    def notification_references(self, view):
        """used to control References field of email send on notification
        for this entity. `view` is the notification view.

        Should return a list of eids which can be used to generate message
        identifiers of previously sent email(s)
        """
        itree = self.entity.cw_adapt_to('ITree')
        if itree is not None:
            return itree.path()[:-1]
        if view.msgid_timestamp:
            return (self.entity.eid,)
        return ()


class IFTIndexableAdapter(view.EntityAdapter):
    """standard adapter to handle fulltext indexing

    .. automethod:: cubicweb.entities.adapters.IFTIndexableAdapter.fti_containers
    .. automethod:: cubicweb.entities.adapters.IFTIndexableAdapter.get_words
    """
    __regid__ = 'IFTIndexable'
    __select__ = is_instance('Any')

    def fti_containers(self, _done=None):
        """return the list of entities to index when handling ``self.entity``

        The actual list of entities depends on ``fulltext_container`` usage
        in the datamodel definition
        """
        if _done is None:
            _done = set()
        entity = self.entity
        _done.add(entity.eid)
        containers = tuple(entity.e_schema.fulltext_containers())
        if containers:
            for rschema, role in containers:
                if role == 'object':
                    targets = getattr(entity, rschema.type)
                else:
                    targets = getattr(entity, 'reverse_%s' % rschema)
                for target in targets:
                    if target.eid in _done:
                        continue
                    for container in target.cw_adapt_to('IFTIndexable').fti_containers(_done):
                        yield container
        else:
            yield entity

    # weight in ABCD
    entity_weight = 1.0
    attr_weight = {}

    def get_words(self):
        """used by the full text indexer to get words to index

        this method should only be used on the repository side since it depends
        on the logilab.database package

        :rtype: list
        :return: the list of indexable word of this entity
        """
        from logilab.database.fti import tokenize
        # take care to cases where we're modyfying the schema
        entity = self.entity
        pending = self._cw.transaction_data.setdefault('pendingrdefs', set())
        words = {}
        for rschema in entity.e_schema.indexable_attributes():
            if (entity.e_schema, rschema) in pending:
                continue
            weight = self.attr_weight.get(rschema, 'C')
            try:
                value = entity.printable_value(rschema, format=u'text/plain')
            except TransformError:
                continue
            except Exception:
                self.exception("can't add value of %s to text index for entity %s",
                               rschema, entity.eid)
                continue
            if value:
                words.setdefault(weight, []).extend(tokenize(value))
        for rschema, role in entity.e_schema.fulltext_relations():
            if role == 'subject':
                for entity_ in getattr(entity, rschema.type):
                    merge_weight_dict(words, entity_.cw_adapt_to('IFTIndexable').get_words())
            else:  # if role == 'object':
                for entity_ in getattr(entity, 'reverse_%s' % rschema.type):
                    merge_weight_dict(words, entity_.cw_adapt_to('IFTIndexable').get_words())
        return words


def merge_weight_dict(maindict, newdict):
    for weight, words in newdict.items():
        maindict.setdefault(weight, []).extend(words)


class IDownloadableAdapter(view.EntityAdapter):
    """interface for downloadable entities"""
    __regid__ = 'IDownloadable'
    __abstract__ = True

    def download_url(self, **kwargs):  # XXX not really part of this interface
        """return a URL to download entity's content

        It should be a unicode object containing url-encoded ASCII.
        """
        raise NotImplementedError

    def download_content_type(self):
        """return MIME type (unicode) of the downloadable content"""
        raise NotImplementedError

    def download_encoding(self):
        """return encoding (unicode) of the downloadable content"""
        raise NotImplementedError

    def download_file_name(self):
        """return file name (unicode) of the downloadable content"""
        raise NotImplementedError

    def download_data(self):
        """return actual data (bytes) of the downloadable content"""
        raise NotImplementedError


# XXX should propose to use two different relations for children/parent
class ITreeAdapter(view.EntityAdapter):
    """This adapter provides a tree interface.

    It has to be overriden to be configured using the tree_relation,
    child_role and parent_role class attributes to benefit from this default
    implementation.

    This class provides the following methods:

    .. automethod: iterparents
    .. automethod: iterchildren
    .. automethod: prefixiter

    .. automethod: is_leaf
    .. automethod: is_root

    .. automethod: root
    .. automethod: parent
    .. automethod: children
    .. automethod: different_type_children
    .. automethod: same_type_children
    .. automethod: children_rql
    .. automethod: path
    """
    __regid__ = 'ITree'
    __abstract__ = True

    child_role = 'subject'
    parent_role = 'object'

    def children_rql(self):
        """Returns RQL to get the children of the entity."""
        return self.entity.cw_related_rql(self.tree_relation, self.parent_role)

    def different_type_children(self, entities=True):
        """Return children entities of different type as this entity.

        According to the `entities` parameter, return entity objects or the
        equivalent result set.
        """
        res = self.entity.related(self.tree_relation, self.parent_role,
                                  entities=entities)
        eschema = self.entity.e_schema
        if entities:
            return [e for e in res if e.e_schema != eschema]
        return res.filtered_rset(lambda x: x.e_schema != eschema, self.entity.cw_col)

    def same_type_children(self, entities=True):
        """Return children entities of the same type as this entity.

        According to the `entities` parameter, return entity objects or the
        equivalent result set.
        """
        res = self.entity.related(self.tree_relation, self.parent_role,
                                  entities=entities)
        eschema = self.entity.e_schema
        if entities:
            return [e for e in res if e.e_schema == eschema]
        return res.filtered_rset(lambda x: x.e_schema is eschema, self.entity.cw_col)

    def is_leaf(self):
        """Returns True if the entity does not have any children."""
        return len(self.children()) == 0

    def is_root(self):
        """Returns true if the entity is root of the tree (e.g. has no parent).
        """
        return self.parent() is None

    def root(self):
        """Return the root entity of the tree."""
        return self._cw.entity_from_eid(self.path()[0])

    def parent(self):
        """Returns the parent entity if any, else None (e.g. if we are on the
        root).
        """
        try:
            return self.entity.related(self.tree_relation, self.child_role,
                                       entities=True)[0]
        except (KeyError, IndexError):
            return None

    def children(self, entities=True, sametype=False):
        """Return children entities.

        According to the `entities` parameter, return entity objects or the
        equivalent result set.
        """
        if sametype:
            return self.same_type_children(entities)
        else:
            return self.entity.related(self.tree_relation, self.parent_role,
                                       entities=entities)

    def iterparents(self, strict=True):
        """Return an iterator on the parents of the entity."""
        def _uptoroot(self):
            curr = self
            while True:
                curr = curr.parent()
                if curr is None:
                    break
                yield curr
                curr = curr.cw_adapt_to('ITree')
        if not strict:
            return chain([self.entity], _uptoroot(self))
        return _uptoroot(self)

    def iterchildren(self, _done=None):
        """Return an iterator over the item's children."""
        if _done is None:
            _done = set()
        for child in self.children():
            if child.eid in _done:
                self.error('loop in %s tree: %s', child.cw_etype.lower(), child)
                continue
            yield child
            _done.add(child.eid)

    def prefixiter(self, _done=None):
        """Return an iterator over the item's descendants in a prefixed order."""
        if _done is None:
            _done = set()
        if self.entity.eid in _done:
            return
        _done.add(self.entity.eid)
        yield self.entity
        for child in self.same_type_children():
            for entity in child.cw_adapt_to('ITree').prefixiter(_done):
                yield entity

    @cached
    def path(self):
        """Returns the list of eids from the root object to this object."""
        path = []
        adapter = self
        entity = adapter.entity
        while entity is not None:
            if entity.eid in path:
                self.error('loop in %s tree: %s', entity.cw_etype.lower(), entity)
                break
            path.append(entity.eid)
            try:
                # check we are not jumping to another tree
                if (adapter.tree_relation != self.tree_relation or
                        adapter.child_role != self.child_role):
                    break
                entity = adapter.parent()
                adapter = entity.cw_adapt_to('ITree')
            except AttributeError:
                break
        path.reverse()
        return path


class ISerializableAdapter(view.EntityAdapter):
    """Adapter to serialize an entity to a bare python structure that may be
    directly serialized to e.g. JSON.
    """

    __regid__ = 'ISerializable'
    __select__ = is_instance('Any')

    def serialize(self):
        entity = self.entity
        entity.complete()
        data = {
            'cw_etype': entity.cw_etype,
            'cw_source': entity.cw_metainformation()['source']['uri'],
            'eid': entity.eid,
        }
        for rschema, __ in entity.e_schema.attribute_definitions():
            attr = rschema.type
            try:
                value = entity.cw_attr_cache[attr]
            except KeyError:
                # Bytes
                continue
            data[attr] = value
        return data


# error handling adapters ######################################################


class IUserFriendlyError(view.EntityAdapter):
    __regid__ = 'IUserFriendlyError'
    __abstract__ = True

    def __init__(self, *args, **kwargs):
        self.exc = kwargs.pop('exc')
        super(IUserFriendlyError, self).__init__(*args, **kwargs)


class IUserFriendlyUniqueTogether(IUserFriendlyError):
    __select__ = match_exception(UniqueTogetherError)

    def raise_user_exception(self):
        rtypes = self.exc.rtypes
        errors = {}
        msgargs = {}
        i18nvalues = []
        for rtype in rtypes:
            errors[rtype] = _('%(KEY-rtype)s is part of violated unicity constraint')
            msgargs[rtype + '-rtype'] = rtype
            i18nvalues.append(rtype + '-rtype')
        errors[''] = _('some relations violate a unicity constraint')
        raise ValidationError(self.entity.eid, errors, msgargs=msgargs, i18nvalues=i18nvalues)


class IUserFriendlyCheckConstraint(IUserFriendlyError):
    __select__ = match_exception(ViolatedConstraint)

    def raise_user_exception(self):
        cstrname = self.exc.cstrname
        eschema = self.entity.e_schema
        for rschema, attrschema in eschema.attribute_definitions():
            rdef = rschema.rdef(eschema, attrschema)
            for constraint in rdef.constraints:
                if cstrname == 'cstr' + md5(
                        (eschema.type + rschema.type + constraint.type() +
                         (constraint.serialize() or '')).encode('ascii')).hexdigest():
                    break
            else:
                continue
            break
        else:
            assert 0
        key = rschema.type + '-subject'
        # use .get since a constraint may be associated to an attribute that isn't edited (e.g.
        # constraint between two attributes). This should be the purpose of an api rework at some
        # point, we currently rely on the fact that such constraint will provide a dedicated user
        # message not relying on the `value` argument
        value = self.entity.cw_edited.get(rschema.type)
        msg, args = constraint.failed_message(key, value, self.entity)
        raise ValidationError(self.entity.eid, {key: msg}, args)
