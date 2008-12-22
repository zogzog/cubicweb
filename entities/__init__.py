"""base application's entities class implementation: `AnyEntity`

:organization: Logilab
:copyright: 2001-2008 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

from warnings import warn

from logilab.common.deprecation import deprecated_function
from logilab.common.decorators import cached

from cubicweb import Unauthorized, typed_eid
from cubicweb.common.utils import dump_class
from cubicweb.common.entity import Entity
from cubicweb.schema import FormatConstraint

from cubicweb.interfaces import IBreadCrumbs, IFeed


class AnyEntity(Entity):
    """an entity instance has e_schema automagically set on the class and
    instances have access to their issuing cursor
    """
    id = 'Any'   
    __rtags__ = {
        'is' : ('generated', 'link'),
        'is_instance_of' : ('generated', 'link'),
        'identity' : ('generated', 'link'),
        
        # use primary and not generated for eid since it has to be an hidden
        # field in edition
        ('eid',                '*', 'subject'): 'primary',
        ('creation_date',      '*', 'subject'): 'generated',
        ('modification_date',  '*', 'subject'): 'generated',
        ('has_text',           '*', 'subject'): 'generated',
        
        ('require_permission', '*', 'subject') : ('generated', 'link'),
        ('owned_by',           '*', 'subject') : ('generated', 'link'),
        ('created_by',         '*', 'subject') : ('generated', 'link'),
        
        ('wf_info_for',        '*', 'subject') : ('generated', 'link'),
        ('wf_info_for',        '*', 'object')  : ('generated', 'link'),
                 
        ('description',        '*', 'subject'): 'secondary',

        # XXX should be moved in their respective cubes
        ('filed_under',        '*', 'subject') : ('generic', 'link'),
        ('filed_under',        '*', 'object')  : ('generic', 'create'),
        # generated since there is a componant to handle comments
        ('comments',           '*', 'subject') : ('generated', 'link'),
        ('comments',           '*', 'object')  : ('generated', 'link'),
        }

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

    @classmethod
    def __initialize__(cls): 
        super(ANYENTITY, cls).__initialize__() # XXX
        eschema = cls.e_schema
        eschema.format_fields = {}
        # set a default_ATTR method for rich text format fields
        for attr, formatattr in eschema.rich_text_fields():
            if not hasattr(cls, 'default_%s' % formatattr):
                setattr(cls, 'default_%s' % formatattr, cls._default_format)
            eschema.format_fields[formatattr] = attr
            
    def _default_format(self):
        return self.req.property_value('ui.default-text-format')

    def use_fckeditor(self, attr):
        """return True if fckeditor should be used to edit entity's attribute named
        `attr`, according to user preferences
        """
        req = self.req
        if req.property_value('ui.fckeditor') and self.has_format(attr):
            if self.has_eid() or '%s_format' % attr in self:
                return self.format(attr) == 'text/html'
            return req.property_value('ui.default-text-format') == 'text/html'
        return False
    
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
    display_name = deprecated_function(dc_type) # require agueol > 0.8.1, asteretud > 0.10.0 for removal

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
        """return the EUser entity which has created this entity, or None if
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

    def after_deletion_path(self):
        """return (path, parameters) which should be used as redirect
        information when this entity is being deleted
        """
        return str(self.e_schema).lower(), {}

    def add_related_schemas(self):
        """this is actually used ui method to generate 'addrelated' actions from
        the schema.

        If you're using explicit 'addrelated' actions for an entity types, you
        should probably overrides this method to return an empty list else you
        may get some unexpected actions.
        """
        req = self.req
        eschema = self.e_schema
        for role, rschemas in (('subject', eschema.subject_relations()),
                               ('object', eschema.object_relations())):
            for rschema in rschemas:
                if rschema.is_final():
                    continue
                # check the relation can be added as well
                if role == 'subject'and not rschema.has_perm(req, 'add', fromeid=self.eid):
                    continue
                if role == 'object'and not rschema.has_perm(req, 'add', toeid=self.eid):
                    continue
                # check the target types can be added as well
                for teschema in rschema.targets(eschema, role):
                    if not self.relation_mode(rschema, teschema, role) == 'create':
                        continue
                    if teschema.has_local_role('add') or teschema.has_perm(req, 'add'):
                        yield rschema, teschema, role

    def relation_mode(self, rtype, targettype, role='subject'):
        """return a string telling if the given relation is usually created
        to a new entity ('create' mode) or to an existant entity ('link' mode)
        """
        return self.rtags.get_mode(rtype, targettype, role)

    # edition helper functions ################################################
    
    def relations_by_category(self, categories=None, permission=None):
        if categories is not None:
            if not isinstance(categories, (list, tuple, set, frozenset)):
                categories = (categories,)
            if not isinstance(categories, (set, frozenset)):
                categories = frozenset(categories)
        eschema, rtags  = self.e_schema, self.rtags
        if self.has_eid():
            eid = self.eid
        else:
            eid = None
        for rschema, targetschemas, role in eschema.relation_definitions(True):
            if rschema in ('identity', 'has_text'):
                continue
            # check category first, potentially lower cost than checking
            # permission which may imply rql queries
            if categories is not None:
                targetschemas = [tschema for tschema in targetschemas
                                 if rtags.get_tags(rschema.type, tschema.type, role).intersection(categories)]
                if not targetschemas:
                    continue
            tags = rtags.get_tags(rschema.type, role=role)
            if permission is not None:
                # tag allowing to hijack the permission machinery when
                # permission is not verifiable until the entity is actually
                # created...
                if eid is None and ('%s_on_new' % permission) in tags:
                    yield (rschema, targetschemas, role)
                    continue
                if rschema.is_final():
                    if not rschema.has_perm(self.req, permission, eid):
                        continue
                elif role == 'subject':
                    if not ((eid is None and rschema.has_local_role(permission)) or
                            rschema.has_perm(self.req, permission, fromeid=eid)):
                        continue
                    # on relation with cardinality 1 or ?, we need delete perm as well
                    # if the relation is already set
                    if (permission == 'add'
                        and rschema.cardinality(eschema, targetschemas[0], role) in '1?'
                        and self.has_eid() and self.related(rschema.type, role)
                        and not rschema.has_perm(self.req, 'delete', fromeid=eid,
                                                 toeid=self.related(rschema.type, role)[0][0])):
                        continue
                elif role == 'object':
                    if not ((eid is None and rschema.has_local_role(permission)) or
                            rschema.has_perm(self.req, permission, toeid=eid)):
                        continue
                    # on relation with cardinality 1 or ?, we need delete perm as well
                    # if the relation is already set
                    if (permission == 'add'
                        and rschema.cardinality(targetschemas[0], eschema, role) in '1?'
                        and self.has_eid() and self.related(rschema.type, role)
                        and not rschema.has_perm(self.req, 'delete', toeid=eid,
                                                 fromeid=self.related(rschema.type, role)[0][0])):
                        continue
            yield (rschema, targetschemas, role)

    def srelations_by_category(self, categories=None, permission=None):
        result = []
        for rschema, ttypes, target in self.relations_by_category(categories,
                                                                  permission):
            if rschema.is_final():
                continue
            result.append( (rschema.display_name(self.req, target), rschema, target) )
        return sorted(result)
                
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
