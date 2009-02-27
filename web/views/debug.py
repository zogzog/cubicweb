"""management and error screens


:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

from time import strftime, localtime

from logilab.mtconverter import html_escape

from cubicweb.selectors import none_rset, match_user_groups
from cubicweb.view import StartupView

def dict_to_html(w, dict):
    # XHTML doesn't allow emtpy <ul> nodes
    if dict:
        w(u'<ul>')
        for key in sorted(dict):
            w(u'<li><span class="label">%s</span>: <span>%s</span></li>' % (
                html_escape(str(key)), html_escape(repr(dict[key]))))
        w(u'</ul>')

    
class DebugView(StartupView):
    id = 'debug'
    __select__ = none_rset() & match_user_groups('managers')
    title = _('server debug information')

    def call(self, **kwargs):
        """display server information"""
        w = self.w
        w(u'<h1>server sessions</h1>')
        sessions = self.req.cnx._repo._sessions.items()
        if sessions:
            w(u'<ul>')
            for sid, session in sessions:
                w(u'<li>%s  (last usage: %s)<br/>' % (html_escape(str(session)),
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
