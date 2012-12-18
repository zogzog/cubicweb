# copyright 2003-2013 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""cubicweb ldap feed source"""

from cubicweb.cwconfig import merge_options
from cubicweb.server.sources import datafeed
from cubicweb.server import ldaputils


class LDAPFeedSource(ldaputils.LDAPSourceMixIn,
                     datafeed.DataFeedSource):
    """LDAP feed source: unlike ldapuser source, this source is copy based and
    will import ldap content (beside passwords for authentication) into the
    system source.
    """
    support_entities = {'CWUser': False}
    use_cwuri_as_url = False

    options = merge_options(datafeed.DataFeedSource.options
                            + ldaputils.LDAPSourceMixIn.options,
                            optgroup='ldap-source')

