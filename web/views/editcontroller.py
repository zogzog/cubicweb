"""The edit controller, handling form submitting.

:organization: Logilab
:copyright: 2001-2008 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"
from decimal import Decimal

from rql.utils import rqlvar_maker

from cubicweb import Binary, ValidationError, typed_eid
from cubicweb.web import INTERNAL_FIELD_VALUE, RequestError, NothingToEdit
from cubicweb.web.controller import parse_relations_descr
from cubicweb.web.views.basecontrollers import ViewController


class ToDoLater(Exception):
    """exception used in the edit controller to indicate that a relation
    can't be handled right now and have to be handled later
    """

class EditController(ViewController):
    id = 'edit'

    def publish(self, rset=None, fromjson=False):
        """edit / create / copy / delete entity / relations"""
        self.fromjson = fromjson
        for key in self.req.form:
            # There should be 0 or 1 action
            if key.startswith('__action_'):
                cbname = key[1:]
                try:
                    callback = getattr(self, cbname)
                except AttributeError:
                    raise RequestError(self.req._('invalid action %r' % key))
                else:
                    return callback()
        self._default_publish()
        self.reset()

    def _default_publish(self):
        req = self.req
        form = req.form
        # no specific action, generic edition
        self._to_create = req.data['eidmap'] = {}
        self._pending_relations = []
        todelete = self.req.get_pending_deletes()
        toinsert = self.req.get_pending_inserts()
        try:
            methodname = form.pop('__method', None)
            for eid in req.edited_eids():
                formparams = req.extract_entity_params(eid)
                if methodname is not None:
                    entity = req.eid_rset(eid).get_entity(0, 0)
                    method = getattr(entity, methodname)
                    method(formparams)
                eid = self.edit_entity(formparams)
        except (RequestError, NothingToEdit):
            if '__linkto' in form and 'eid' in form:
                self.execute_linkto()
            elif not ('__delete' in form or '__insert' in form or todelete or toinsert):
                raise ValidationError(None, {None: req._('nothing to edit')})
        # handle relations in newly created entities
        if self._pending_relations:
            for rschema, formparams, x, entity in self._pending_relations:
                self.handle_relation(rschema, formparams, x, entity, True)

        # XXX this processes *all* pending operations of *all* entities
        if form.has_key('__delete'):
            todelete += req.list_form_param('__delete', form, pop=True)
        if todelete:
            self.delete_relations(parse_relations_descr(todelete))
        if form.has_key('__insert'):
            toinsert = req.list_form_param('__insert', form, pop=True)
        if toinsert:
            self.insert_relations(parse_relations_descr(toinsert))
        self.req.remove_pending_operations()

    def edit_entity(self, formparams, multiple=False):
        """edit / create / copy an entity and return its eid"""
        etype = formparams['__type']
        entity = self.vreg.etype_class(etype)(self.req, None, None)
        entity.eid = eid = self._get_eid(formparams['eid'])
        edited = self.req.form.get('__maineid') == formparams['eid']
        # let a chance to do some entity specific stuff.
        entity.pre_web_edit()
        # create a rql query from parameters
        self.relations = []
        self.restrictions = []
        # process inlined relations at the same time as attributes
        # this is required by some external source such as the svn source which
        # needs some information provided by those inlined relation. Moreover
        # this will generate less write queries.
        for rschema in entity.e_schema.subject_relations():
            if rschema.is_final():
                self.handle_attribute(entity, rschema, formparams)
            elif rschema.inlined:
                self.handle_inlined_relation(rschema, formparams, entity)
        execute = self.req.execute
        if eid is None: # creation or copy
            if self.relations:
                rql = 'INSERT %s X: %s' % (etype, ','.join(self.relations))
            else:
                rql = 'INSERT %s X' % etype
            if self.restrictions:
                rql += ' WHERE %s' % ','.join(self.restrictions)
            try:
                # get the new entity (in some cases, the type might have
                # changed as for the File --> Image mutation)
                entity = execute(rql, formparams).get_entity(0, 0)
                eid = entity.eid
            except ValidationError, ex:
                # ex.entity may be an int or an entity instance
                self._to_create[formparams['eid']] = ex.entity
                if self.fromjson:
                    ex.entity = formparams['eid']
                raise
            self._to_create[formparams['eid']] = eid
        elif self.relations: # edition of an existant entity
            varmaker = rqlvar_maker()
            var = varmaker.next()
            while var in formparams:
                var = varmaker.next()
            rql = 'SET %s WHERE X eid %%(%s)s' % (','.join(self.relations), var)
            if self.restrictions:
                rql += ', %s' % ','.join(self.restrictions)
            formparams[var] = eid
            execute(rql, formparams)
        for rschema in entity.e_schema.subject_relations():
            if rschema.is_final() or rschema.inlined:
                continue
            self.handle_relation(rschema, formparams, 'subject', entity)
        for rschema in entity.e_schema.object_relations():
            if rschema.is_final():
                continue
            self.handle_relation(rschema, formparams, 'object', entity)
        if edited:
            self.notify_edited(entity)
        if formparams.has_key('__delete'):
            todelete = self.req.list_form_param('__delete', formparams, pop=True)
            self.delete_relations(parse_relations_descr(todelete))
        if formparams.has_key('__cloned_eid'):
            entity.copy_relations(formparams['__cloned_eid'])
        if formparams.has_key('__insert'):
            toinsert = self.req.list_form_param('__insert', formparams, pop=True)
            self.insert_relations(parse_relations_descr(toinsert))
        if edited: # only execute linkto for the main entity
            self.execute_linkto(eid)
        return eid

    def _action_apply(self):
        self._default_publish()
        self.reset()

    def _action_cancel(self):
        errorurl = self.req.form.get('__errorurl')
        if errorurl:
            self.req.cancel_edition(errorurl)
        return self.reset()

    def _action_delete(self):
        self.delete_entities(self.req.edited_eids(withtype=True))
        return self.reset()

    def _needs_edition(self, rtype, formparams, entity):
        """returns True and and the new value if `rtype` was edited"""
        editkey = 'edits-%s' % rtype
        if not editkey in formparams:
            return False, None # not edited
        value = formparams.get(rtype) or None
        if entity.has_eid() and (formparams.get(editkey) or None) == value:
            return False, None # not modified
        if value == INTERNAL_FIELD_VALUE:
            value = None
        return True, value

    def handle_attribute(self, entity, rschema, formparams):
        """append to `relations` part of the rql query to edit the
        attribute described by the given schema if necessary
        """
        attr = rschema.type
        edition_needed, value = self._needs_edition(attr, formparams, entity)
        if not edition_needed:
            return
        # test if entity class defines a special handler for this attribute
        custom_edit = getattr(entity, 'custom_%s_edit' % attr, None)
        if custom_edit:
            custom_edit(formparams, value, self.relations)
            return
        attrtype = rschema.objects(entity.e_schema)[0].type
        # on checkbox or selection, the field may not be in params
        if attrtype == 'Boolean':
            value = bool(value)
        elif attrtype == 'Decimal':
            value = Decimal(value)
        elif attrtype == 'Bytes':
            # if it is a file, transport it using a Binary (StringIO)
            # XXX later __detach is for the new widget system, the former is to
            # be removed once web/widgets.py has been dropped
            if formparams.has_key('__%s_detach' % attr) or formparams.has_key('%s__detach' % attr):
                # drop current file value
                value = None
            # no need to check value when nor explicit detach nor new file
            # submitted, since it will think the attribute is not modified
            elif isinstance(value, unicode):
                # file modified using a text widget
                encoding = entity.attr_metadata(attr, 'encoding')
                value = Binary(value.encode(encoding))
            elif value:
                # value is a  3-uple (filename, mimetype, stream)
                val = Binary(value[2].read())
                if not val.getvalue(): # usually an unexistant file
                    value = None
                else:
                    val.filename = value[0]
                    # ignore browser submitted MIME type since it may be buggy
                    # XXX add a config option to tell if we should consider it
                    # or not?
                    #if entity.e_schema.has_metadata(attr, 'format'):
                    #    key = '%s_format' % attr
                    #    formparams[key] = value[1]
                    #    self.relations.append('X %s_format %%(%s)s'
                    #                          % (attr, key))
                    # XXX suppose a File compatible schema
                    if entity.e_schema.has_subject_relation('name') \
                           and not formparams.get('name'):
                        formparams['name'] = value[0]
                        self.relations.append('X name %(name)s')
                    value = val
        elif value is not None:
            if attrtype in ('Date', 'Datetime', 'Time'):
                try:
                    value = self.parse_datetime(value, attrtype)
                except ValueError:
                    raise ValidationError(entity.eid,
                                          {attr: self.req._("invalid date")})
            elif attrtype == 'Password':
                # check confirmation (see PasswordWidget for confirmation field name)
                confirmval = formparams.get(attr + '-confirm')
                if confirmval != value:
                    raise ValidationError(entity.eid,
                                          {attr: self.req._("password and confirmation don't match")})
                # password should *always* be utf8 encoded
                value = value.encode('UTF8')
            else:
                # strip strings
                value = value.strip()
        elif attrtype == 'Password':
            # skip None password
            return # unset password
        formparams[attr] = value
        self.relations.append('X %s %%(%s)s' % (attr, attr))

    def _relation_values(self, rschema, formparams, x, entity, late=False):
        """handle edition for the (rschema, x) relation of the given entity
        """
        rtype = rschema.type
        editkey = 'edit%s-%s' % (x[0], rtype)
        if not editkey in formparams:
            return # not edited
        try:
            values = self._linked_eids(self.req.list_form_param(rtype, formparams), late)
        except ToDoLater:
            self._pending_relations.append((rschema, formparams, x, entity))
            return
        origvalues = set(typed_eid(eid) for eid in self.req.list_form_param(editkey, formparams))
        return values, origvalues

    def handle_inlined_relation(self, rschema, formparams, entity, late=False):
        """handle edition for the (rschema, x) relation of the given entity
        """
        try:
            values, origvalues = self._relation_values(rschema, formparams,
                                                       'subject', entity, late)
        except TypeError:
            return # not edited / to do later
        if values == origvalues:
            return # not modified
        attr = str(rschema)
        if values:
            formparams[attr] = iter(values).next()
            self.relations.append('X %s %s' % (attr, attr.upper()))
            self.restrictions.append('%s eid %%(%s)s' % (attr.upper(), attr))
        elif entity.has_eid():
            self.handle_relation(rschema, formparams, 'subject', entity, late)

    def handle_relation(self, rschema, formparams, x, entity, late=False):
        """handle edition for the (rschema, x) relation of the given entity
        """
        try:
            values, origvalues = self._relation_values(rschema, formparams, x,
                                                       entity, late)
        except TypeError:
            return # not edited / to do later
        etype = entity.e_schema
        if values == origvalues:
            return # not modified
        if x == 'subject':
            desttype = rschema.objects(etype)[0]
            card = rschema.rproperty(etype, desttype, 'cardinality')[0]
            subjvar, objvar = 'X', 'Y'
        else:
            desttype = rschema.subjects(etype)[0]
            card = rschema.rproperty(desttype, etype, 'cardinality')[1]
            subjvar, objvar = 'Y', 'X'
        eid = entity.eid
        if x == 'object' or not rschema.inlined or not values:
            # this is not an inlined relation or no values specified,
            # explicty remove relations
            rql = 'DELETE %s %s %s WHERE X eid %%(x)s, Y eid %%(y)s' % (
                subjvar, rschema, objvar)
            for reid in origvalues.difference(values):
                self.req.execute(rql, {'x': eid, 'y': reid}, ('x', 'y'))
        seteids = values.difference(origvalues)
        if seteids:
            rql = 'SET %s %s %s WHERE X eid %%(x)s, Y eid %%(y)s' % (
                subjvar, rschema, objvar)
            for reid in seteids:
                self.req.execute(rql, {'x': eid, 'y': reid}, ('x', 'y'))

    def _get_eid(self, eid):
        # should be either an int (existant entity) or a variable (to be
        # created entity)
        assert eid or eid == 0, repr(eid) # 0 is a valid eid
        try:
            return typed_eid(eid)
        except ValueError:
            try:
                return self._to_create[eid]
            except KeyError:
                self._to_create[eid] = None
                return None

    def _linked_eids(self, eids, late=False):
        """return a list of eids if they are all known, else raise ToDoLater
        """
        result = set()
        for eid in eids:
            if not eid: # AutoCompletionWidget
                continue
            eid = self._get_eid(eid)
            if eid is None:
                if not late:
                    raise ToDoLater()
                # eid is still None while it's already a late call
                # this mean that the associated entity has not been created
                raise Exception('duh')
            result.add(eid)
        return result


