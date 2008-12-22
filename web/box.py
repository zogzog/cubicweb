"""abstract box classes for CubicWeb web client

:organization: Logilab
:copyright: 2001-2008 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

from logilab.common.decorators import cached
from logilab.mtconverter import html_escape

from cubicweb import Unauthorized, role as get_role
from cubicweb.common.registerers import (
    accepts_registerer, extresources_registerer,
    etype_rtype_priority_registerer)
from cubicweb.common.selectors import (
    etype_rtype_selector, one_line_rset, accept_selector, accept_rtype_selector,
    primaryview_selector, contextprop_selector, has_related_entities,
    _rqlcondition_selector)
from cubicweb.common.view import Template
from cubicweb.common.appobject import ReloadableMixIn

from cubicweb.web.htmlwidgets import (BoxLink, BoxWidget, SideBoxWidget,
                                      RawBoxItem, BoxSeparator)
from cubicweb.web.action import UnregisteredAction

_ = unicode


class BoxTemplate(Template):
    """base template for boxes, usually a (contextual) list of possible
    
    actions. Various classes attributes may be used to control the box
    rendering.
    
    You may override on of the formatting callbacks is this is not necessary
    for your custom box.
    
    Classes inheriting from this class usually only have to override call
    to fetch desired actions, and then to do something like  ::

        box.render(self.w)
    """
    __registry__ = 'boxes'
    __selectors__ = Template.__selectors__ + (contextprop_selector,)
    
    categories_in_order = ()
    property_defs = {
        _('visible'): dict(type='Boolean', default=True,
                           help=_('display the box or not')),
        _('order'):   dict(type='Int', default=99,
                           help=_('display order of the box')),
        # XXX 'incontext' boxes are handled by the default primary view
        _('context'): dict(type='String', default='left',
                           vocabulary=(_('left'), _('incontext'), _('right')),
                           help=_('context where this box should be displayed')),
        }
    context = 'left'
    htmlitemclass = 'boxItem'

    def sort_actions(self, actions):
        """return a list of (category, actions_sorted_by_title)"""
        result = []
        actions_by_cat = {}
        for action in actions:
            actions_by_cat.setdefault(action.category, []).append((action.title, action))
        for key, values in actions_by_cat.items():
            actions_by_cat[key] = [act for title, act in sorted(values)]
        for cat in self.categories_in_order:
            if cat in actions_by_cat:
                result.append( (cat, actions_by_cat[cat]) )
        for item in sorted(actions_by_cat.items()):
            result.append(item)
        return result

    def mk_action(self, title, path, escape=True, **kwargs):
        """factory function to create dummy actions compatible with the
        .format_actions method
        """
        if escape:
            title = html_escape(title)
        return self.box_action(self._action(title, path, **kwargs))
    
    def _action(self, title, path, **kwargs):
        return UnregisteredAction(self.req, self.rset, title, path, **kwargs)        

    # formating callbacks

    def boxitem_link_tooltip(self, action):
        if action.id:
            return u'keyword: %s' % action.id
        return u''

    def box_action(self, action):
        cls = getattr(action, 'html_class', lambda: None)() or self.htmlitemclass
        return BoxLink(action.url(), self.req._(action.title),
                       cls, self.boxitem_link_tooltip(action))
        

class RQLBoxTemplate(BoxTemplate):
    """abstract box for boxes displaying the content of a rql query not
    related to the current result set.
    
    It rely on etype, rtype (both optional, usable to control registration
    according to application schema and display according to connected
    user's rights) and rql attributes
    """
    __registerer__ = etype_rtype_priority_registerer
    __selectors__ = BoxTemplate.__selectors__ + (etype_rtype_selector,)

    rql  = None
    
    def to_display_rql(self):
        assert self.rql is not None, self.id
        return (self.rql,)
    
    def call(self, **kwargs):
        try:
            rset = self.req.execute(*self.to_display_rql())
        except Unauthorized:
            # can't access to something in the query, forget this box
            return
        if len(rset) == 0:
            return
        box = BoxWidget(self.req._(self.title), self.id)
        for i, (teid, tname) in enumerate(rset):
            entity = rset.get_entity(i, 0)
            box.append(self.mk_action(tname, entity.absolute_url()))
        box.render(w=self.w)

        
class UserRQLBoxTemplate(RQLBoxTemplate):
    """same as rql box template but the rql is build using the eid of the
    request's user
    """

    def to_display_rql(self):
        assert self.rql is not None, self.id
        return (self.rql, {'x': self.req.user.eid}, 'x')
    

class ExtResourcesBoxTemplate(BoxTemplate):
    """base class for boxes displaying external resources such as the RSS logo.
    It should list necessary resources with the .need_resources attribute.
    """
    __registerer__ = extresources_registerer
    need_resources = ()


class EntityBoxTemplate(BoxTemplate):
    """base class for boxes related to a single entity"""
    __registerer__ = accepts_registerer
    __selectors__ = (one_line_rset, primaryview_selector,
                     contextprop_selector, etype_rtype_selector,
                     accept_rtype_selector, accept_selector,
                     _rqlcondition_selector)
    accepts = ('Any',)
    context = 'incontext'
    condition = None
    
    def call(self, row=0, col=0, **kwargs):
        """classes inheriting from EntityBoxTemplate should defined cell_call,
        """
        self.cell_call(row, col, **kwargs)


class RelatedEntityBoxTemplate(EntityBoxTemplate):
    __selectors__ = EntityBoxTemplate.__selectors__ + (has_related_entities,)
    
    def cell_call(self, row, col, **kwargs):
        entity = self.entity(row, col)
        limit = self.req.property_value('navigation.related-limit') + 1
        role = get_role(self)
        self.w(u'<div class="sideRelated">')
        self.wview('sidebox', entity.related(self.rtype, role, limit=limit),
                   title=display_name(self.req, self.rtype, role))
        self.w(u'</div>')


class EditRelationBoxTemplate(ReloadableMixIn, EntityBoxTemplate):
    """base class for boxes which let add or remove entities linked
    by a given relation

    subclasses should define at least id, rtype and target
    class attributes.
    """
    
    def cell_call(self, row, col):
        self.req.add_js('cubicweb.ajax.js')
        entity = self.entity(row, col)
        box = SideBoxWidget(display_name(self.req, self.rtype), self.id)
        count = self.w_related(box, entity)
        if count:
            box.append(BoxSeparator())
        self.w_unrelated(box, entity)
        box.render(self.w)

    def div_id(self):
        return self.id

    @cached
    def xtarget(self):
        if self.target == 'subject':
            return 'object', 'subject'
        return 'subject', 'object'
        
    def box_item(self, entity, etarget, rql, label):
        """builds HTML link to edit relation between `entity` and `etarget`
        """
        x, target = self.xtarget()
        args = {x[0] : entity.eid, target[0] : etarget.eid}
        url = self.user_rql_callback((rql, args))
        # for each target, provide a link to edit the relation
        label = u'[<a href="%s">%s</a>] %s' % (url, label,
                                               etarget.view('incontext'))
        return RawBoxItem(label, liclass=u'invisible')
    
    def w_related(self, box, entity):
        """appends existing relations to the `box`"""
        rql = 'DELETE S %s O WHERE S eid %%(s)s, O eid %%(o)s' % self.rtype
        related = self.related_entities(entity)
        for etarget in related:
            box.append(self.box_item(entity, etarget, rql, u'-'))
        return len(related)
    
    def w_unrelated(self, box, entity):
        """appends unrelated entities to the `box`"""
        rql = 'SET S %s O WHERE S eid %%(s)s, O eid %%(o)s' % self.rtype
        for etarget in self.unrelated_entities(entity):
            box.append(self.box_item(entity, etarget, rql, u'+'))

    def unrelated_entities(self, entity):
        """returns the list of unrelated entities

        if etype is not defined on the Box's class, the default
        behaviour is to use the entity's appropraite vocabulary function
        """
        x, target = self.xtarget()
        # use entity.unrelated if we've been asked for a particular etype
        if hasattr(self, 'etype'):
            return entity.unrelated(self.rtype, self.etype, x).entities()
        # in other cases, use vocabulary functions
        entities = []
        for _, eid in entity.vocabulary(self.rtype, x):
            if eid is not None:
                rset = self.req.eid_rset(eid)
                entities.append(rset.get_entity(0, 0))
        return entities
        
    def related_entities(self, entity):
        x, target = self.xtarget()
        return entity.related(self.rtype, x, entities=True)

