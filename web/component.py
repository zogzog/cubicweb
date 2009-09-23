"""abstract component class and base components definition for CubicWeb web client

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"
_ = unicode

from simplejson import dumps

from logilab.common.deprecation import class_renamed
from logilab.mtconverter import xml_escape

from cubicweb import role
from cubicweb.utils import merge_dicts
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
        _('context'):  dict(type='String', default='header',
                            vocabulary=(_('navtop'), _('navbottom'),
                                        _('navcontenttop'), _('navcontentbottom')),
                            #vocabulary=(_('header'), _('incontext'), _('footer')),
                            help=_('context where this component should be displayed')),
    }

    context = 'navcontentbottom' # 'footer' | 'header' | 'incontext'

    def call(self, view=None):
        return self.cell_call(0, 0, view=view)

    def cell_call(self, row, col, view=None):
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
            page_size = self.extra_kwargs.get('page_size')
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
        self.starting_from = start
        return start, stop

    def clean_params(self, params):
        if self.start_param in params:
            del params[self.start_param]
        if self.stop_param in params:
            del params[self.stop_param]

    def page_url(self, path, params, start, stop):
        params = merge_dicts(params, {self.start_param : start,
                                      self.stop_param : stop,})
        if path == 'json':
            rql = params.pop('rql', self.cw_rset.printable_rql())
            # latest 'true' used for 'swap' mode
            url = 'javascript: replacePageChunk(%s, %s, %s, %s, true)' % (
                dumps(params.get('divid', 'paginated-content')),
                dumps(rql), dumps(params.pop('vid', None)), dumps(params))
        else:
            url = self._cw.build_url(path, **params)
        return url

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
            rset = self._cw.execute(self.rql(), {'x': eid}, 'x')
        if not rset.rowcount:
            return
        self.w(u'<div class="%s">' % self.div_class())
        self.wview(self.vid, rset, title=self._cw._(self.title).capitalize())
        self.w(u'</div>')


VComponent = class_renamed('VComponent', Component,
                           'VComponent is deprecated, use Component')
SingletonVComponent = class_renamed('SingletonVComponent', Component,
                                    'SingletonVComponent is deprecated, use '
                                    'Component and explicit registration control')
