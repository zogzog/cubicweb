"""abstract form classes for CubicWeb web client

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

from simplejson import dumps

from logilab.mtconverter import html_escape

from cubicweb import typed_eid
from cubicweb.selectors import match_form_params
from cubicweb.view import NOINDEX, NOFOLLOW, View, EntityView, AnyRsetView
from cubicweb.common.registerers import accepts_registerer
from cubicweb.web import stdmsgs
from cubicweb.web.httpcache import NoHTTPCacheManager
from cubicweb.web.controller import redirect_params


def relation_id(eid, rtype, target, reid):
    if target == 'subject':
        return u'%s:%s:%s' % (eid, rtype, reid)
    return u'%s:%s:%s' % (reid, rtype, eid)


class FormMixIn(object):
    """abstract form mix-in"""
    category = 'form'
    controller = 'edit'
    domid = 'entityForm'
    
    http_cache_manager = NoHTTPCacheManager
    add_to_breadcrumbs = False
    skip_relations = set()
    
    def __init__(self, req, rset):
        super(FormMixIn, self).__init__(req, rset)
        self.maxrelitems = self.req.property_value('navigation.related-limit')
        self.maxcomboitems = self.req.property_value('navigation.combobox-limit')
        self.force_display = not not req.form.get('__force_display')
        # get validation session data which may have been previously set.
        # deleting validation errors here breaks form reloading (errors are
        # no more available), they have to be deleted by application's publish
        # method on successful commit
        formurl = req.url()
        forminfo = req.get_session_data(formurl)
        if forminfo:
            req.data['formvalues'] = forminfo['values']
            req.data['formerrors'] = errex = forminfo['errors']
            req.data['displayederrors'] = set()
            # if some validation error occured on entity creation, we have to
            # get the original variable name from its attributed eid
            foreid = errex.entity
            for var, eid in forminfo['eidmap'].items():
                if foreid == eid:
                    errex.eid = var
                    break
            else:
                errex.eid = foreid
        
    def html_headers(self):
        """return a list of html headers (eg something to be inserted between
        <head> and </head> of the returned page

        by default forms are neither indexed nor followed
        """
        return [NOINDEX, NOFOLLOW]
        
    def linkable(self):
        """override since forms are usually linked by an action,
        so we don't want them to be listed by appli.possible_views
        """
        return False

    @property
    def limit(self):
        if self.force_display:
            return None
        return self.maxrelitems + 1

    def need_multipart(self, entity, categories=('primary', 'secondary')):
        """return a boolean indicating if form's enctype should be multipart
        """
        for rschema, _, x in entity.relations_by_category(categories):
            if entity.get_widget(rschema, x).need_multipart:
                return True
        # let's find if any of our inlined entities needs multipart
        for rschema, targettypes, x in entity.relations_by_category('inlineview'):
            assert len(targettypes) == 1, \
                   "I'm not able to deal with several targets and inlineview"
            ttype = targettypes[0]
            inlined_entity = self.vreg.etype_class(ttype)(self.req, None, None)
            for irschema, _, x in inlined_entity.relations_by_category(categories):
                if inlined_entity.get_widget(irschema, x).need_multipart:
                    return True
        return False

    def error_message(self):
        """return formatted error message

        This method should be called once inlined field errors has been consumed
        """
        errex = self.req.data.get('formerrors')
        # get extra errors
        if errex is not None:
            errormsg = self.req._('please correct the following errors:')
            displayed = self.req.data['displayederrors']
            errors = sorted((field, err) for field, err in errex.errors.items()
                            if not field in displayed)
            if errors:
                if len(errors) > 1:
                    templstr = '<li>%s</li>\n' 
                else:
                    templstr = '&nbsp;%s\n'
                for field, err in errors:
                    if field is None:
                        errormsg += templstr % err
                    else:
                        errormsg += templstr % '%s: %s' % (self.req._(field), err)
                if len(errors) > 1:
                    errormsg = '<ul>%s</ul>' % errormsg
            return u'<div class="errorMessage">%s</div>' % errormsg
        return u''
    
    def restore_pending_inserts(self, entity, cell=False):
        """used to restore edition page as it was before clicking on
        'search for <some entity type>'
        
        """
        eid = entity.eid
        cell = cell and "div_insert_" or "tr"
        pending_inserts = set(self.req.get_pending_inserts(eid))
        for pendingid in pending_inserts:
            eidfrom, rtype, eidto = pendingid.split(':')
            if typed_eid(eidfrom) == entity.eid: # subject
                label = display_name(self.req, rtype, 'subject')
                reid = eidto
            else:
                label = display_name(self.req, rtype, 'object')
                reid = eidfrom
            jscall = "javascript: cancelPendingInsert('%s', '%s', null, %s);" \
                     % (pendingid, cell, eid)
            rset = self.req.eid_rset(reid)
            eview = self.view('text', rset, row=0)
            # XXX find a clean way to handle baskets
            if rset.description[0][0] == 'Basket':
                eview = '%s (%s)' % (eview, display_name(self.req, 'Basket'))
            yield rtype, pendingid, jscall, label, reid, eview
        
    
    def force_display_link(self):
        return (u'<span class="invisible">' 
                u'[<a href="javascript: window.location.href+=\'&amp;__force_display=1\'">%s</a>]'
                u'</span>' % self.req._('view all'))
    
    def relations_table(self, entity):
        """yiels 3-tuples (rtype, target, related_list)
        where <related_list> itself a list of :
          - node_id (will be the entity element's DOM id)
          - appropriate javascript's togglePendingDelete() function call
          - status 'pendingdelete' or ''
          - oneline view of related entity
        """
        eid = entity.eid
        pending_deletes = self.req.get_pending_deletes(eid)
        # XXX (adim) : quick fix to get Folder relations
        for label, rschema, target in entity.srelations_by_category(('generic', 'metadata'), 'add'):
            if rschema in self.skip_relations:
                continue
            relatedrset = entity.related(rschema, target, limit=self.limit)
            toggable_rel_link = self.toggable_relation_link_func(rschema)
            related = []
            for row in xrange(relatedrset.rowcount):
                nodeid = relation_id(eid, rschema, target, relatedrset[row][0])
                if nodeid in pending_deletes:
                    status = u'pendingDelete'
                    label = '+'
                else:
                    status = u''
                    label = 'x'
                dellink = toggable_rel_link(eid, nodeid, label)
                eview = self.view('oneline', relatedrset, row=row)
                related.append((nodeid, dellink, status, eview))
            yield (rschema, target, related)
        
    def toggable_relation_link_func(self, rschema):
        if not rschema.has_perm(self.req, 'delete'):
            return lambda x, y, z: u''
        return toggable_relation_link


    def redirect_url(self, entity=None):
        """return a url to use as next direction if there are some information
        specified in current form params, else return the result the reset_url
        method which should be defined in concrete classes
        """
        rparams = redirect_params(self.req.form)
        if rparams:
            return self.build_url('view', **rparams)
        return self.reset_url(entity)

    def reset_url(self, entity):
        raise NotImplementedError('implement me in concrete classes')

    BUTTON_STR = u'<input class="validateButton" type="submit" name="%s" value="%s" tabindex="%s"/>'
    ACTION_SUBMIT_STR = u'<input class="validateButton" type="button" onclick="postForm(\'%s\', \'%s\', \'%s\')" value="%s" tabindex="%s"/>'

    def button_ok(self, label=None, tabindex=None):
        label = self.req._(label or stdmsgs.BUTTON_OK).capitalize()
        return self.BUTTON_STR % ('defaultsubmit', label, tabindex or 2)
    
    def button_apply(self, label=None, tabindex=None):
        label = self.req._(label or stdmsgs.BUTTON_APPLY).capitalize()
        return self.ACTION_SUBMIT_STR % ('__action_apply', label, self.domid, label, tabindex or 3)

    def button_delete(self, label=None, tabindex=None):
        label = self.req._(label or stdmsgs.BUTTON_DELETE).capitalize()
        return self.ACTION_SUBMIT_STR % ('__action_delete', label, self.domid, label, tabindex or 3)
    
    def button_cancel(self, label=None, tabindex=None):
        label = self.req._(label or stdmsgs.BUTTON_CANCEL).capitalize()
        return self.ACTION_SUBMIT_STR % ('__action_cancel', label, self.domid, label, tabindex or 4)
    
    def button_reset(self, label=None, tabindex=None):
        label = self.req._(label or stdmsgs.BUTTON_CANCEL).capitalize()
        return u'<input class="validateButton" type="reset" value="%s" tabindex="%s"/>' % (
            label, tabindex or 4)
        
def toggable_relation_link(eid, nodeid, label='x'):
    js = u"javascript: togglePendingDelete('%s', %s);" % (nodeid, html_escape(dumps(eid)))
    return u'[<a class="handle" href="%s" id="handle%s">%s</a>]' % (js, nodeid, label)

