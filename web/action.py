# copyright 2003-2012 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""abstract action classes for CubicWeb web client

Actions are typically displayed in an action box, but can also be used
in other parts of the interface (the user menu, the footer, etc.). The
'order', 'category' and 'title' class attributes control how the action will
be displayed. The 'submenu' attribute is only used for actions in the
action box.

The most important method from a developper point of view in the
:meth:'Action.url' method, which returns a URL on which the navigation
should directed to perform the action.  There are two common ways of
writing that method:

* do nothing special and simply return a URL to the current rset with
  a special view (with `self._cw.build_url(...)` for instance)

* define an inner function `callback_func(req, *args)` which will do
  the work and call it through `self._cw.user_callback(callback_func,
  args, msg)`: this method will return a URL which calls the inner
  function, and displays the message in the web interface when the
  callback has completed (and report any exception occuring in the
  callback too)

Many examples of the first approach are available in :mod:`cubicweb.web.views.actions`.

Here is an example of the second approach:

.. sourcecode:: python

 from cubicweb.web import action
 class SomeAction(action.Action):
     __regid__ = 'mycube_some_action'
     title = _(some action)
     __select__ = action.Action.__select__ & is_instance('TargetEntity')
 
     def url(self):
         if self.cw_row is None:
             eids = [row[0] for row in self.cw_rset]
         else:
             eids = (self.cw_rset[self.cw_row][self.cw_col or 0],)
         def do_action(req, eids):
             for eid in eids:
                 entity = req.entity_from_eid(eid, 'TargetEntity')
                 entity.perform_action()
         msg = self._cw._('some_action performed')
         return self._cw.user_callback(do_action, (eids,), msg)

"""

__docformat__ = "restructuredtext en"
_ = unicode

from cubicweb import target
from cubicweb.predicates import (partial_relation_possible, match_search_state,
                                 one_line_rset)
from cubicweb.appobject import AppObject


class Action(AppObject):
    """abstract action. Handle the .search_states attribute to match
    request search state.
    """
    __registry__ = 'actions'
    __select__ = match_search_state('normal')
    order = 99
    category = 'moreactions'
    # actions in category 'moreactions' can specify a sub-menu in which they should be filed
    submenu = None

    def actual_actions(self):
        yield self

    def fill_menu(self, box, menu):
        """add action(s) to the given submenu of the given box"""
        for action in self.actual_actions():
            menu.append(box.action_link(action))

    def html_class(self):
        if self._cw.selected(self.url()):
            return 'selected'

    def build_action(self, title, url, **kwargs):
        return UnregisteredAction(self._cw, title, url, **kwargs)

    def url(self):
        """return the url associated with this action"""
        raise NotImplementedError


class UnregisteredAction(Action):
    """non registered action, used to build boxes"""
    category = None
    id = None

    def __init__(self, req, title, url, **kwargs):
        Action.__init__(self, req)
        self.title = req._(title)
        self._url = url
        self.__dict__.update(kwargs)

    def url(self):
        return self._url


class LinkToEntityAction(Action):
    """base class for actions consisting to create a new object with an initial
    relation set to an entity.

    Additionaly to EntityAction behaviour, this class is parametrized using
    .rtype, .role and .target_etype attributes to check if the action apply and
    if the logged user has access to it (see
    :class:`~cubicweb.selectors.partial_relation_possible` selector
    documentation for more information).
    """
    __select__ = (match_search_state('normal') & one_line_rset()
                  & partial_relation_possible(action='add', strict=True))

    submenu = 'addrelated'
    # to be defined in concrete classes
    target_etype = rtype = None

    def url(self):
        ttype = self.target_etype
        entity = self.cw_rset.get_entity(self.cw_row or 0, self.cw_col or 0)
        linkto = '%s:%s:%s' % (self.rtype, entity.eid, target(self))
        return self._cw.vreg["etypes"].etype_class(ttype).cw_create_url(self._cw,
                                  __redirectpath=entity.rest_path(), __linkto=linkto,
                                  __redirectvid=self._cw.form.get('__redirectvid', ''))

