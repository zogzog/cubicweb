# copyright 2010 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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

__docformat__ = "restructuredtext en"

from itertools import chain

from logilab.mtconverter import TransformError
from logilab.common.decorators import cached

from cubicweb.view import EntityAdapter, implements_adapter_compat
from cubicweb.selectors import implements, relation_possible
from cubicweb.interfaces import IDownloadable, ITree


class IEmailableAdapter(EntityAdapter):
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
        return dict( (attr, getattr(self.entity, attr))
                     for attr in self.allowed_massmail_keys() )


class INotifiableAdapter(EntityAdapter):
    __regid__ = 'INotifiable'
    __select__ = implements('Any')

    @implements_adapter_compat('INotifiableAdapter')
    def notification_references(self, view):
        """used to control References field of email send on notification
        for this entity. `view` is the notification view.

        Should return a list of eids which can be used to generate message
        identifiers of previously sent email(s)
        """
        itree = self.entity.cw_adapt_to('ITree')
        if itree is not None:
            return itree.path()[:-1]
        return ()


class IFTIndexableAdapter(EntityAdapter):
    __regid__ = 'IFTIndexable'
    __select__ = implements('Any')

    def fti_containers(self, _done=None):
        if _done is None:
            _done = set()
        entity = self.entity
        _done.add(entity.eid)
        containers = tuple(entity.e_schema.fulltext_containers())
        if containers:
            for rschema, target in containers:
                if target == 'object':
                    targets = getattr(entity, rschema.type)
                else:
                    targets = getattr(entity, 'reverse_%s' % rschema)
                for entity in targets:
                    if entity.eid in _done:
                        continue
                    for container in entity.cw_adapt_to('IFTIndexable').fti_containers(_done):
                        yield container
                        yielded = True
        else:
            yield entity

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
        words = []
        for rschema in entity.e_schema.indexable_attributes():
            if (entity.e_schema, rschema) in pending:
                continue
            try:
                value = entity.printable_value(rschema, format='text/plain')
            except TransformError:
                continue
            except:
                self.exception("can't add value of %s to text index for entity %s",
                               rschema, entity.eid)
                continue
            if value:
                words += tokenize(value)
        for rschema, role in entity.e_schema.fulltext_relations():
            if role == 'subject':
                for entity_ in getattr(entity, rschema.type):
                    words += entity_.cw_adapt_to('IFTIndexable').get_words()
            else: # if role == 'object':
                for entity_ in getattr(entity, 'reverse_%s' % rschema.type):
                    words += entity_.cw_adapt_to('IFTIndexable').get_words()
        return words


class IDownloadableAdapter(EntityAdapter):
    """interface for downloadable entities"""
    __regid__ = 'IDownloadable'
    __select__ = implements(IDownloadable) # XXX for bw compat, else should be abstract

    @implements_adapter_compat('IDownloadable')
    def download_url(self): # XXX not really part of this interface
        """return an url to download entity's content"""
        raise NotImplementedError
    @implements_adapter_compat('IDownloadable')
    def download_content_type(self):
        """return MIME type of the downloadable content"""
        raise NotImplementedError
    @implements_adapter_compat('IDownloadable')
    def download_encoding(self):
        """return encoding of the downloadable content"""
        raise NotImplementedError
    @implements_adapter_compat('IDownloadable')
    def download_file_name(self):
        """return file name of the downloadable content"""
        raise NotImplementedError
    @implements_adapter_compat('IDownloadable')
    def download_data(self):
        """return actual data of the downloadable content"""
        raise NotImplementedError


class ITreeAdapter(EntityAdapter):
    """This adapter has to be overriden to be configured using the
    tree_relation, child_role and parent_role class attributes to
    benefit from this default implementation
    """
    __regid__ = 'ITree'
    __select__ = implements(ITree) # XXX for bw compat, else should be abstract

    tree_relation = None
    child_role = 'subject'
    parent_role = 'object'

    @implements_adapter_compat('ITree')
    def children_rql(self):
        """returns RQL to get children

        XXX should be removed from the public interface
        """
        return self.entity.cw_related_rql(self.tree_relation, self.parent_role)

    @implements_adapter_compat('ITree')
    def different_type_children(self, entities=True):
        """return children entities of different type as this entity.

        according to the `entities` parameter, return entity objects or the
        equivalent result set
        """
        res = self.entity.related(self.tree_relation, self.parent_role,
                                  entities=entities)
        eschema = self.entity.e_schema
        if entities:
            return [e for e in res if e.e_schema != eschema]
        return res.filtered_rset(lambda x: x.e_schema != eschema, self.entity.cw_col)

    @implements_adapter_compat('ITree')
    def same_type_children(self, entities=True):
        """return children entities of the same type as this entity.

        according to the `entities` parameter, return entity objects or the
        equivalent result set
        """
        res = self.entity.related(self.tree_relation, self.parent_role,
                                  entities=entities)
        eschema = self.entity.e_schema
        if entities:
            return [e for e in res if e.e_schema == eschema]
        return res.filtered_rset(lambda x: x.e_schema is eschema, self.entity.cw_col)

    @implements_adapter_compat('ITree')
    def is_leaf(self):
        """returns true if this node as no child"""
        return len(self.children()) == 0

    @implements_adapter_compat('ITree')
    def is_root(self):
        """returns true if this node has no parent"""
        return self.parent() is None

    @implements_adapter_compat('ITree')
    def root(self):
        """return the root object"""
        return self._cw.entity_from_eid(self.path()[0])

    @implements_adapter_compat('ITree')
    def parent(self):
        """return the parent entity if any, else None (e.g. if we are on the
        root)
        """
        try:
            return self.entity.related(self.tree_relation, self.child_role,
                                       entities=True)[0]
        except (KeyError, IndexError):
            return None

    @implements_adapter_compat('ITree')
    def children(self, entities=True, sametype=False):
        """return children entities

        according to the `entities` parameter, return entity objects or the
        equivalent result set
        """
        if sametype:
            return self.same_type_children(entities)
        else:
            return self.entity.related(self.tree_relation, self.parent_role,
                                       entities=entities)

    @implements_adapter_compat('ITree')
    def iterparents(self, strict=True):
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

    @implements_adapter_compat('ITree')
    def iterchildren(self, _done=None):
        """iterates over the item's children"""
        if _done is None:
            _done = set()
        for child in self.children():
            if child.eid in _done:
                self.error('loop in %s tree', child.__regid__.lower())
                continue
            yield child
            _done.add(child.eid)

    @implements_adapter_compat('ITree')
    def prefixiter(self, _done=None):
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
    @implements_adapter_compat('ITree')
    def path(self):
        """returns the list of eids from the root object to this object"""
        path = []
        adapter = self
        entity = adapter.entity
        while entity is not None:
            if entity.eid in path:
                self.error('loop in %s tree', entity.__regid__.lower())
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

