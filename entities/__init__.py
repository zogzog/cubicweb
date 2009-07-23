"""base application's entities class implementation: `AnyEntity`

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

from warnings import warn

from logilab.common.deprecation import deprecated_function, obsolete
from logilab.common.decorators import cached

from cubicweb import Unauthorized, typed_eid
from cubicweb.entity import Entity
from cubicweb.utils import dump_class

from cubicweb.interfaces import IBreadCrumbs, IFeed


class AnyEntity(Entity):
    """an entity instance has e_schema automagically set on the class and
    instances have access to their issuing cursor
    """
    id = 'Any'
    __implements__ = (IBreadCrumbs, IFeed)

    @classmethod
    def selected(cls, etype):
        """the special Any entity is used as the default factory, so
        the actual class has to be constructed at selection time once we
        have an actual entity'type
        """
        if cls.id == etype:
            return cls
        usercls = dump_class(cls, etype)
        usercls.id = etype
        usercls.__initialize__()
        return usercls

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
        if self.e_schema.has_subject_relation('description'):
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
        return self.format_date(self.modification_date, date_format=date_format)

    def dc_type(self, form=''):
        """return the display name for the type of this entity (translated)"""
        return self.e_schema.display_name(self.req, form)

    def dc_language(self):
        """return language used by this entity (translated)"""
        # check if entities has internationalizable attributes
        # XXX one is enough or check if all String attributes are internationalizable?
        for rschema, attrschema in self.e_schema.attribute_definitions():
            if rschema.rproperty(self.e_schema, attrschema,
                                 'internationalizable'):
                return self.req._(self.req.user.property_value('ui.language'))
        return self.req._(self.vreg.property_value('ui.language'))

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
                if 'vtitle' in self.req.form:
                    # embeding for instance
                    path.append( self.req.form['vtitle'] )
            elif view.id != 'primary' and hasattr(view, 'title'):
                path.append( self.req._(view.title) )
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

    def linked_to(self, rtype, target, remove=True):
        """if entity should be linked to another using __linkto form param for
        the given relation/target, return eids of related entities

        This method is consuming matching link-to information from form params
        if `remove` is True (by default).
        """
        try:
            return self.__linkto[(rtype, target)]
        except AttributeError:
            self.__linkto = {}
        except KeyError:
            pass
        linktos = list(self.req.list_form_param('__linkto'))
        linkedto = []
        for linkto in linktos[:]:
            ltrtype, eid, lttarget = linkto.split(':')
            if rtype == ltrtype and target == lttarget:
                # delete __linkto from form param to avoid it being added as
                # hidden input
                if remove:
                    linktos.remove(linkto)
                    self.req.form['__linkto'] = linktos
                linkedto.append(typed_eid(eid))
        self.__linkto[(rtype, target)] = linkedto
        return linkedto

    # edit controller callbacks ###############################################

    def after_deletion_path(self):
        """return (path, parameters) which should be used as redirect
        information when this entity is being deleted
        """
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

    # XXX deprecates, may be killed once old widgets system is gone ###########

    @classmethod
    def get_widget(cls, rschema, x='subject'):
        """return a widget to view or edit a relation

        notice that when the relation support multiple target types, the widget
        is necessarily the same for all those types
        """
        # let ImportError propage if web par isn't available
        from cubicweb.web.widgets import widget
        if isinstance(rschema, basestring):
            rschema = cls.schema.rschema(rschema)
        if x == 'subject':
            tschema = rschema.objects(cls.e_schema)[0]
            wdg = widget(cls.vreg, cls, rschema, tschema, 'subject')
        else:
            tschema = rschema.subjects(cls.e_schema)[0]
            wdg = widget(cls.vreg, tschema, rschema, cls, 'object')
        return wdg

    @obsolete('use EntityFieldsForm.subject_relation_vocabulary')
    def subject_relation_vocabulary(self, rtype, limit):
        form = self.vreg.select('forms', 'edition', self.req, entity=self)
        return form.subject_relation_vocabulary(rtype, limit)

    @obsolete('use EntityFieldsForm.object_relation_vocabulary')
    def object_relation_vocabulary(self, rtype, limit):
        form = self.vreg.select('forms', 'edition', self.req, entity=self)
        return form.object_relation_vocabulary(rtype, limit)

    @obsolete('use AutomaticEntityForm.[e]relations_by_category')
    def relations_by_category(self, categories=None, permission=None):
        from cubicweb.web.views.autoform import AutomaticEntityForm
        return AutomaticEntityForm.erelations_by_category(self, categories, permission)

    @obsolete('use AutomaticEntityForm.[e]srelations_by_category')
    def srelations_by_category(self, categories=None, permission=None):
        from cubicweb.web.views.autoform import AutomaticEntityForm
        return AutomaticEntityForm.esrelations_by_category(self, categories, permission)

    def attribute_values(self, attrname):
        if self.has_eid() or attrname in self:
            try:
                values = self[attrname]
            except KeyError:
                values = getattr(self, attrname)
            # actual relation return a list of entities
            if isinstance(values, list):
                return [v.eid for v in values]
            return (values,)
        # the entity is being created, try to find default value for
        # this attribute
        try:
            values = self.req.form[attrname]
        except KeyError:
            try:
                values = self[attrname] # copying
            except KeyError:
                values = getattr(self, 'default_%s' % attrname,
                                 self.e_schema.default(attrname))
                if callable(values):
                    values = values()
        if values is None:
            values = ()
        elif not isinstance(values, (list, tuple)):
            values = (values,)
        return values

    def use_fckeditor(self, attr):
        """return True if fckeditor should be used to edit entity's attribute named
        `attr`, according to user preferences
        """
        if self.req.use_fckeditor() and self.e_schema.has_metadata(attr, 'format'):
            if self.has_eid() or '%s_format' % attr in self:
                return self.attr_metadata(attr, 'format') == 'text/html'
            return self.req.property_value('ui.default-text-format') == 'text/html'
        return False

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
