"""mixins of entity/views organized somewhat in a graph or tree structure


:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

from logilab.common.deprecation import deprecated
from logilab.common.decorators import cached

from cubicweb import typed_eid
from cubicweb.selectors import implements
from cubicweb.interfaces import IEmailable, ITree


class TreeMixIn(object):
    """base tree-mixin providing the tree interface

    This mixin has to be inherited explicitly and configured using the
    tree_attribute, parent_target and children_target class attribute to
    benefit from this default implementation
    """
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
        return res.filtered_rset(lambda x: x.e_schema == self.e_schema, self.cw_col)

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
        yield self
        _done.add(self.eid)
        for child in self.iterchildren(_done):
            try:
                for entity in child.prefixiter(_done):
                    yield entity
            except AttributeError:
                pass

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

    def iterparents(self):
        def _uptoroot(self):
            curr = self
            while True:
                curr = curr.parent()
                if curr is None:
                    break
                yield curr
        return _uptoroot(self)

    def notification_references(self, view):
        """used to control References field of email send on notification
        for this entity. `view` is the notification view.

        Should return a list of eids which can be used to generate message ids
        of previously sent email
        """
        return self.path()[:-1]


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
        return self.related_rql(self.tree_attribute, self.children_target)

    def __iter__(self):
        return self.iterchildren()

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
    __implements__ = (IEmailable,)

    def get_email(self):
        if getattr(self, 'primary_email', None):
            return self.primary_email[0].address
        if getattr(self, 'use_email', None):
            return self.use_email[0].address
        return None

    @classmethod
    def allowed_massmail_keys(cls):
        """returns a set of allowed email substitution keys

        The default is to return the entity's attribute list but an
        entity class might override this method to allow extra keys.
        For instance, the Person class might want to return a `companyname`
        key.
        """
        return set(rs.type for rs, _ in cls.e_schema.attribute_definitions())

    def as_email_context(self):
        """returns the dictionary as used by the sendmail controller to
        build email bodies.

        NOTE: the dictionary keys should match the list returned by the
        `allowed_massmail_keys` method.
        """
        return dict( (attr, getattr(self, attr)) for attr in self.allowed_massmail_keys() )



MI_REL_TRIGGERS = {
    ('primary_email',   'subject'): EmailableMixIn,
    ('use_email',   'subject'): EmailableMixIn,
    }



def _done_init(done, view, row, col):
    """handle an infinite recursion safety belt"""
    if done is None:
        done = set()
    entity = view.rset.get_entity(row, col)
    if entity.eid in done:
        msg = entity._cw._('loop in %(rel)s relation (%(eid)s)') % {
            'rel': entity.tree_attribute,
            'eid': entity.eid
            }
        return None, msg
    done.add(entity.eid)
    return done, entity


class TreeViewMixIn(object):
    """a recursive tree view"""
    __regid__ = 'tree'
    item_vid = 'treeitem'
    __select__ = implements(ITree)

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
    """provide default implementations for IProgress interface methods"""
    # This is an adapter isn't it ?

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
