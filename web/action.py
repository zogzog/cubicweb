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
"""abstract action classes for CubicWeb web client"""

__docformat__ = "restructuredtext en"
_ = unicode

from cubicweb import target
from cubicweb.selectors import (partial_relation_possible, match_search_state,
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
            menu.append(box.box_action(action))

    def url(self):
        """return the url associated with this action"""
        raise NotImplementedError

    def html_class(self):
        if self._cw.selected(self.url()):
            return 'selected'
        if self.category:
            return 'box' + self.category.capitalize()

    def build_action(self, title, path, **kwargs):
        return UnregisteredAction(self._cw, self.cw_rset, title, path, **kwargs)


class UnregisteredAction(Action):
    """non registered action used to build boxes. Unless you set them
    explicitly, .vreg and .schema attributes at least are None.
    """
    category = None
    id = None

    def __init__(self, req, rset, title, path, **kwargs):
        Action.__init__(self, req, rset=rset)
        self.title = req._(title)
        self._path = path
        self.__dict__.update(kwargs)

    def url(self):
        return self._path


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

    def url(self):
        try:
            ttype = self.etype # deprecated in 3.6, already warned by the selector
        except AttributeError:
            ttype = self.target_etype
        entity = self.cw_rset.get_entity(self.cw_row or 0, self.cw_col or 0)
        linkto = '%s:%s:%s' % (self.rtype, entity.eid, target(self))
        return self._cw.build_url('add/%s' % ttype, __linkto=linkto,
                                  __redirectpath=entity.rest_path(),
                                  __redirectvid=self._cw.form.get('__redirectvid', ''))

