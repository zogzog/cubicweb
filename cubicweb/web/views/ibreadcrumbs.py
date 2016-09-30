# copyright 2003-2014 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""breadcrumbs components definition for CubicWeb web client"""


from cubicweb import _

from warnings import warn

from six import text_type

from logilab.mtconverter import xml_escape

from cubicweb import tags, uilib
from cubicweb.entity import Entity
from cubicweb.predicates import (is_instance, one_line_rset, adaptable,
                                one_etype_rset, multi_lines_rset, any_rset,
                                match_form_params)
from cubicweb.view import EntityView, EntityAdapter
from cubicweb.web.views import basecomponents
# don't use AnyEntity since this may cause bug with isinstance() due to reloading



class IBreadCrumbsAdapter(EntityAdapter):
    """adapters for entities which can be"located" on some path to display in
    the web ui
    """
    __regid__ = 'IBreadCrumbs'
    __select__ = is_instance('Any', accept_none=False)

    def parent_entity(self):
        itree = self.entity.cw_adapt_to('ITree')
        if itree is not None:
            return itree.parent()
        return None

    def breadcrumbs(self, view=None, recurs=None):
        """return a list containing some:

        * tuple (url, label)
        * entity
        * simple label string

        defining path from a root to the current view

        the main view is given as argument so breadcrumbs may vary according to
        displayed view (may be None). When recursing on a parent entity, the
        `recurs` argument should be a set of already traversed nodes (infinite
        loop safety belt).
        """
        parent = self.parent_entity()
        if parent is not None:
            if recurs:
                _recurs = recurs
            else:
                _recurs = set()
            if _recurs and parent.eid in _recurs:
                self.error('cycle in breadcrumbs for entity %s' % self.entity)
                return []
            _recurs.add(parent.eid)
            adapter = parent.cw_adapt_to('IBreadCrumbs')
            path = adapter.breadcrumbs(view, _recurs) + [self.entity]
        else:
            path = [self.entity]
        if not recurs:
            if view is None:
                if 'vtitle' in self._cw.form:
                    # embeding for instance
                    path.append( self._cw.form['vtitle'] )
            elif view.__regid__ != 'primary' and hasattr(view, 'title'):
                path.append( self._cw._(view.title) )
        return path


class BreadCrumbEntityVComponent(basecomponents.HeaderComponent):
    __regid__ = 'breadcrumbs'
    __select__ = (basecomponents.HeaderComponent.__select__
                  & one_line_rset() & adaptable('IBreadCrumbs'))
    order = basecomponents.ApplicationName.order + 1
    context = basecomponents.ApplicationName.context
    separator = u'&#160;&gt;&#160;'
    link_template = u'<a href="%s">%s</a>'
    first_separator = True

    # XXX support kwargs for compat with other components which gets the view as
    # argument
    def render(self, w, **kwargs):
        try:
            entity = self.cw_extra_kwargs['entity']
        except KeyError:
            entity = self.cw_rset.get_entity(0, 0)
        adapter = entity.cw_adapt_to('IBreadCrumbs')
        view = self.cw_extra_kwargs.get('view')
        path = adapter.breadcrumbs(view)
        if path:
            self.open_breadcrumbs(w)
            self.render_breadcrumbs(w, entity, path)
            self.close_breadcrumbs(w)

    def open_breadcrumbs(self, w):
        w(u'<span id="breadcrumbs" class="pathbar">')
        if self.first_separator:
            w(self.separator)

    def close_breadcrumbs(self, w):
        w(u'</span>')

    def render_root(self, w, contextentity, path):
        root = path.pop(0)
        if isinstance(root, Entity):
            w(self.link_template % (self._cw.build_url(root.__regid__),
                                         root.dc_type('plural')))
            w(self.separator)
        self.wpath_part(w, root, contextentity, not path)
 
    def render_breadcrumbs(self, w, contextentity, path):
        self.render_root(w, contextentity, path)
        for i, parent in enumerate(path):
            w(self.separator)
            w(u"\n")
            self.wpath_part(w, parent, contextentity, i == len(path) - 1)

    def wpath_part(self, w, part, contextentity, last=False): # XXX deprecates last argument?
        if isinstance(part, Entity):
            w(part.view('breadcrumbs'))
        elif isinstance(part, tuple):
            url, title = part
            textsize = self._cw.property_value('navigation.short-line-size')
            w(self.link_template % (
                xml_escape(url), xml_escape(uilib.cut(title, textsize))))
        else:
            textsize = self._cw.property_value('navigation.short-line-size')
            w(xml_escape(uilib.cut(text_type(part), textsize)))


class BreadCrumbETypeVComponent(BreadCrumbEntityVComponent):
    __select__ = (basecomponents.HeaderComponent.__select__
                  & multi_lines_rset() & one_etype_rset()
                  & adaptable('IBreadCrumbs'))

    def render_breadcrumbs(self, w, contextentity, path):
        # XXX hack: only display etype name or first non entity path part
        root = path.pop(0)
        if isinstance(root, Entity):
            w(u'<a href="%s">%s</a>' % (self._cw.build_url(root.__regid__),
                                        root.dc_type('plural')))
        else:
            self.wpath_part(w, root, contextentity, not path)


class BreadCrumbAnyRSetVComponent(BreadCrumbEntityVComponent):
    __select__ = basecomponents.HeaderComponent.__select__ & any_rset()

    # XXX support kwargs for compat with other components which gets the view as
    # argument
    def render(self, w, **kwargs):
        self.open_breadcrumbs(w)
        w(self._cw._('search'))
        self.close_breadcrumbs(w)


class BreadCrumbLinkToVComponent(BreadCrumbEntityVComponent):
    __select__ = basecomponents.HeaderComponent.__select__ & match_form_params('__linkto')

    def render(self, w, **kwargs):
        eid = self._cw.list_form_param('__linkto')[0].split(':')[1]
        entity = self._cw.entity_from_eid(eid)
        ecmp = self._cw.vreg[self.__registry__].select(
            self.__regid__, self._cw, entity=entity, **kwargs)
        ecmp.render(w, **kwargs)


class BreadCrumbView(EntityView):
    __regid__ = 'breadcrumbs'

    def cell_call(self, row, col, **kwargs):
        entity = self.cw_rset.get_entity(row, col)
        desc = uilib.cut(entity.dc_description(), 50)
        # NOTE remember camember: tags.a autoescapes
        self.w(tags.a(entity.view('breadcrumbtext'),
                      href=entity.absolute_url(), title=desc))


class BreadCrumbTextView(EntityView):
    __regid__ = 'breadcrumbtext'

    def cell_call(self, row, col, **kwargs):
        entity = self.cw_rset.get_entity(row, col)
        textsize = self._cw.property_value('navigation.short-line-size')
        self.w(uilib.cut(entity.dc_title(), textsize))
