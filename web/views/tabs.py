"""base classes to handle tabbed views

:organization: Logilab
:copyright: 2008-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""

__docformat__ = "restructuredtext en"

from logilab.mtconverter import xml_escape

from cubicweb import NoSelectableObject, role
from cubicweb.selectors import partial_has_related_entities
from cubicweb.view import EntityView
from cubicweb.common import tags, uilib
from cubicweb.utils import make_uid

class LazyViewMixin(object):
    """provides two convenience methods for the tab machinery
    can also be used to lazy-load arbitrary views
    caveat : lazyview is not recursive, i.e : you can't (successfully)
    lazyload a view that in turns does the same
    """

    def _prepare_bindings(self, vid, reloadable):
        self.req.add_onload(u"""
  jQuery('#lazy-%(vid)s').bind('%(event)s', function(event) {
     load_now('#lazy-%(vid)s', '#%(vid)s-hole', %(reloadable)s);
  });""" % {'event': 'load_%s' % vid, 'vid': vid,
            'reloadable' : str(reloadable).lower()})

    def lazyview(self, vid, rql=None, eid=None, rset=None, static=False,
                 reloadable=False, show_spinbox=True, w=None):
        """a lazy version of wview
        first version only support lazy viewing for an entity at a time
        """
        assert rql or eid or rset or static, \
            'lazyview wants at least : rql, or an eid, or an rset -- or call it with static=True'
        w = w or self.w
        self.req.add_js('cubicweb.lazy.js')
        urlparams = {'vid' : vid, 'fname' : 'view'}
        if rql:
            urlparams['rql'] = rql
        elif eid:
            urlparams['rql'] = uilib.rql_for_eid(eid)
        elif rset:
            urlparams['rql'] = rset.printable_rql()
        w(u'<div id="lazy-%s" cubicweb:loadurl="%s">' % (
            vid, xml_escape(self.build_url('json', **urlparams))))
        if show_spinbox:
            w(u'<img src="data/loading.gif" id="%s-hole" alt="%s"/>'
              % (vid, self.req._('loading')))
        w(u'</div>')
        self._prepare_bindings(vid, reloadable)

    def forceview(self, vid):
        """trigger an event that will force immediate loading of the view
        on dom readyness
        """
        self.req.add_js('cubicweb.lazy.js')
        self.req.add_onload("trigger_load('%s');" % vid)


class TabsMixin(LazyViewMixin):
    """a tab mixin
    """

    @property
    def cookie_name(self):
        return str('%s_active_tab' % self.config.appid)

    def active_tab(self, tabs, default):
        formtab = self.req.form.get('tab')
        if formtab in tabs:
            return formtab
        cookies = self.req.get_cookie()
        cookiename = self.cookie_name
        activetab = cookies.get(cookiename)
        if activetab is None:
            cookies[cookiename] = default
            self.req.set_cookie(cookies, cookiename)
            tab = default
        else:
            tab = activetab.value
        return tab in tabs and tab or default

    def prune_tabs(self, tabs):
        selected_tabs = []
        for tab in tabs:
            try:
                self.vreg['views'].select(tab, self.req, rset=self.rset)
                selected_tabs.append(tab)
            except NoSelectableObject:
                continue
        return selected_tabs

    def render_tabs(self, tabs, default, entity=None):
        # delegate to the default tab if there is more than one entity
        # in the result set (tabs are pretty useless there)
        if entity and len(self.rset) > 1:
            entity.view(default, w=self.w)
            return
        self.req.add_css('ui.tabs.css')
        self.req.add_js(('ui.core.js', 'ui.tabs.js',
                         'cubicweb.ajax.js', 'cubicweb.tabs.js', 'cubicweb.lazy.js'))
        # prune tabs : not all are to be shown
        tabs = self.prune_tabs(tabs)
        # select a tab
        active_tab = self.active_tab(tabs, default)
        # build the html structure
        w = self.w
        uid = entity and entity.eid or make_uid('tab')
        w(u'<div id="entity-tabs-%s">' % uid)
        w(u'<ul>')
        for tab in tabs:
            w(u'<li>')
            w(u'<a href="#%s">' % tab)
            w(u'<span onclick="set_tab(\'%s\', \'%s\')">' % (tab, self.cookie_name))
            w(self.req._(tab))
            w(u'</span>')
            w(u'</a>')
            w(u'</li>')
        w(u'</ul>')
        w(u'</div>')
        for tab in tabs:
            w(u'<div id="%s">' % tab)
            if entity:
                self.lazyview(tab, eid=entity.eid)
            else:
                self.lazyview(tab, static=True)
            w(u'</div>')
        # call the set_tab() JS function *after* each tab is generated
        # because the callback binding needs to be done before
        # XXX make work history: true
        self.req.add_onload(u"""
  jQuery('#entity-tabs-%(eeid)s > ul').tabs( { selected: %(tabindex)s });
  set_tab('%(vid)s', '%(cookiename)s');
""" % {'tabindex'   : tabs.index(active_tab),
       'vid'        : active_tab,
       'eeid'       : (entity and entity.eid or uid),
       'cookiename' : self.cookie_name})


class EntityRelationView(EntityView):
    """view displaying entity related stuff.
    Such a view _must_ provide the rtype, target and vid attributes :

    Example :

    class ProjectScreenshotsView(EntityRelationView):
        '''display project's screenshots'''
        __regid__ = title = _('projectscreenshots')
        __select__ = EntityRelationView.__select__ & implements('Project')
        rtype = 'screenshot'
        role = 'subject'
        vid = 'gallery'

    in this example, entities related to project entity by the 'screenshot'
    relation (where the project is subject of the relation) will be displayed
    using the 'gallery' view.
    """
    __select__ = EntityView.__select__ & partial_has_related_entities()
    vid = 'list'

    def cell_call(self, row, col):
        rset = self.rset.get_entity(row, col).related(self.rtype, role(self))
        self.w(u'<div class="mainInfo">')
        if self.title:
            self.w(tags.h1(self.req._(self.title)))
        self.wview(self.vid, rset, 'noresult')
        self.w(u'</div>')
