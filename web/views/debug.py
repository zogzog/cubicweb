"""management and error screens


:organization: Logilab
:copyright: 2001-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

from time import strftime, localtime

from logilab.mtconverter import xml_escape

from cubicweb.selectors import none_rset, match_user_groups
from cubicweb.view import StartupView

def dict_to_html(w, dict):
    # XHTML doesn't allow emtpy <ul> nodes
    if dict:
        w(u'<ul>')
        for key in sorted(dict):
            w(u'<li><span class="label">%s</span>: <span>%s</span></li>' % (
                xml_escape(str(key)), xml_escape(repr(dict[key]))))
        w(u'</ul>')



class ProcessInformationView(StartupView):
    __regid__ = 'info'
    __select__ = none_rset() & match_user_groups('managers')

    title = _('server information')

    def call(self, **kwargs):
        """display server information"""
        req = self._cw
        dtformat = req.property_value('ui.datetime-format')
        _ = req._
        w = self.w
        # generic instance information
        w(u'<h1>%s</h1>' % _('Instance'))
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
        w(u'<h1>%s</h1>' % _('Repository'))
        w(u'<h3>%s</h3>' % _('resources usage'))
        w(u'<table>')
        stats = repo.stats()
        for element in sorted(stats):
            w(u'<tr><th align="left">%s</th><td>%s %s</td></tr>'
                   % (element, xml_escape(unicode(stats[element])),
                      element.endswith('percent') and '%' or '' ))
        w(u'</table>')
        if req.cnx._cnxtype == 'inmemory':
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
        w(u'<h1>%s</h1>' % _('Web server'))
        w(u'<table>')
        w(u'<tr><th align="left">%s</th><td>%s</td></tr>' % (
            _('base url'), req.base_url()))
        w(u'<tr><th align="left">%s</th><td>%s</td></tr>' % (
            _('data directory url'), req.datadir_url))
        w(u'</table>')
        from cubicweb.web.application import SESSION_MANAGER
        sessions = SESSION_MANAGER.current_sessions()
        w(u'<h3>%s</h3>' % _('opened web sessions'))
        if sessions:
            w(u'<ul>')
            for session in sessions:
                w(u'<li>%s (%s: %s)<br/>' % (
                    session.sessionid,
                    _('last usage'),
                    strftime(dtformat, localtime(session.last_usage_time))))
                dict_to_html(w, session.data)
                w(u'</li>')
            w(u'</ul>')
        else:
            w(u'<p>%s</p>' % _('no web sessions found'))



class RegistryView(StartupView):
    __regid__ = 'registry'
    __select__ = StartupView.__select__ & match_user_groups('managers')
    title = _('registry')

    def call(self, **kwargs):
        """The default view representing the instance's management"""
        self.w(u'<h1>%s</h1>' % _("Registry's content"))
        keys = sorted(self._cw.vreg)
        self.w(u'<p>%s</p>\n' % ' - '.join('<a href="/_registry#%s">%s</a>'
                                           % (key, key) for key in keys))
        for key in keys:
            self.w(u'<h2><a name="%s">%s</a></h2>' % (key, key))
            items = self._cw.vreg[key].items()
            if items:
                self.w(u'<table><tbody>')
                for key, value in sorted(items):
                    self.w(u'<tr><td>%s</td><td>%s</td></tr>'
                           % (key, xml_escape(repr(value))))
                self.w(u'</tbody></table>\n')
            else:
                self.w(u'<p>Empty</p>\n')
