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
"""management and error screens"""

__docformat__ = "restructuredtext en"
_ = unicode

from time import strftime, localtime

from logilab.mtconverter import xml_escape

from cubicweb import BadConnectionId
from cubicweb.predicates import none_rset, match_user_groups
from cubicweb.view import StartupView
from cubicweb.web.views import actions, tabs

def dict_to_html(w, dict):
    # XHTML doesn't allow emtpy <ul> nodes
    if dict:
        w(u'<ul>')
        for key in sorted(dict):
            w(u'<li><span class="label">%s</span>: <span>%s</span></li>' % (
                xml_escape(str(key)), xml_escape(repr(dict[key]))))
        w(u'</ul>')


class SiteInfoAction(actions.ManagersAction):
    __regid__ = 'siteinfo'
    __select__ = match_user_groups('users','managers')
    title = _('Site information')
    category = 'manage'
    order = 1000


class SiteInfoView(tabs.TabsMixin, StartupView):
    __regid__ = 'siteinfo'
    title = _('Site information')
    tabs = [_('info'), _('registry'), _('gc')]
    default_tab = 'info'

    def call(self, **kwargs):
        """The default view representing the instance's management"""
        self.w(u'<h1>%s</h1>' % self._cw._(self.title))
        self.render_tabs(self.tabs, self.default_tab)


class ProcessInformationView(StartupView):
    """display various web server /repository information"""
    __regid__ = 'info'
    __select__ = none_rset() & match_user_groups('managers', 'users')

    title = _('server information')
    cache_max_age = 0

    def call(self, **kwargs):
        req = self._cw
        dtformat = req.property_value('ui.datetime-format')
        _ = req._
        w = self.w
        # generic instance information
        w(u'<h2>%s</h2>' % _('Instance'))
        w(u'<table>')
        w(u'<tr><th align="left">%s</th><td>%s</td></tr>' % (
            _('config type'), self._cw.vreg.config.name))
        w(u'<tr><th align="left">%s</th><td>%s</td></tr>' % (
            _('config mode'), self._cw.vreg.config.mode))
        w(u'<tr><th align="left">%s</th><td>%s</td></tr>' % (
            _('instance home'), self._cw.vreg.config.apphome))
        w(u'</table>')
        vcconf = req.vreg.config.vc_config()
        w(u'<h3>%s</h3>' % _('versions configuration'))
        w(u'<table>')
        w(u'<tr><th align="left">%s</th><td>%s</td></tr>' % (
            'CubicWeb', vcconf.get('cubicweb', _('no version information'))))
        for cube in sorted(self._cw.vreg.config.cubes()):
            cubeversion = vcconf.get(cube, _('no version information'))
            w(u'<tr><th align="left">%s</th><td>%s</td></tr>' % (
                cube, cubeversion))
        w(u'</table>')
        # repository information
        repo = req.vreg.config.repository(None)
        w(u'<h2>%s</h2>' % _('Repository'))
        w(u'<h3>%s</h3>' % _('resources usage'))
        w(u'<table>')
        stats = self._cw.call_service('repo_stats')
        for element in sorted(stats):
            w(u'<tr><th align="left">%s</th><td>%s %s</td></tr>'
                   % (element, xml_escape(unicode(stats[element])),
                      element.endswith('percent') and '%' or '' ))
        w(u'</table>')
        if req.cnx.is_repo_in_memory and req.user.is_in_group('managers'):
            w(u'<h3>%s</h3>' % _('opened sessions'))
            sessions = repo._sessions.values()
            if sessions:
                w(u'<ul>')
                for session in sessions:
                    w(u'<li>%s (%s: %s)<br/>' % (
                        xml_escape(unicode(session)),
                        _('last usage'),
                        strftime(dtformat, localtime(session.timestamp))))
                    dict_to_html(w, session.data)
                    w(u'</li>')
                w(u'</ul>')
            else:
                w(u'<p>%s</p>' % _('no repository sessions found'))
        # web server information
        w(u'<h2>%s</h2>' % _('Web server'))
        w(u'<table>')
        w(u'<tr><th align="left">%s</th><td>%s</td></tr>' % (
            _('base url'), req.base_url()))
        w(u'<tr><th align="left">%s</th><td>%s</td></tr>' % (
            _('data directory url'), req.datadir_url))
        w(u'</table>')
        from cubicweb.web.application import SESSION_MANAGER
        if SESSION_MANAGER is not None and req.user.is_in_group('managers'):
            sessions = SESSION_MANAGER.current_sessions()
            w(u'<h3>%s</h3>' % _('opened web sessions'))
            if sessions:
                w(u'<ul>')
                for session in sessions:
                    last_usage_time = session.mtime
                    w(u'<li>%s (%s: %s)<br/>' % (
                        session.sessionid,
                        _('last usage'),
                        strftime(dtformat, localtime(last_usage_time))))
                    dict_to_html(w, session.data)
                    w(u'</li>')
                w(u'</ul>')
            else:
                w(u'<p>%s</p>' % _('no web sessions found'))



class RegistryView(StartupView):
    """display vregistry content"""
    __regid__ = 'registry'
    __select__ = StartupView.__select__ & match_user_groups('managers')
    title = _('registry')
    cache_max_age = 0

    def call(self, **kwargs):
        self.w(u'<h2>%s</h2>' % self._cw._("Registry's content"))
        keys = sorted(self._cw.vreg)
        url = xml_escape(self._cw.url())
        self.w(u'<p>%s</p>\n' % ' - '.join('<a href="%s#%s">%s</a>'
                                           % (url, key, key) for key in keys))
        for key in keys:
            if key in ('boxes', 'contentnavigation'): # those are bw compat registries
                continue
            self.w(u'<h3 id="%s">%s</h3>' % (key, key))
            if self._cw.vreg[key]:
                values = sorted(self._cw.vreg[key].iteritems())
                self.wview('pyvaltable', pyvalue=[(key, xml_escape(repr(val)))
                                                  for key, val in values])
            else:
                self.w(u'<p>Empty</p>\n')


class GCView(StartupView):
    """display garbage collector information"""
    __regid__ = 'gc'
    __select__ = StartupView.__select__ & match_user_groups('managers')
    title = _('memory leak debugging')
    cache_max_age = 0

    def call(self, **kwargs):
        from cubicweb._gcdebug import gc_info
        from rql.stmts import Union
        from cubicweb.appobject import AppObject
        from cubicweb.rset import ResultSet
        from cubicweb.dbapi import Connection, Cursor
        from cubicweb.web.request import CubicWebRequestBase
        lookupclasses = (AppObject,
                         Union, ResultSet,
                         Connection, Cursor,
                         CubicWebRequestBase)
        try:
            from cubicweb.server.session import Session, InternalSession
            lookupclasses += (InternalSession, Session)
        except ImportError:
            pass # no server part installed
        self.w(u'<h2>%s</h2>' % _('Garbage collection information'))
        counters, ocounters, garbage = gc_info(lookupclasses,
                                               viewreferrersclasses=())
        self.w(u'<h3>%s</h3>' % self._cw._('Looked up classes'))
        values = sorted(counters.iteritems(), key=lambda x: x[1], reverse=True)
        self.wview('pyvaltable', pyvalue=values)
        self.w(u'<h3>%s</h3>' % self._cw._('Most referenced classes'))
        values = sorted(ocounters.iteritems(), key=lambda x: x[1], reverse=True)
        self.wview('pyvaltable', pyvalue=values[:self._cw.form.get('nb', 20)])
        if garbage:
            self.w(u'<h3>%s</h3>' % self._cw._('Unreachable objects'))
            values = sorted(xml_escape(repr(o)) for o in garbage)
            self.wview('pyvallist', pyvalue=values)
