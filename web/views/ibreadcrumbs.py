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
"""navigation components definition for CubicWeb web client

"""
__docformat__ = "restructuredtext en"
_ = unicode

from logilab.mtconverter import xml_escape

from cubicweb.interfaces import IBreadCrumbs
from cubicweb.selectors import (one_line_rset, implements, one_etype_rset,
                                multi_lines_rset, any_rset)
from cubicweb.view import EntityView, Component
# don't use AnyEntity since this may cause bug with isinstance() due to reloading
from cubicweb.entity import Entity
from cubicweb import tags, uilib


class BreadCrumbEntityVComponent(Component):
    __regid__ = 'breadcrumbs'
    __select__ = one_line_rset() & implements(IBreadCrumbs, accept_none=False)

    cw_property_defs = {
        _('visible'):  dict(type='Boolean', default=True,
                            help=_('display the component or not')),
        }
    title = _('contentnavigation_breadcrumbs')
    help = _('contentnavigation_breadcrumbs_description')
    separator = u'&#160;&gt;&#160;'
    link_template = u'<a href="%s">%s</a>'

    def call(self, view=None, first_separator=True):
        entity = self.cw_rset.get_entity(0, 0)
        path = entity.breadcrumbs(view)
        if path:
            self.open_breadcrumbs()
            if first_separator:
                self.w(self.separator)
            self.render_breadcrumbs(entity, path)
            self.close_breadcrumbs()

    def open_breadcrumbs(self):
        self.w(u'<span id="breadcrumbs" class="pathbar">')

    def close_breadcrumbs(self):
        self.w(u'</span>')

    def render_breadcrumbs(self, contextentity, path):
        root = path.pop(0)
        if isinstance(root, Entity):
            self.w(self.link_template % (self._cw.build_url(root.__regid__),
                                         root.dc_type('plural')))
            self.w(self.separator)
        self.wpath_part(root, contextentity, not path)
        for i, parent in enumerate(path):
            self.w(self.separator)
            self.w(u"\n")
            self.wpath_part(parent, contextentity, i == len(path) - 1)

    def wpath_part(self, part, contextentity, last=False):
        if isinstance(part, Entity):
            self.w(part.view('breadcrumbs'))
        elif isinstance(part, tuple):
            url, title = part
            textsize = self._cw.property_value('navigation.short-line-size')
            self.w(self.link_template % (
                xml_escape(url), xml_escape(uilib.cut(title, textsize))))
        else:
            textsize = self._cw.property_value('navigation.short-line-size')
            self.w(uilib.cut(unicode(part), textsize))


class BreadCrumbETypeVComponent(BreadCrumbEntityVComponent):
    __select__ = multi_lines_rset() & one_etype_rset() & \
                 implements(IBreadCrumbs, accept_none=False)

    def render_breadcrumbs(self, contextentity, path):
        # XXX hack: only display etype name or first non entity path part
        root = path.pop(0)
        if isinstance(root, Entity):
            self.w(u'<a href="%s">%s</a>' % (self._cw.build_url(root.__regid__),
                                             root.dc_type('plural')))
        else:
            self.wpath_part(root, contextentity, not path)


class BreadCrumbAnyRSetVComponent(BreadCrumbEntityVComponent):
    __select__ = any_rset()

    def call(self, view=None, first_separator=True):
        self.w(u'<span id="breadcrumbs" class="pathbar">')
        if first_separator:
            self.w(self.separator)
        self.w(self._cw._('search'))
        self.w(u'</span>')


class BreadCrumbView(EntityView):
    __regid__ = 'breadcrumbs'

    def cell_call(self, row, col, **kwargs):
        entity = self.cw_rset.get_entity(row, col)
        desc = xml_escape(uilib.cut(entity.dc_description(), 50))
        # XXX remember camember : tags.a autoescapes !
        self.w(tags.a(entity.view('breadcrumbtext'),
                      href=entity.absolute_url(), title=desc))


class BreadCrumbTextView(EntityView):
    __regid__ = 'breadcrumbtext'

    def cell_call(self, row, col, **kwargs):
        entity = self.cw_rset.get_entity(row, col)
        textsize = self._cw.property_value('navigation.short-line-size')
        self.w(uilib.cut(entity.dc_title(), textsize))
