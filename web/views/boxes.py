# copyright 2003-2011 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""Generic boxes for CubicWeb web client:

* actions box
* search box

Additional boxes (disabled by default):
* schema box
* possible views box
* startup views box
"""
__docformat__ = "restructuredtext en"
_ = unicode

from warnings import warn

from logilab.mtconverter import xml_escape
from logilab.common.deprecation import class_deprecated

from cubicweb import Unauthorized
from cubicweb.predicates import (match_user_groups, match_kwargs,
                                non_final_entity, nonempty_rset,
                                match_context, contextual)
from cubicweb.utils import wrap_on_write
from cubicweb.view import EntityView
from cubicweb.schema import display_name
from cubicweb.web import component, box, htmlwidgets

# XXX bw compat, some cubes import this class from here
BoxTemplate = box.BoxTemplate
BoxHtml = htmlwidgets.BoxHtml

class EditBox(component.CtxComponent):
    """
    box with all actions impacting the entity displayed: edit, copy, delete
    change state, add related entities...
    """
    __regid__ = 'edit_box'

    title = _('actions')
    order = 2
    contextual = True
    __select__ = component.CtxComponent.__select__ & non_final_entity()

    def init_rendering(self):
        super(EditBox, self).init_rendering()
        _ = self._cw._
        self._menus_in_order = []
        self._menus_by_id = {}
        # build list of actions
        actions = self._cw.vreg['actions'].possible_actions(self._cw, self.cw_rset,
                                                            **self.cw_extra_kwargs)
        other_menu = self._get_menu('moreactions', _('more actions'))
        for category, defaultmenu in (('mainactions', self),
                                      ('moreactions', other_menu),
                                      ('addrelated', None)):
            for action in actions.get(category, ()):
                if action.submenu:
                    menu = self._get_menu(action.submenu)
                else:
                    menu = defaultmenu
                action.fill_menu(self, menu)
        # if we've nothing but actions in the other_menu, add them directly into the box
        if not self.items and len(self._menus_by_id) == 1 and not other_menu.is_empty():
            self.items = other_menu.items
        else: # ensure 'more actions' menu appears last
            self._menus_in_order.remove(other_menu)
            self._menus_in_order.append(other_menu)
            for submenu in self._menus_in_order:
                self.add_submenu(self, submenu)
        if not self.items:
            raise component.EmptyComponent()

    def render_title(self, w):
        title = self._cw._(self.title)
        if self.cw_rset:
            etypes = self.cw_rset.column_types(0)
            if len(etypes) == 1:
                plural = self.cw_rset.rowcount > 1 and 'plural' or ''
                etypelabel = display_name(self._cw, iter(etypes).next(), plural)
                title = u'%s - %s' % (title, etypelabel.lower())
        w(title)

    def render_body(self, w):
        self.render_items(w)

    def _get_menu(self, id, title=None, label_prefix=None):
        try:
            return self._menus_by_id[id]
        except KeyError:
            if title is None:
                title = self._cw._(id)
            self._menus_by_id[id] = menu = htmlwidgets.BoxMenu(title)
            menu.label_prefix = label_prefix
            self._menus_in_order.append(menu)
            return menu

    def add_submenu(self, box, submenu, label_prefix=None):
        appendanyway = getattr(submenu, 'append_anyway', False)
        if len(submenu.items) == 1 and not appendanyway:
            boxlink = submenu.items[0]
            if submenu.label_prefix:
                # XXX iirk
                if hasattr(boxlink, 'label'):
                    boxlink.label = u'%s %s' % (submenu.label_prefix, boxlink.label)
                else:
                    boxlink = u'%s %s' % (submenu.label_prefix, boxlink)
            box.append(boxlink)
        elif submenu.items:
            box.append(submenu)
        elif appendanyway:
            box.append(xml_escape(submenu.label))


class SearchBox(component.CtxComponent):
    """display a box with a simple search form"""
    __regid__ = 'search_box'

    title = _('search')
    order = 0
    formdef = u"""<form action="%(action)s">
<table id="%(id)s"><tr><td>
<input class="norql" type="text" accesskey="q" tabindex="%(tabindex1)s" title="search text" value="%(value)s" name="rql" />
<input type="hidden" name="__fromsearchbox" value="1" />
<input type="hidden" name="subvid" value="tsearch" />
</td><td>
<input tabindex="%(tabindex2)s" type="submit" class="rqlsubmit" value="" />
 </td></tr></table>
 </form>"""

    def render_title(self, w):
        w(u"""<span onclick="javascript: toggleVisibility('rqlinput')">%s</span>"""
          % self._cw._(self.title))

    def render_body(self, w):
        if self._cw.form.pop('__fromsearchbox', None):
            rql = self._cw.form.get('rql', '')
        else:
            rql = ''
        tabidx1 = self._cw.next_tabindex()
        tabidx2 = self._cw.next_tabindex()
        w(self.formdef % {'action': self._cw.build_url('view'),
                          'value': xml_escape(rql),
                          'id': self.cw_extra_kwargs.get('domid', 'tsearch'),
                          'tabindex1': tabidx1,
                          'tabindex2': tabidx2})


# boxes disabled by default ###################################################

class PossibleViewsBox(component.CtxComponent):
    """display a box containing links to all possible views"""
    __regid__ = 'possible_views_box'

    contextual = True
    title = _('possible views')
    order = 10
    visible = False # disabled by default

    def init_rendering(self):
        self.views = [v for v in self._cw.vreg['views'].possible_views(self._cw,
                                                                       rset=self.cw_rset)
                      if v.category != 'startupview']
        if not self.views:
            raise component.EmptyComponent()
        self.items = []

    def render_body(self, w):
        for category, views in box.sort_by_category(self.views):
            menu = htmlwidgets.BoxMenu(self._cw._(category), ident=category)
            for view in views:
                menu.append(self.action_link(view))
            self.append(menu)
        self.render_items(w)


class StartupViewsBox(PossibleViewsBox):
    """display a box containing links to all startup views"""
    __regid__ = 'startup_views_box'

    contextual = False
    title = _('startup views')
    order = 70
    visible = False # disabled by default

    def init_rendering(self):
        self.views = [v for v in self._cw.vreg['views'].possible_views(self._cw)
                      if v.category == 'startupview']
        if not self.views:
            raise component.EmptyComponent()
        self.items = []


class RsetBox(component.CtxComponent):
    """helper view class to display an rset in a sidebox"""
    __select__ = nonempty_rset() & match_kwargs('title', 'vid')
    __regid__ = 'rsetbox'
    cw_property_defs = {}
    context = 'incontext'

    @property
    def domid(self):
        return super(RsetBox, self).domid + unicode(abs(id(self))) + unicode(abs(id(self.cw_rset)))

    def render_title(self, w):
        w(self.cw_extra_kwargs['title'])

    def render_body(self, w):
        if 'dispctrl' in self.cw_extra_kwargs:
            # XXX do not modify dispctrl!
            self.cw_extra_kwargs['dispctrl'].setdefault('subvid', 'outofcontext')
            self.cw_extra_kwargs['dispctrl'].setdefault('use_list_limit', 1)
        self._cw.view(self.cw_extra_kwargs['vid'], self.cw_rset, w=w,
                      initargs=self.cw_extra_kwargs)

 # helper classes ##############################################################

class SideBoxView(EntityView):
    """helper view class to display some entities in a sidebox"""
    __metaclass__ = class_deprecated
    __deprecation_warning__ = '[3.10] SideBoxView is deprecated, use RsetBox instead (%(cls)s)'

    __regid__ = 'sidebox'

    def call(self, title=u'', **kwargs):
        """display a list of entities by calling their <item_vid> view"""
        if 'dispctrl' in self.cw_extra_kwargs:
            # XXX do not modify dispctrl!
            self.cw_extra_kwargs['dispctrl'].setdefault('subvid', 'outofcontext')
            self.cw_extra_kwargs['dispctrl'].setdefault('use_list_limit', 1)
        if title:
            self.cw_extra_kwargs['title'] = title
        self.cw_extra_kwargs.setdefault('context', 'incontext')
        box = self._cw.vreg['ctxcomponents'].select(
            'rsetbox', self._cw, rset=self.cw_rset, vid='autolimited',
            **self.cw_extra_kwargs)
        box.render(self.w)


class ContextualBoxLayout(component.Layout):
    __select__ = match_context('incontext', 'left', 'right') & contextual()
    # predefined class in cubicweb.css: contextualBox | contextFreeBox
    cssclass = 'contextualBox'

    def render(self, w):
        if self.init_rendering():
            view = self.cw_extra_kwargs['view']
            w(u'<div class="%s %s" id="%s">' % (self.cssclass, view.cssclass,
                                                view.domid))
            with wrap_on_write(w, u'<div class="boxTitle"><span>',
                               u'</span></div>') as wow:
                view.render_title(wow)
            w(u'<div class="boxBody">')
            view.render_body(w)
            # boxFooter div is a CSS place holder (for shadow for example)
            w(u'</div><div class="boxFooter"></div></div>\n')


class ContextFreeBoxLayout(ContextualBoxLayout):
    __select__ = match_context('incontext', 'left', 'right') & ~contextual()
    cssclass = 'contextFreeBox'
