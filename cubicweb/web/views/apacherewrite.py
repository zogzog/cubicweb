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
"""provide class to do Apache rewrite rules'job inside cubicweb (though functionnalities
are much more limited for the moment)

"""

__docformat__ = "restructuredtext en"

from re import compile

from cubicweb.web import Redirect
from cubicweb.web.component import Component

class RewriteCond(object):
    def __init__(self, condition, match='host', rules=(), action='rewrite'):
        self.condition = compile(condition)
        assert match in ('host', 'path'), match
        self.match_part = match
        self.rules = []
        for rule, replace in rules:
            rulergx = compile(rule)
            self.rules.append( (rulergx, replace) )
        assert action in ('rewrite', 'redirect', 'stop'), action
        self.process = getattr(self, 'action_%s' % action)

    def match(self, **kwargs):
        self._match = self.condition.match(kwargs[self.match_part])
        return not self._match is None

    def action_rewrite(self, path):
        for rgx, replace in self.rules:
            if not rgx.match(path) is None:
                matchdict = self._match.groupdict() or None
                if not matchdict is None:
                    replace = replace % matchdict
                return rgx.sub(replace, path)
        return path

    def action_redirect(self, path):
        url = self.action_rewrite(path)
        raise Redirect(url)

    def action_stop(self, path):
        return path


class ApacheURLRewrite(Component):
    """inherit from this class with actual rules to activate apache style rewriting

    rules should have the form :

    [('condition pattern 1', [('rule1 pattern', 'replace expression'),
                              ('rule2 pattern', 'replace expression')],
     ('condition pattern 2', [('rule1 pattern', 'replace expression'),
                              ('rule2 pattern', 'replace expression')]
    ]

    for instance the equivalent of the following apache rules:

        RewriteCond %{HTTP_HOST} ^logilab\.fr
        RewriteRule ^/(.*) http://www.logilab.fr/$1 [L,R=301]

        RewriteCond %{HTTP_HOST} ^www\.logilab\.fr
        RewriteRule ^/(.*) http://localhost:8080/$1 [L,P]

        RewriteCond %{HTTP_HOST} ^(.+)\.logilab\.fr
        RewriteRule ^/(data/.*) http://localhost:8080/$1 [L,P]
        RewriteRule ^/(json.*) http://localhost:8080/$1 [L,P]
        RewriteRule ^/(.*) http://localhost:8080/m_%1/$1 [L,P]

    could be written (considering that no "host rewritting" is necessary):

      class MyAppRules(ApacheURLRewrite):
        rules = [
          RewriteCond('logilab\.fr', match='host',
                      rules=[('/(.*)', r'http://www.logilab.fr/\1')],
                      action='redirect'),
          RewriteCond('(www)\.logilab\.fr', match='host', action='stop'),
          RewriteCond('/(data|json)/', match='path', action='stop'),
          RewriteCond('(?P<cat>.*)\.logilab\.fr', match='host',
                      rules=[('/(.*)', r'/m_%(cat)s/\1')]),
        ]
    """
    __abstract__ = True
    __regid__ = 'urlrewriter'
    rules = []

    def get_rules(self, req):
        return self.rules

    def rewrite(self, host, path, req):
        for cond in self.get_rules(req):
            if cond.match(host=host, path=path):
                return cond.process(path)
        return path
