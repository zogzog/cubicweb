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
"""abstract component class and base components definition for CubicWeb web
client
"""

__docformat__ = "restructuredtext en"
_ = unicode

from logilab.common.deprecation import class_renamed
from logilab.mtconverter import xml_escape

from cubicweb import role
from cubicweb.utils import json_dumps
from cubicweb.uilib import js
from cubicweb.view import Component
from cubicweb.selectors import (
    paginated_rset, one_line_rset, primary_view, match_context_prop,
    partial_has_related_entities)


class EntityVComponent(Component):
    """abstract base class for additinal components displayed in content
    headers and footer according to:

    * the displayed entity's type
    * a context (currently 'header' or 'footer')

    it should be configured using .accepts, .etype, .rtype, .target and
    .context class attributes
    """

    __registry__ = 'contentnavigation'
    __select__ = one_line_rset() & primary_view() & match_context_prop()

    cw_property_defs = {
        _('visible'):  dict(type='Boolean', default=True,
                            help=_('display the component or not')),
        _('order'):    dict(type='Int', default=99,
                            help=_('display order of the component')),
        _('context'):  dict(type='String', default='navtop',
                            vocabulary=(_('navtop'), _('navbottom'),
                                        _('navcontenttop'), _('navcontentbottom'),
                                        _('ctxtoolbar')),
                            help=_('context where this component should be displayed')),
    }

    context = 'navcontentbottom'

    def call(self, view=None):
        if self.cw_rset is None:
            self.entity_call(self.cw_extra_kwargs.pop('entity'))
        else:
            self.cell_call(0, 0, view=view)

    def cell_call(self, row, col, view=None):
        self.entity_call(self.cw_rset.get_entity(row, col), view=view)

    def entity_call(self, entity, view=None):
        raise NotImplementedError()


class NavigationComponent(Component):
    """abstract base class for navigation components"""
    __regid__ = 'navigation'
    __select__ = paginated_rset()

    cw_property_defs = {
        _('visible'):  dict(type='Boolean', default=True,
                            help=_('display the component or not')),
        }

    page_size_property = 'navigation.page-size'
    start_param = '__start'
    stop_param = '__stop'
    page_link_templ = u'<span class="slice"><a href="%s" title="%s">%s</a></span>'
    selected_page_link_templ = u'<span class="selectedSlice"><a href="%s" title="%s">%s</a></span>'
    previous_page_link_templ = next_page_link_templ = page_link_templ
    no_previous_page_link = u'&lt;&lt;'
    no_next_page_link = u'&gt;&gt;'

    def __init__(self, req, rset, **kwargs):
        super(NavigationComponent, self).__init__(req, rset=rset, **kwargs)
        self.starting_from = 0
        self.total = rset.rowcount

    def get_page_size(self):
        try:
            return self._page_size
        except AttributeError:
            page_size = self.cw_extra_kwargs.get('page_size')
            if page_size is None:
                if 'page_size' in self._cw.form:
                    page_size = int(self._cw.form['page_size'])
                else:
                    page_size = self._cw.property_value(self.page_size_property)
            self._page_size = page_size
            return page_size

    def set_page_size(self, page_size):
        self._page_size = page_size

    page_size = property(get_page_size, set_page_size)

    def page_boundaries(self):
        try:
            stop = int(self._cw.form[self.stop_param]) + 1
            start = int(self._cw.form[self.start_param])
        except KeyError:
            start, stop = 0, self.page_size
        if start >= len(self.cw_rset):
            start, stop = 0, self.page_size
        self.starting_from = start
        return start, stop

    def clean_params(self, params):
        if self.start_param in params:
            del params[self.start_param]
        if self.stop_param in params:
            del params[self.stop_param]

    def page_url(self, path, params, start=None, stop=None):
        params = dict(params)
        if start is not None:
            params[self.start_param] = start
        if stop is not None:
            params[self.stop_param] = stop
        view = self.cw_extra_kwargs.get('view')
        if view is not None and hasattr(view, 'page_navigation_url'):
            url = view.page_navigation_url(self, path, params)
        elif path == 'json':
            url = self.ajax_page_url(**params)
        else:
            url = self._cw.build_url(path, **params)
        # XXX hack to avoid opening a new page containing the evaluation of the
        # js expression on ajax call
        if url.startswith('javascript:'):
            url += '; noop();'
        return url

    def ajax_page_url(self, **params):
        divid = params.setdefault('divid', 'pageContent')
        params['rql'] = self.cw_rset.printable_rql()
        return "javascript: $(%s).loadxhtml('json', %s, 'get', 'swap')" % (
            json_dumps('#'+divid), js.ajaxFuncArgs('view', params))

    def page_link(self, path, params, start, stop, content):
        url = xml_escape(self.page_url(path, params, start, stop))
        if start == self.starting_from:
            return self.selected_page_link_templ % (url, content, content)
        return self.page_link_templ % (url, content, content)

    def previous_link(self, path, params, content='&lt;&lt;', title=_('previous_results')):
        start = self.starting_from
        if not start :
            return self.no_previous_page_link
        start = max(0, start - self.page_size)
        stop = start + self.page_size - 1
        url = xml_escape(self.page_url(path, params, start, stop))
        return self.previous_page_link_templ % (url, title, content)

    def next_link(self, path, params, content='&gt;&gt;', title=_('next_results')):
        start = self.starting_from + self.page_size
        if start >= self.total:
            return self.no_next_page_link
        stop = start + self.page_size - 1
        url = xml_escape(self.page_url(path, params, start, stop))
        return self.next_page_link_templ % (url, title, content)


class RelatedObjectsVComponent(EntityVComponent):
    """a section to display some related entities"""
    __select__ = EntityVComponent.__select__ & partial_has_related_entities()

    vid = 'list'

    def rql(self):
        """override this method if you want to use a custom rql query"""
        return None

    def cell_call(self, row, col, view=None):
        rql = self.rql()
        if rql is None:
            entity = self.cw_rset.get_entity(row, col)
            rset = entity.related(self.rtype, role(self))
        else:
            eid = self.cw_rset[row][col]
            rset = self._cw.execute(self.rql(), {'x': eid})
        if not rset.rowcount:
            return
        self.w(u'<div class="%s">' % self.div_class())
        self.w(u'<h4>%s</h4>\n' % self._cw._(self.title).capitalize())
        self.wview(self.vid, rset)
        self.w(u'</div>')


VComponent = class_renamed('VComponent', Component,
                           'VComponent is deprecated, use Component')
SingletonVComponent = class_renamed('SingletonVComponent', Component,
                                    'SingletonVComponent is deprecated, use '
                                    'Component and explicit registration control')
