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


class DebugView(StartupView):
    __regid__ = 'debug'
    __select__ = none_rset() & match_user_groups('managers')
    title = _('server debug information')

    def call(self, **kwargs):
        """display server information"""
        w = self.w
        w(u'<h1>server sessions</h1>')
        sessions = self._cw.cnx._repo._sessions.items()
        if sessions:
            w(u'<ul>')
            for sid, session in sessions:
                w(u'<li>%s  (last usage: %s)<br/>' % (xml_escape(str(session)),
                                                      strftime('%Y-%m-%d %H:%M:%S',
                                                               localtime(session.timestamp))))
                dict_to_html(w, session.data)
                w(u'</li>')
            w(u'</ul>')
        else:
            w(u'<p>no server sessions found</p>')
        from cubicweb.web.application import SESSION_MANAGER
        w(u'<h1>web sessions</h1>')
        sessions = SESSION_MANAGER.current_sessions()
        if sessions:
            w(u'<ul>')
            for session in sessions:
                w(u'<li>%s (last usage: %s)<br/>' % (session.sessionid,
                                                     strftime('%Y-%m-%d %H:%M:%S',
                                                              localtime(session.last_usage_time))))
                dict_to_html(w, session.data)
                w(u'</li>')
            w(u'</ul>')
        else:
            w(u'<p>no web sessions found</p>')


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
            self.w(u'<h2><a name="%s">%s</a></h2>' % (key,key))
            items = self._cw.vreg[key].items()
            if items:
                self.w(u'<table><tbody>')
                for key, value in sorted(items):
                    self.w(u'<tr><td>%s</td><td>%s</td></tr>'
                           % (key, xml_escape(repr(value))))
                self.w(u'</tbody></table>\n')
            else:
                self.w(u'<p>Empty</p>\n')
