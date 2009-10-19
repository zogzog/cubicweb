"""base application's entities class implementation: `AnyEntity`

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

from warnings import warn

from logilab.common.deprecation import deprecated
from logilab.common.decorators import cached

from cubicweb import Unauthorized, typed_eid
from cubicweb.entity import Entity

from cubicweb.interfaces import IBreadCrumbs, IFeed


class AnyEntity(Entity):
    """an entity instance has e_schema automagically set on the class and
    instances have access to their issuing cursor
    """
    __regid__ = 'Any'
    __implements__ = (IBreadCrumbs, IFeed)

    fetch_attrs = ('modification_date',)
    @classmethod
    def fetch_order(cls, attr, var):
        """class method used to control sort order when multiple entities of
        this type are fetched
        """
        return cls.fetch_unrelated_order(attr, var)

    @classmethod
    def fetch_unrelated_order(cls, attr, var):
        """class method used to control sort order when multiple entities of
        this type are fetched to use in edition (eg propose them to create a
        new relation on an edited entity).
        """
        if attr == 'modification_date':
            return '%s DESC' % var
        return None

    # meta data api ###########################################################

    def dc_title(self):
        """return a suitable *unicode* title for this entity"""
        for rschema, attrschema in self.e_schema.attribute_definitions():
            if rschema.meta:
                continue
            value = self.get_value(rschema.type)
            if value:
                # make the value printable (dates, floats, bytes, etc.)
                return self.printable_value(rschema.type, value, attrschema.type,
                                            format='text/plain')
        return u'%s #%s' % (self.dc_type(), self.eid)

    def dc_long_title(self):
        """return a more detailled title for this entity"""
        return self.dc_title()

    def dc_description(self, format='text/plain'):
        """return a suitable description for this entity"""
        if 'description' in self.e_schema.subjrels:
            return self.printable_value('description', format=format)
        return u''

    def dc_authors(self):
        """return a suitable description for the author(s) of the entity"""
        try:
            return ', '.join(u.name() for u in self.owned_by)
        except Unauthorized:
            return u''

    def dc_creator(self):
        """return a suitable description for the creator of the entity"""
        if self.creator:
            return self.creator.name()
        return u''

    def dc_date(self, date_format=None):# XXX default to ISO 8601 ?
        """return latest modification date of this entity"""
        return self._cw.format_date(self.modification_date, date_format=date_format)

    def dc_type(self, form=''):
        """return the display name for the type of this entity (translated)"""
        return self.e_schema.display_name(self._cw, form)

    def dc_language(self):
        """return language used by this entity (translated)"""
        # check if entities has internationalizable attributes
        # XXX one is enough or check if all String attributes are internationalizable?
        for rschema, attrschema in self.e_schema.attribute_definitions():
            if rschema.rproperty(self.e_schema, attrschema,
                                 'internationalizable'):
                return self._cw._(self._cw.user.property_value('ui.language'))
        return self._cw._(self._cw.vreg.property_value('ui.language'))

    @property
    def creator(self):
        """return the CWUser entity which has created this entity, or None if
        unknown or if the curent user doesn't has access to this euser
        """
        try:
            return self.created_by[0]
        except (Unauthorized, IndexError):
            return None

    def breadcrumbs(self, view=None, recurs=False):
        path = [self]
        if hasattr(self, 'parent'):
            parent = self.parent()
            if parent is not None:
                try:
                    path = parent.breadcrumbs(view, True) + [self]
                except TypeError:
                    warn("breadcrumbs method's now takes two arguments "
                         "(view=None, recurs=False), please update",
                         DeprecationWarning)
                    path = parent.breadcrumbs(view) + [self]
        if not recurs:
            if view is None:
                if 'vtitle' in self._cw.form:
                    # embeding for instance
                    path.append( self._cw.form['vtitle'] )
            elif view.__regid__ != 'primary' and hasattr(view, 'title'):
                path.append( self._cw._(view.title) )
        return path

    ## IFeed interface ########################################################

    def rss_feed_url(self):
        return self.absolute_url(vid='rss')

    # abstractions making the whole things (well, some at least) working ######

    def sortvalue(self, rtype=None):
        """return a value which can be used to sort this entity or given
        entity's attribute
        """
        if rtype is None:
            return self.dc_title().lower()
        value = self.get_value(rtype)
        # do not restrict to `unicode` because Bytes will return a `str` value
        if isinstance(value, basestring):
            return self.printable_value(rtype, format='text/plain').lower()
        return value

    # edition helper functions ################################################

    def linked_to(self, rtype, role, remove=True):
        """if entity should be linked to another using __linkto form param for
        the given relation/role, return eids of related entities

        This method is consuming matching link-to information from form params
        if `remove` is True (by default).
        """
        try:
            return self.__linkto[(rtype, role)]
        except AttributeError:
            self.__linkto = {}
        except KeyError:
            pass
        linktos = list(self._cw.list_form_param('__linkto'))
        linkedto = []
        for linkto in linktos[:]:
            ltrtype, eid, ltrole = linkto.split(':')
            if rtype == ltrtype and role == ltrole:
                # delete __linkto from form param to avoid it being added as
                # hidden input
                if remove:
                    linktos.remove(linkto)
                    self._cw.form['__linkto'] = linktos
                linkedto.append(typed_eid(eid))
        self.__linkto[(rtype, role)] = linkedto
        return linkedto

    # edit controller callbacks ###############################################

    def after_deletion_path(self):
        """return (path, parameters) which should be used as redirect
        information when this entity is being deleted
        """
        if hasattr(self, 'parent') and self.parent():
            return self.parent().rest_path(), {}
        return str(self.e_schema).lower(), {}

    def pre_web_edit(self):
        """callback called by the web editcontroller when an entity will be
        created/modified, to let a chance to do some entity specific stuff.

        Do nothing by default.
        """
        pass

    # server side helpers #####################################################

    def notification_references(self, view):
        """used to control References field of email send on notification
        for this entity. `view` is the notification view.

        Should return a list of eids which can be used to generate message ids
        of previously sent email
        """
        return ()

# XXX:  store a reference to the AnyEntity class since it is hijacked in goa
#       configuration and we need the actual reference to avoid infinite loops
#       in mro
ANYENTITY = AnyEntity

def fetch_config(fetchattrs, mainattr=None, pclass=AnyEntity, order='ASC'):
    if pclass is ANYENTITY:
        pclass = AnyEntity # AnyEntity and ANYENTITY may be different classes
    if pclass is not None:
        fetchattrs += pclass.fetch_attrs
    if mainattr is None:
        mainattr = fetchattrs[0]
    @classmethod
    def fetch_order(cls, attr, var):
        if attr == mainattr:
            return '%s %s' % (var, order)
        return None
    return fetchattrs, fetch_order
