"""mixins of entity/views organized somewhat in a graph or tree structure


:organization: Logilab
:copyright: 2001-2008 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

from logilab.common.decorators import cached

from cubicweb.common.selectors import implement_interface
from cubicweb.interfaces import IWorkflowable, IEmailable, ITree


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
        return res.filtered_rset(lambda x: x.e_schema != self.e_schema, self.col)

    def same_type_children(self, entities=True):
        """return children entities of the same type as this entity.
        
        according to the `entities` parameter, return entity objects or the
        equivalent result set
        """
        res = self.related(self.tree_attribute, self.children_target,
                           entities=entities)
        if entities:
            return [e for e in res if e.e_schema == self.e_schema]
        return res.filtered_rset(lambda x: x.e_schema == self.e_schema, self.col)
    
    def iterchildren(self, _done=None):
        if _done is None:
            _done = set()
        for child in self.children():
            if child.eid in _done:
                self.error('loop in %s tree', self.id.lower())
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
                self.error('loop in %s tree', self.id.lower())
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
        print '*' * 80
        return len(self.children()) == 0

    def is_root(self):
        return self.parent() is None

    def root(self):
        """return the root object"""
        return self.req.eid_rset(self.path()[0]).get_entity(0, 0)


class WorkflowableMixIn(object):
    """base mixin providing workflow helper methods for workflowable entities.
    This mixin will be automatically set on class supporting the 'in_state'
    relation (which implies supporting 'wf_info_for' as well)
    """
    __implements__ = (IWorkflowable,)
    
    @property
    def state(self):
        return self.in_state[0].name
    
    @property
    def displayable_state(self):
        return self.req._(self.state)

    def wf_state(self, statename):
        rset = self.req.execute('Any S, SN WHERE S name %(n)s, S state_of E, E name %(e)s',
                                {'n': statename, 'e': str(self.e_schema)})
        if rset:
            return rset.get_entity(0, 0)
        return None
    
    def wf_transition(self, trname):
        rset = self.req.execute('Any T, TN WHERE T name %(n)s, T transition_of E, E name %(e)s',
                                {'n': trname, 'e': str(self.e_schema)})
        if rset:
            return rset.get_entity(0, 0)
        return None
    
    def change_state(self, stateeid, trcomment=None, trcommentformat=None):
        """change the entity's state according to a state defined in given
        parameters
        """
        if trcomment:
            self.req.set_shared_data('trcomment', trcomment)
        if trcommentformat:
            self.req.set_shared_data('trcommentformat', trcommentformat)
        self.req.execute('SET X in_state S WHERE X eid %(x)s, S eid %(s)s',
                         {'x': self.eid, 's': stateeid}, 'x')
    
    def can_pass_transition(self, trname):
        """return the Transition instance if the current user can pass the
        transition with the given name, else None
        """
        stateeid = self.in_state[0].eid
        rset = self.req.execute('Any T,N,DS WHERE S allowed_transition T,'
                                'S eid %(x)s,T name %(trname)s,ET name %(et)s,'
                                'T name N,T destination_state DS,T transition_of ET',
                                {'x': stateeid, 'et': str(self.e_schema),
                                 'trname': trname}, 'x')
        for tr in rset.entities():
            if tr.may_be_passed(self.eid, stateeid):
                return tr
    
    def latest_trinfo(self):
        """return the latest transition information for this entity"""
        return self.reverse_wf_info_for[-1]
            
    # specific vocabulary methods #############################################

    def subject_in_state_vocabulary(self, rschema, limit=None):
        """vocabulary method for the in_state relation, looking for
        relation's object entities (i.e. self is the subject) according
        to initial_state, state_of and next_state relation
        """
        if not self.has_eid() or not self.in_state:
            # get the initial state
            rql = 'Any S where S state_of ET, ET name %(etype)s, ET initial_state S'
            rset = self.req.execute(rql, {'etype': str(self.e_schema)})
            if rset:
                return [(rset.get_entity(0, 0).view('combobox'), rset[0][0])]
            return []
        results = []
        for tr in self.in_state[0].transitions(self):
            state = tr.destination_state[0]
            results.append((state.view('combobox'), state.eid))
        return sorted(results)
            
    # __method methods ########################################################
    
    def set_state(self, params=None):
        """change the entity's state according to a state defined in given
        parameters, used to be called using __method controler facility
        """
        params = params or self.req.form
        self.change_state(int(params.pop('state')), params.get('trcomment'),
                          params.get('trcommentformat'))
        self.req.set_message(self.req._('__msg state changed'))



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
    ('in_state',    'subject'): WorkflowableMixIn,
    ('primary_email',   'subject'): EmailableMixIn,
    ('use_email',   'subject'): EmailableMixIn,
    }



def _done_init(done, view, row, col):
    """handle an infinite recursion safety belt"""
    if done is None:
        done = set()
    entity = view.entity(row, col)
    if entity.eid in done:
        msg = entity.req._('loop in %(rel)s relation (%(eid)s)') % {
            'rel': entity.tree_attribute,
            'eid': entity.eid
            }
        return None, msg
    done.add(entity.eid)
    return done, entity


class TreeViewMixIn(object):
    """a recursive tree view"""
    id = 'tree'
    item_vid = 'treeitem'
    __selectors__ = (implement_interface,)
    accepts_interfaces = (ITree,)

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
        self.wview(self.id, relatedrset, 'null', done=done, **kwargs)
        self.close_item(entity)

    def open_item(self, entity):
        self.w(u'<li class="%s">\n' % entity.id.lower())
    def close_item(self, entity):
        self.w(u'</li>\n')


class TreePathMixIn(object):
    """a recursive path view"""
    id = 'path'
    item_vid = 'oneline'
    separator = u'&nbsp;&gt;&nbsp;'

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
            parent.view(self.id, w=self.w, done=done)
            self.w(self.separator)
        entity.view(vid or self.item_vid, w=self.w)


class ProgressMixIn(object):
    """provide default implementations for IProgress interface methods"""

    @property
    @cached
    def cost(self):
        return self.progress_info()['estimated']

    @property
    @cached
    def revised_cost(self):
        return self.progress_info().get('estimatedcorrected', self.cost)

    @property
    @cached
    def done(self):
        return self.progress_info()['done']

    @property
    @cached
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
            if self.progress_info().get('notestmiated'):
                return 0.
            return 100
