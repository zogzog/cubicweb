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
"""entity classes for optional library entities"""


from warnings import warn
from datetime import datetime
from urllib.parse import urlsplit, urlunsplit

from logilab.mtconverter import xml_escape

from cubicweb import UnknownProperty
from cubicweb.entity import _marker
from cubicweb.entities import AnyEntity, fetch_config

def mangle_email(address):
    try:
        name, host = address.split('@', 1)
    except ValueError:
        return address
    return '%s at %s' % (name, host.replace('.', ' dot '))


class EmailAddress(AnyEntity):
    __regid__ = 'EmailAddress'
    fetch_attrs, cw_fetch_order = fetch_config(['address', 'alias'])
    rest_attr = 'eid'

    def dc_title(self):
        if self.alias:
            return '%s <%s>' % (self.alias, self.display_address())
        return self.display_address()

    @property
    def email_of(self):
        return self.reverse_use_email and self.reverse_use_email[0] or None

    @property
    def prefered(self):
        return self.prefered_form and self.prefered_form[0] or self

    def related_emails(self, skipeids=None):
        # XXX move to eemail
        # check email relations are in the schema first
        subjrels = self.e_schema.object_relations()
        if not ('sender' in subjrels and 'recipients' in subjrels):
            return
        rset = self._cw.execute('DISTINCT Any X, S, D ORDERBY D DESC '
                                'WHERE X sender Y or X recipients Y, '
                                'X subject S, X date D, Y eid %(y)s',
                                {'y': self.eid})
        if skipeids is None:
            skipeids = set()
        for i in range(len(rset)):
            eid = rset[i][0]
            if eid in skipeids:
                continue
            skipeids.add(eid)
            yield rset.get_entity(i, 0)

    def display_address(self):
        if self._cw.vreg.config['mangle-emails']:
            return mangle_email(self.address)
        return self.address

    def printable_value(self, attr, value=_marker, attrtype=None,
                        format='text/html'):
        """overriden to return displayable address when necessary"""
        if attr == 'address':
            address = self.display_address()
            if format == 'text/html':
                address = xml_escape(address)
            return address
        return super(EmailAddress, self).printable_value(attr, value, attrtype, format)


class Bookmark(AnyEntity):
    """customized class for Bookmark entities"""
    __regid__ = 'Bookmark'
    fetch_attrs, cw_fetch_order = fetch_config(['title', 'path'])

    def actual_url(self):
        url = self._cw.build_url(self.path)
        if self.title:
            urlparts = list(urlsplit(url))
            if urlparts[3]:
                urlparts[3] += '&vtitle=%s' % self._cw.url_quote(self.title)
            else:
                urlparts[3] = 'vtitle=%s' % self._cw.url_quote(self.title)
            url = urlunsplit(urlparts)
        return url

    def action_url(self):
        return self.absolute_url() + '/follow'


class CWProperty(AnyEntity):
    __regid__ = 'CWProperty'

    fetch_attrs, cw_fetch_order = fetch_config(['pkey', 'value'])
    rest_attr = 'pkey'

    def typed_value(self):
        return self._cw.vreg.typed_value(self.pkey, self.value)

    def dc_description(self, format='text/plain'):
        try:
            return self._cw._(self._cw.vreg.property_info(self.pkey)['help'])
        except UnknownProperty:
            return u''
