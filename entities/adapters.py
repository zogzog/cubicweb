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
from warnings import warn

from logilab.mtconverter import TransformError
from logilab.common.decorators import cached

from cubicweb import ValidationError
from cubicweb.view import EntityAdapter, implements_adapter_compat
from cubicweb.selectors import (implements, is_instance, relation_possible,
                                match_exception)
from cubicweb.interfaces import IDownloadable, ITree, IProgress, IMileStone


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
    __needs_bw_compat__ = True
    __regid__ = 'INotifiable'
    __select__ = is_instance('Any')

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
    __select__ = is_instance('Any')

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
                value = entity.printable_value(rschema, format='text/plain')
            except TransformError:
                continue
            except:
                self.exception("can't add value of %s to text index for entity %s",
                               rschema, entity.eid)
                continue
            if value:
                words.setdefault(weight, []).extend(tokenize(value))
        for rschema, role in entity.e_schema.fulltext_relations():
            if role == 'subject':
                for entity_ in getattr(entity, rschema.type):
                    merge_weight_dict(words, entity_.cw_adapt_to('IFTIndexable').get_words())
            else: # if role == 'object':
                for entity_ in getattr(entity, 'reverse_%s' % rschema.type):
                    merge_weight_dict(words, entity_.cw_adapt_to('IFTIndexable').get_words())
        return words

def merge_weight_dict(maindict, newdict):
    for weight, words in newdict.iteritems():
        maindict.setdefault(weight, []).extend(words)

class IDownloadableAdapter(EntityAdapter):
    """interface for downloadable entities"""
    __needs_bw_compat__ = True
    __regid__ = 'IDownloadable'
    __select__ = implements(IDownloadable, warn=False) # XXX for bw compat, else should be abstract

    @implements_adapter_compat('IDownloadable')
    def download_url(self, **kwargs): # XXX not really part of this interface
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
    tree_relation, child_role and parent_role class attributes to benefit from
    this default implementation.

    This adapter provides a tree interface. It has to be overriden to be
    configured using the tree_relation, child_role and parent_role class
    attributes to benefit from this default implementation.

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
    __needs_bw_compat__ = True
    __regid__ = 'ITree'
    __select__ = implements(ITree, warn=False) # XXX for bw compat, else should be abstract

    child_role = 'subject'
    parent_role = 'object'

    @property
    def tree_relation(self):
        warn('[3.9] tree_attribute is deprecated, define tree_relation on a custom '
             'ITree for %s instead' % (self.entity.__class__),
             DeprecationWarning)
        return self.entity.tree_attribute

    # XXX should be removed from the public interface
    @implements_adapter_compat('ITree')
    def children_rql(self):
        """Returns RQL to get the children of the entity."""
        return self.entity.cw_related_rql(self.tree_relation, self.parent_role)

    @implements_adapter_compat('ITree')
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

    @implements_adapter_compat('ITree')
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

    @implements_adapter_compat('ITree')
    def is_leaf(self):
        """Returns True if the entity does not have any children."""
        return len(self.children()) == 0

    @implements_adapter_compat('ITree')
    def is_root(self):
        """Returns true if the entity is root of the tree (e.g. has no parent).
        """
        return self.parent() is None

    @implements_adapter_compat('ITree')
    def root(self):
        """Return the root entity of the tree."""
        return self._cw.entity_from_eid(self.path()[0])

    @implements_adapter_compat('ITree')
    def parent(self):
        """Returns the parent entity if any, else None (e.g. if we are on the
        root).
        """
        try:
            return self.entity.related(self.tree_relation, self.child_role,
                                       entities=True)[0]
        except (KeyError, IndexError):
            return None

    @implements_adapter_compat('ITree')
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

    @implements_adapter_compat('ITree')
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

    @implements_adapter_compat('ITree')
    def iterchildren(self, _done=None):
        """Return an iterator over the item's children."""
        if _done is None:
            _done = set()
        for child in self.children():
            if child.eid in _done:
                self.error('loop in %s tree: %s', child.__regid__.lower(), child)
                continue
            yield child
            _done.add(child.eid)

    @implements_adapter_compat('ITree')
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

    @implements_adapter_compat('ITree')
    @cached
    def path(self):
        """Returns the list of eids from the root object to this object."""
        path = []
        adapter = self
        entity = adapter.entity
        while entity is not None:
            if entity.eid in path:
                self.error('loop in %s tree: %s', entity.__regid__.lower(), entity)
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


class IProgressAdapter(EntityAdapter):
    """something that has a cost, a state and a progression.

    You should at least override progress_info an in_progress methods on concret
    implementations.
    """
    __needs_bw_compat__ = True
    __regid__ = 'IProgress'
    __select__ = implements(IProgress, warn=False) # XXX for bw compat, should be abstract

    @property
    @implements_adapter_compat('IProgress')
    def cost(self):
        """the total cost"""
        return self.progress_info()['estimated']

    @property
    @implements_adapter_compat('IProgress')
    def revised_cost(self):
        return self.progress_info().get('estimatedcorrected', self.cost)

    @property
    @implements_adapter_compat('IProgress')
    def done(self):
        """what is already done"""
        return self.progress_info()['done']

    @property
    @implements_adapter_compat('IProgress')
    def todo(self):
        """what remains to be done"""
        return self.progress_info()['todo']

    @implements_adapter_compat('IProgress')
    def progress_info(self):
        """returns a dictionary describing progress/estimated cost of the
        version.

        - mandatory keys are (''estimated', 'done', 'todo')

        - optional keys are ('notestimated', 'notestimatedcorrected',
          'estimatedcorrected')

        'noestimated' and 'notestimatedcorrected' should default to 0
        'estimatedcorrected' should default to 'estimated'
        """
        raise NotImplementedError

    @implements_adapter_compat('IProgress')
    def finished(self):
        """returns True if status is finished"""
        return not self.in_progress()

    @implements_adapter_compat('IProgress')
    def in_progress(self):
        """returns True if status is not finished"""
        raise NotImplementedError

    @implements_adapter_compat('IProgress')
    def progress(self):
        """returns the % progress of the task item"""
        try:
            return 100. * self.done / self.revised_cost
        except ZeroDivisionError:
            # total cost is 0 : if everything was estimated, task is completed
            if self.progress_info().get('notestimated'):
                return 0.
            return 100

    @implements_adapter_compat('IProgress')
    def progress_class(self):
        return ''


class IMileStoneAdapter(IProgressAdapter):
    __needs_bw_compat__ = True
    __regid__ = 'IMileStone'
    __select__ = implements(IMileStone, warn=False) # XXX for bw compat, should be abstract

    parent_type = None # specify main task's type

    @implements_adapter_compat('IMileStone')
    def get_main_task(self):
        """returns the main ITask entity"""
        raise NotImplementedError

    @implements_adapter_compat('IMileStone')
    def initial_prevision_date(self):
        """returns the initial expected end of the milestone"""
        raise NotImplementedError

    @implements_adapter_compat('IMileStone')
    def eta_date(self):
        """returns expected date of completion based on what remains
        to be done
        """
        raise NotImplementedError

    @implements_adapter_compat('IMileStone')
    def completion_date(self):
        """returns date on which the subtask has been completed"""
        raise NotImplementedError

    @implements_adapter_compat('IMileStone')
    def contractors(self):
        """returns the list of persons supposed to work on this task"""
        raise NotImplementedError


# error handling adapters ######################################################

from cubicweb import UniqueTogetherError

class IUserFriendlyError(EntityAdapter):
    __regid__ = 'IUserFriendlyError'
    __abstract__ = True
    def __init__(self, *args, **kwargs):
        self.exc = kwargs.pop('exc')
        super(IUserFriendlyError, self).__init__(*args, **kwargs)


class IUserFriendlyUniqueTogether(IUserFriendlyError):
    __select__ = match_exception(UniqueTogetherError)
    def raise_user_exception(self):
        etype, rtypes = self.exc.args
        msg = self._cw._('violates unique_together constraints (%s)') % (
            ', '.join([self._cw._(rtype) for rtype in rtypes]))
        raise ValidationError(self.entity.eid, dict((col, msg) for col in rtypes))
