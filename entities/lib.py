"""entity classes for optional library entities

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

from urlparse import urlsplit, urlunsplit
from datetime import datetime

from logilab.common.decorators import cached
from logilab.common.deprecation import deprecated

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
    id = 'EmailAddress'
    fetch_attrs, fetch_order = fetch_config(['address', 'alias'])

    def dc_title(self):
        if self.alias:
            return '%s <%s>' % (self.alias, self.display_address())
        return self.display_address()

    @property
    def email_of(self):
        return self.reverse_use_email and self.reverse_use_email[0]

    @property
    def prefered(self):
        return self.prefered_form and self.prefered_form[0] or None

    @deprecated('use .prefered')
    def canonical_form(self):
        return self.prefered_form and self.prefered_form[0] or self

    def related_emails(self, skipeids=None):
        # XXX move to eemail
        # check email relations are in the schema first
        subjrels = self.e_schema.object_relations()
        if not ('sender' in subjrels and 'recipients' in subjrels):
            return
        rql = 'DISTINCT Any X, S, D ORDERBY D DESC WHERE X sender Y or X recipients Y, X subject S, X date D, Y eid %(y)s'
        rset = self.req.execute(rql, {'y': self.eid}, 'y')
        if skipeids is None:
            skipeids = set()
        for i in xrange(len(rset)):
            eid = rset[i][0]
            if eid in skipeids:
                continue
            skipeids.add(eid)
            yield rset.get_entity(i, 0)

    def display_address(self):
        if self.vreg.config['mangle-emails']:
            return mangle_email(self.address)
        return self.address

    def printable_value(self, attr, value=_marker, attrtype=None,
                        format='text/html'):
        """overriden to return displayable address when necessary"""
        if attr == 'address':
            return self.display_address()
        return super(EmailAddress, self).printable_value(attr, value, attrtype, format)

    def after_deletion_path(self):
        """return (path, parameters) which should be used as redirect
        information when this entity is being deleted
        """
        if self.email_of:
            return self.email_of.rest_path(), {}
        return super(EmailAddress, self).after_deletion_path()


from logilab.common.deprecation import class_renamed
Emailaddress = class_renamed('Emailaddress', EmailAddress)
Emailaddress.id = 'Emailaddress'


class CWProperty(AnyEntity):
    id = 'CWProperty'

    fetch_attrs, fetch_order = fetch_config(['pkey', 'value'])
    rest_attr = 'pkey'

    def typed_value(self):
        return self.vreg.typed_value(self.pkey, self.value)

    def dc_description(self, format='text/plain'):
        try:
            return self.req._(self.vreg.property_info(self.pkey)['help'])
        except UnknownProperty:
            return u''

    def after_deletion_path(self):
        """return (path, parameters) which should be used as redirect
        information when this entity is being deleted
        """
        return 'view', {}


class Bookmark(AnyEntity):
    """customized class for Bookmark entities"""
    id = 'Bookmark'
    fetch_attrs, fetch_order = fetch_config(['title', 'path'])

    def actual_url(self):
        url = self.req.build_url(self.path)
        if self.title:
            urlparts = list(urlsplit(url))
            if urlparts[3]:
                urlparts[3] += '&vtitle=%s' % self.req.url_quote(self.title)
            else:
                urlparts[3] = 'vtitle=%s' % self.req.url_quote(self.title)
            url = urlunsplit(urlparts)
        return url

    def action_url(self):
        return self.absolute_url() + '/follow'


class CWCache(AnyEntity):
    """Cache"""
    id = 'CWCache'
    fetch_attrs, fetch_order = fetch_config(['name'])

    def touch(self):
        self.req.execute('SET X timestamp %(t)s WHERE X eid %(x)s',
                         {'t': datetime.now(), 'x': self.eid}, 'x')

    def valid(self, date):
        if date:
            return date > self.timestamp
        return False

