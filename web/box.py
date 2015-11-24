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
"""abstract box classes for CubicWeb web client"""

__docformat__ = "restructuredtext en"
from cubicweb import _

from six import add_metaclass

from logilab.mtconverter import xml_escape
from logilab.common.deprecation import class_deprecated, class_renamed

from cubicweb import Unauthorized, role as get_role
from cubicweb.schema import display_name
from cubicweb.predicates import no_cnx, one_line_rset
from cubicweb.view import View
from cubicweb.web import INTERNAL_FIELD_VALUE, stdmsgs
from cubicweb.web.htmlwidgets import (BoxLink, BoxWidget, SideBoxWidget,
                                      RawBoxItem, BoxSeparator)
from cubicweb.web.action import UnregisteredAction


def sort_by_category(actions, categories_in_order=None):
    """return a list of (category, actions_sorted_by_title)"""
    result = []
    actions_by_cat = {}
    for action in actions:
        actions_by_cat.setdefault(action.category, []).append(
            (action.title, action) )
    for key, values in actions_by_cat.items():
        actions_by_cat[key] = [act for title, act in sorted(values, key=lambda x: x[0])]
    if categories_in_order:
        for cat in categories_in_order:
            if cat in actions_by_cat:
                result.append( (cat, actions_by_cat[cat]) )
    for item in sorted(actions_by_cat.items()):
        result.append(item)
    return result


# old box system, deprecated ###################################################

@add_metaclass(class_deprecated)
class BoxTemplate(View):
    """base template for boxes, usually a (contextual) list of possible
    actions. Various classes attributes may be used to control the box
    rendering.

    You may override one of the formatting callbacks if this is not necessary
    for your custom box.

    Classes inheriting from this class usually only have to override call
    to fetch desired actions, and then to do something like  ::

        box.render(self.w)
    """
    __deprecation_warning__ = '[3.10] *BoxTemplate classes are deprecated, use *CtxComponent instead (%(cls)s)'

    __registry__ = 'ctxcomponents'
    __select__ = ~no_cnx()

    categories_in_order = ()
    cw_property_defs = {
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

    def sort_actions(self, actions):
        """return a list of (category, actions_sorted_by_title)"""
        return sort_by_category(actions, self.categories_in_order)

    def mk_action(self, title, url, escape=True, **kwargs):
        """factory function to create dummy actions compatible with the
        .format_actions method
        """
        if escape:
            title = xml_escape(title)
        return self.box_action(self._action(title, url, **kwargs))

    def _action(self, title, url, **kwargs):
        return UnregisteredAction(self._cw, title, url, **kwargs)

    # formating callbacks

    def boxitem_link_tooltip(self, action):
        if action.__regid__:
            return u'keyword: %s' % action.__regid__
        return u''

    def box_action(self, action):
        klass = getattr(action, 'html_class', lambda: None)()
        return BoxLink(action.url(), self._cw._(action.title),
                       klass, self.boxitem_link_tooltip(action))


class RQLBoxTemplate(BoxTemplate):
    """abstract box for boxes displaying the content of a rql query not
    related to the current result set.
    """

    # to be defined in concrete classes
    rql = title = None

    def to_display_rql(self):
        assert self.rql is not None, self.__regid__
        return (self.rql,)

    def call(self, **kwargs):
        try:
            rset = self._cw.execute(*self.to_display_rql())
        except Unauthorized:
            # can't access to something in the query, forget this box
            return
        if len(rset) == 0:
            return
        box = BoxWidget(self._cw._(self.title), self.__regid__)
        for i, (teid, tname) in enumerate(rset):
            entity = rset.get_entity(i, 0)
            box.append(self.mk_action(tname, entity.absolute_url()))
        box.render(w=self.w)


class UserRQLBoxTemplate(RQLBoxTemplate):
    """same as rql box template but the rql is build using the eid of the
    request's user
    """

    def to_display_rql(self):
        assert self.rql is not None, self.__regid__
        return (self.rql, {'x': self._cw.user.eid})


class EntityBoxTemplate(BoxTemplate):
    """base class for boxes related to a single entity"""
    __select__ = BoxTemplate.__select__ & one_line_rset()
    context = 'incontext'

    def call(self, row=0, col=0, **kwargs):
        """classes inheriting from EntityBoxTemplate should define cell_call"""
        self.cell_call(row, col, **kwargs)

from cubicweb.web.component import AjaxEditRelationCtxComponent, EditRelationMixIn


class EditRelationBoxTemplate(EditRelationMixIn, EntityBoxTemplate):
    """base class for boxes which let add or remove entities linked
    by a given relation

    subclasses should define at least id, rtype and target
    class attributes.
    """
    rtype = None
    def cell_call(self, row, col, view=None, **kwargs):
        self._cw.add_js('cubicweb.ajax.js')
        entity = self.cw_rset.get_entity(row, col)
        title = display_name(self._cw, self.rtype, get_role(self),
                             context=entity.cw_etype)
        box = SideBoxWidget(title, self.__regid__)
        related = self.related_boxitems(entity)
        unrelated = self.unrelated_boxitems(entity)
        box.extend(related)
        if related and unrelated:
            box.append(BoxSeparator())
        box.extend(unrelated)
        box.render(self.w)

    def box_item(self, entity, etarget, rql, label):
        label = super(EditRelationBoxTemplate, self).box_item(
            entity, etarget, rql, label)
        return RawBoxItem(label, liclass=u'invisible')


AjaxEditRelationBoxTemplate = class_renamed(
    'AjaxEditRelationBoxTemplate', AjaxEditRelationCtxComponent,
    '[3.10] AjaxEditRelationBoxTemplate has been renamed to AjaxEditRelationCtxComponent (%(cls)s)')
