"""abstract component class and base components definition for CubicWeb web client

:organization: Logilab
:copyright: 2001-2008 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

from cubicweb.common.appobject import Component, SingletonComponent
from cubicweb.common.utils import merge_dicts
from cubicweb.common.view import VComponent, SingletonVComponent
from cubicweb.common.registerers import action_registerer
from cubicweb.common.selectors import (largerset_selector, onelinerset_selector, 
                                    etype_rtype_selector, rqlcondition_selector,
                                    accept_selector, contextprop_selector,
                                    primaryview_selector, accept_rtype_selector)
from cubicweb.common.uilib import html_escape

_ = unicode


class EntityVComponent(VComponent):
    """abstract base class for additinal components displayed in content
    headers and footer according to:
    
    * the displayed entity's type
    * a context (currently 'header' or 'footer')

    it should be configured using .accepts, .etype, .rtype, .target and
    .context class attributes
    """
    
    __registry__ = 'contentnavigation'
    __registerer__ = action_registerer    
    __selectors__ = (onelinerset_selector, primaryview_selector,
                     contextprop_selector, etype_rtype_selector,
                     accept_rtype_selector, accept_selector,
                     rqlcondition_selector)
    
    property_defs = {
        _('visible'):  dict(type='Boolean', default=True,
                            help=_('display the box or not')),
        _('order'):    dict(type='Int', default=99,
                            help=_('display order of the component')),
        _('context'):  dict(type='String', default='header',
                            vocabulary=(_('navtop'), _('navbottom'), 
                                        _('navcontenttop'), _('navcontentbottom')),
                            #vocabulary=(_('header'), _('incontext'), _('footer')),
                            help=_('context where this component should be displayed')),
        _('htmlclass'):dict(type='String', default='mainRelated',
                            help=_('html class of the component')),
    }
    
    accepts = ('Any',)
    context = 'navcontentbottom' # 'footer' | 'header' | 'incontext'
    condition = None
    
    def call(self, view):
        raise RuntimeError()

    
class NavigationComponent(VComponent):
    """abstract base class for navigation components"""
    __selectors__ = (largerset_selector,)
    id = 'navigation'
    page_size_property = 'navigation.page-size'
    start_param = '__start'
    stop_param = '__stop'
    page_link_templ = u'<span class="slice"><a href="%s" title="%s">%s</a></span>'
    selected_page_link_templ = u'<span class="selectedSlice"><a href="%s" title="%s">%s</a></span>'
    previous_page_link_templ = next_page_link_templ = page_link_templ
    no_previous_page_link = no_next_page_link = u''
    
    def __init__(self, req, rset):
        super(NavigationComponent, self).__init__(req, rset)
        self.starting_from = 0
        self.total = rset.rowcount

    def get_page_size(self):
        try:
            return self._page_size
        except AttributeError:
            self._page_size = self.req.property_value(self.page_size_property)
            return self._page_size

    def set_page_size(self, page_size):
        self._page_size = page_size
        
    page_size = property(get_page_size, set_page_size)
    
    def page_boundaries(self):
        try:
            stop = int(self.req.form[self.stop_param]) + 1
            start = int(self.req.form[self.start_param])
        except KeyError:
            start, stop = 0, self.page_size
        self.starting_from = start
        return start, stop
        
    def clean_params(self, params):
        if self.start_param in params:
            del params[self.start_param]
        if self.stop_param in params:
            del params[self.stop_param]

    def page_link(self, path, params, start, stop, content):
        url = self.build_url(path, **merge_dicts(params, {self.start_param : start,
                                                          self.stop_param : stop,}))
        url = html_escape(url)
        if start == self.starting_from:
            return self.selected_page_link_templ % (url, content, content)
        return self.page_link_templ % (url, content, content)

    def previous_link(self, params, content='&lt;&lt;', title=_('previous_results')):
        start = self.starting_from
        if not start :
            return self.no_previous_page_link
        start = max(0, start - self.page_size)
        stop = start + self.page_size - 1
        url = self.build_url(**merge_dicts(params, {self.start_param : start,
                                                    self.stop_param : stop,}))
        url = html_escape(url)
        return self.previous_page_link_templ % (url, title, content)

    def next_link(self, params, content='&gt;&gt;', title=_('next_results')):
        start = self.starting_from + self.page_size
        if start >= self.total:
            return self.no_next_page_link
        stop = start + self.page_size - 1
        url = self.build_url(**merge_dicts(params, {self.start_param : start,
                                                    self.stop_param : stop,}))
        url = html_escape(url)
        return self.next_page_link_templ % (url, title, content)


class RelatedObjectsVComponent(EntityVComponent):
    """a section to display some related entities"""
    __selectors__ = (onelinerset_selector, primaryview_selector,
                     etype_rtype_selector, accept_rtype_selector,
                     contextprop_selector, accept_selector)
    vid = 'list'

    def rql(self):
        """override this method if you want to use a custom rql query.
        """
        return None
    
    def call(self, view=None):
        rql = self.rql()
        if rql is None:
            entity = self.rset.get_entity(0, 0)
            if self.target == 'object':
                role = 'subject'
            else:
                role = 'object'
            rset = entity.related(self.rtype, role)
        else:
            eid = self.rset[0][0]
            rset = self.req.execute(self.rql(), {'x': eid}, 'x')
        if not rset.rowcount:
            return
        self.w(u'<div class="%s">' % self.div_class())
        self.wview(self.vid, rset, title=self.req._(self.title).capitalize())
        self.w(u'</div>')
