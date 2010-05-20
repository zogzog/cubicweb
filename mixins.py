# copyright 2003-2010 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""mixins of entity/views organized somewhat in a graph or tree structure"""
__docformat__ = "restructuredtext en"

from itertools import chain

from logilab.common.decorators import cached
from logilab.common.deprecation import deprecated, class_deprecated

from cubicweb.selectors import implements
from cubicweb.interfaces import ITree


class TreeMixIn(object):
    """base tree-mixin implementing the tree interface

    This mixin has to be inherited explicitly and configured using the
    tree_attribute, parent_target and children_target class attribute to
    benefit from this default implementation
    """
    __metaclass__ = class_deprecated
    __deprecation_warning__ = '[3.9] TreeMixIn is deprecated, use/override ITreeAdapter instead'

    tree_attribute = None
    # XXX misnamed
    parent_target = 'subject'
    children_target = 'object'

    def different_type_children(self, entities=True):
        """return children entities of different type as this entity.

        according to the `entities` parameter, return entity objects or the
        equivalent result set
        """
        res = self.related(self.tree_attribute, self.children_target,
                           entities=entities)
        if entities:
            return [e for e in res if e.e_schema != self.e_schema]
        return res.filtered_rset(lambda x: x.e_schema != self.e_schema, self.cw_col)

    def same_type_children(self, entities=True):
        """return children entities of the same type as this entity.

        according to the `entities` parameter, return entity objects or the
        equivalent result set
        """
        res = self.related(self.tree_attribute, self.children_target,
                           entities=entities)
        if entities:
            return [e for e in res if e.e_schema == self.e_schema]
        return res.filtered_rset(lambda x: x.e_schema is self.e_schema, self.cw_col)

    def iterchildren(self, _done=None):
        if _done is None:
            _done = set()
        for child in self.children():
            if child.eid in _done:
                self.error('loop in %s tree', self.__regid__.lower())
                continue
            yield child
            _done.add(child.eid)

    def prefixiter(self, _done=None):
        if _done is None:
            _done = set()
        if self.eid in _done:
            return
        _done.add(self.eid)
        yield self
        for child in self.same_type_children():
            for entity in child.prefixiter(_done):
                yield entity

    @cached
    def path(self):
        """returns the list of eids from the root object to this object"""
        path = []
        parent = self
        while parent:
            if parent.eid in path:
                self.error('loop in %s tree', self.__regid__.lower())
                break
            path.append(parent.eid)
            try:
                # check we are not leaving the tree
                if (parent.tree_attribute != self.tree_attribute or
                    parent.parent_target != self.parent_target):
                    break
                parent = parent.parent()
            except AttributeError:
                break

        path.reverse()
        return path

    def iterparents(self, strict=True):
        def _uptoroot(self):
            curr = self
            while True:
                curr = curr.parent()
                if curr is None:
                    break
                yield curr
        if not strict:
            return chain([self], _uptoroot(self))
        return _uptoroot(self)

    ## ITree interface ########################################################
    def parent(self):
        """return the parent entity if any, else None (e.g. if we are on the
        root
        """
        try:
            return self.related(self.tree_attribute, self.parent_target,
                                entities=True)[0]
        except (KeyError, IndexError):
            return None

    def children(self, entities=True, sametype=False):
        """return children entities

        according to the `entities` parameter, return entity objects or the
        equivalent result set
        """
        if sametype:
            return self.same_type_children(entities)
        else:
            return self.related(self.tree_attribute, self.children_target,
                                entities=entities)

    def children_rql(self):
        return self.cw_related_rql(self.tree_attribute, self.children_target)

    def is_leaf(self):
        return len(self.children()) == 0

    def is_root(self):
        return self.parent() is None

    def root(self):
        """return the root object"""
        return self._cw.entity_from_eid(self.path()[0])


class EmailableMixIn(object):
    """base mixin providing the default get_email() method used by
    the massmailing view

    NOTE: The default implementation is based on the
    primary_email / use_email scheme
    """
    @deprecated("[3.9] use entity.cw_adapt_to('IEmailable').get_email()")
    def get_email(self):
        if getattr(self, 'primary_email', None):
            return self.primary_email[0].address
        if getattr(self, 'use_email', None):
            return self.use_email[0].address
        return None


"""pluggable mixins system: plug classes registered in MI_REL_TRIGGERS on entity
classes which have the relation described by the dict's key.

NOTE: pluggable mixins can't override any method of the 'explicit' user classes tree
(eg without plugged classes). This includes bases Entity and AnyEntity classes.
"""
MI_REL_TRIGGERS = {
    ('primary_email',   'subject'): EmailableMixIn,
    ('use_email',   'subject'): EmailableMixIn,
    }



class TreeViewMixIn(object):
    """a recursive tree view"""
    __metaclass__ = class_deprecated
    __deprecation_warning__ = '[3.9] TreeViewMixIn is deprecated, use/override BaseTreeView instead'

    __regid__ = 'tree'
    __select__ = implements(ITree)
    item_vid = 'treeitem'

    def call(self, done=None, **kwargs):
        if done is None:
            done = set()
        super(TreeViewMixIn, self).call(done=done, **kwargs)

    def cell_call(self, row, col=0, vid=None, done=None, **kwargs):
        done, entity = _done_init(done, self, row, col)
        if done is None:
            # entity is actually an error message
            self.w(u'<li class="badcontent">%s</li>' % entity)
            return
        self.open_item(entity)
        entity.view(vid or self.item_vid, w=self.w, **kwargs)
        relatedrset = entity.children(entities=False)
        self.wview(self.__regid__, relatedrset, 'null', done=done, **kwargs)
        self.close_item(entity)

    def open_item(self, entity):
        self.w(u'<li class="%s">\n' % entity.__regid__.lower())
    def close_item(self, entity):
        self.w(u'</li>\n')


class TreePathMixIn(object):
    """a recursive path view"""
    __metaclass__ = class_deprecated
    __deprecation_warning__ = '[3.9] TreePathMixIn is deprecated, use/override TreePathView instead'
    __regid__ = 'path'
    item_vid = 'oneline'
    separator = u'&#160;&gt;&#160;'

    def call(self, **kwargs):
        self.w(u'<div class="pathbar">')
        super(TreePathMixIn, self).call(**kwargs)
        self.w(u'</div>')

    def cell_call(self, row, col=0, vid=None, done=None, **kwargs):
        done, entity = _done_init(done, self, row, col)
        if done is None:
            # entity is actually an error message
            self.w(u'<span class="badcontent">%s</span>' % entity)
            return
        parent = entity.parent()
        if parent:
            parent.view(self.__regid__, w=self.w, done=done)
            self.w(self.separator)
        entity.view(vid or self.item_vid, w=self.w)


class ProgressMixIn(object):
    """provide a default implementations for IProgress interface methods"""
    __metaclass__ = class_deprecated
    __deprecation_warning__ = '[3.9] ProgressMixIn is deprecated, use/override IProgressAdapter instead'

    @property
    def cost(self):
        return self.progress_info()['estimated']

    @property
    def revised_cost(self):
        return self.progress_info().get('estimatedcorrected', self.cost)

    @property
    def done(self):
        return self.progress_info()['done']

    @property
    def todo(self):
        return self.progress_info()['todo']

    @cached
    def progress_info(self):
        raise NotImplementedError()

    def finished(self):
        return not self.in_progress()

    def in_progress(self):
        raise NotImplementedError()

    def progress(self):
        try:
            return 100. * self.done / self.revised_cost
        except ZeroDivisionError:
            # total cost is 0 : if everything was estimated, task is completed
            if self.progress_info().get('notestimated'):
                return 0.
            return 100
