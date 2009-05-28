"""

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""


rql('SET X value "navtop" WHERE X pkey ~= "contentnavigation.%.context", X value "header"')
rql('SET X value "navcontenttop" WHERE X pkey ~= "contentnavigation%.context", X value "incontext"')
rql('SET X value "navcontentbottom" WHERE X pkey ~= "contentnavigation%.context", X value "footer"')
checkpoint()

if 'require_permission' in schema:
    synchronize_rschema('require_permission')
