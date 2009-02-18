"""abstract action classes for CubicWeb web client

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

from cubicweb import role, target
from cubicweb.vregistry import objectify_selector
from cubicweb.selectors import (relation_possible, match_search_state,
                                one_line_rset, may_add_relation, yes,
                                accepts_compat, condition_compat, deprecate)
from cubicweb.appobject import AppRsetObject
from cubicweb.common.registerers import accepts_registerer

_ = unicode


class Action(AppRsetObject):
    """abstract action. Handle the .search_states attribute to match
    request search state. 
    """
    __registry__ = 'actions'
    __registerer__ = accepts_registerer
    __select__ = yes()
    
    property_defs = {
        'visible':  dict(type='Boolean', default=True,
                         help=_('display the action or not')),
        'order':    dict(type='Int', default=99,
                         help=_('display order of the action')),
        'category': dict(type='String', default='moreactions',
                         vocabulary=('mainactions', 'moreactions', 'addrelated',
                                     'useractions', 'siteactions', 'hidden'),
                         help=_('context where this component should be displayed')),
    }
    site_wide = True # don't want user to configuration actions eproperties
    category = 'moreactions'
    
    def url(self):
        """return the url associated with this action"""
        raise NotImplementedError
    
    def html_class(self):
        if self.req.selected(self.url()):
            return 'selected'
        if self.category:
            return 'box' + self.category.capitalize()


class UnregisteredAction(Action):
    """non registered action used to build boxes. Unless you set them
    explicitly, .vreg and .schema attributes at least are None.
    """
    category = None
    id = None
    
    def __init__(self, req, rset, title, path, **kwargs):
        Action.__init__(self, req, rset)
        self.title = req._(title)
        self._path = path
        self.__dict__.update(kwargs)
        
    def url(self):
        return self._path


class LinkToEntityAction(Action):
    """base class for actions consisting to create a new object
    with an initial relation set to an entity.
    Additionaly to EntityAction behaviour, this class is parametrized
    using .etype, .rtype and .target attributes to check if the
    action apply and if the logged user has access to it
    """
    @objectify_selector
    def my_selector(cls, req, rset, row=None, col=0, **kwargs):
        selector = (match_search_state('normal') & one_line_rset()
                    & relation_possible(cls.rtype, role(cls), cls.etype,
                                        action='add')
                    & may_add_relation(cls.rtype, role(cls)))
        return selector(cls, req, rset, row, col, **kwargs)

    __select__ = my_selector()
    registered = accepts_compat(Action.registered)
    
    category = 'addrelated'
                
    def url(self):
        current_entity = self.rset.get_entity(self.row or 0, self.col or 0)
        linkto = '%s:%s:%s' % (self.rtype, current_entity.eid, target(self))
        return self.build_url(vid='creation', etype=self.etype,
                              __linkto=linkto,
                              __redirectpath=current_entity.rest_path(), # should not be url quoted!
                              __redirectvid=self.req.form.get('__redirectvid', ''))

class EntityAction(Action):
    """DEPRECATED / BACKWARD COMPAT
    """
    registered = deprecate(accepts_compat(condition_compat(Action.registered)),
                           msg='EntityAction is deprecated, use Action with '
                           'appropriate selectors')
    
