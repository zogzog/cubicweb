"""abstract controller classe for CubicWeb web client


:organization: Logilab
:copyright: 2001-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

import datetime

from cubicweb import typed_eid
from cubicweb.selectors import yes
from cubicweb.appobject import AppObject
from cubicweb.web import LOGGER, Redirect, RequestError


NAVIGATION_PARAMETERS = (('vid', '__redirectvid'),
                         ('rql', '__redirectrql'),
                         ('__redirectpath', '__redirectpath'),
                         ('__redirectparams', '__redirectparams'),
                         )
NAV_FORM_PARAMETERS = tuple(fp for ap, fp in NAVIGATION_PARAMETERS)

def redirect_params(form):
    """transform redirection parameters into navigation parameters
    """
    params = {}
    # extract navigation parameters from redirection parameters
    for navparam, redirectparam in NAVIGATION_PARAMETERS:
        if navparam == redirectparam:
            continue
        if redirectparam in form:
            params[navparam] = form[redirectparam]
    return params

def append_url_params(url, params):
    """append raw parameters to the url. Given parameters, if any, are expected
    to be already url-quoted.
    """
    if params:
        if not '?' in url:
            url += '?'
        else:
            url += '&'
        url += params
    return url


class Controller(AppObject):
    """a controller is responsible to make necessary stuff to publish
    a request. There is usually at least one standard "view" controller
    and another linked by forms to edit objects ("edit").
    """
    __registry__ = 'controllers'
    __select__ = yes()

    def __init__(self, *args, **kwargs):
        self.appli = kwargs.pop('appli', None)
        super(Controller, self).__init__(*args, **kwargs)
        # attributes use to control after edition redirection
        self._after_deletion_path = None
        self._edited_entity = None

    def publish(self, rset=None):
        """publish the current request, with an option input rql string
        (already processed if necessary)
        """
        raise NotImplementedError

    # generic methods useful for concret implementations ######################

    def process_rql(self, rql):
        """execute rql if specified"""
        # XXX assigning to self really necessary?
        self.cw_rset = None
        if rql:
            self._cw.ensure_ro_rql(rql)
            if not isinstance(rql, unicode):
                rql = unicode(rql, self._cw.encoding)
            pp = self._cw.vreg['components'].select_or_none('magicsearch', self._cw)
            if pp is not None:
                self.cw_rset = pp.process_query(rql)
        return self.cw_rset

    def check_expected_params(self, params):
        """check that the given list of parameters are specified in the form
        dictionary
        """
        missing = []
        for param in params:
            if not self._cw.form.get(param):
                missing.append(param)
        if missing:
            raise RequestError('missing required parameter(s): %s'
                               % ','.join(missing))


    def notify_edited(self, entity):
        """called by edit_entity() to notify which entity is edited"""
        # NOTE: we can't use entity.rest_path() at this point because
        #       rest_path() could rely on schema constraints (such as a required
        #       relation) that might not be satisfied yet (in case of creations)
        if not self._edited_entity:
            self._edited_entity = entity

    def delete_entities(self, eidtypes):
        """delete entities from the repository"""
        redirect_info = set()
        eidtypes = tuple(eidtypes)
        for eid, etype in eidtypes:
            entity = self._cw.entity_from_eid(eid, etype)
            path, params = entity.after_deletion_path()
            redirect_info.add( (path, tuple(params.iteritems())) )
            entity.delete()
        if len(redirect_info) > 1:
            # In the face of ambiguity, refuse the temptation to guess.
            self._after_deletion_path = 'view', ()
        else:
            self._after_deletion_path = iter(redirect_info).next()
        if len(eidtypes) > 1:
            self._cw.set_message(self._cw._('entities deleted'))
        else:
            self._cw.set_message(self._cw._('entity deleted'))

    def validate_cache(self, view):
        view.set_http_cache_headers()
        self._cw.validate_cache()

    def reset(self):
        """reset form parameters and redirect to a view determinated by given
        parameters
        """
        newparams = {}
        # sets message if needed
        if self._cw.message:
            newparams['__message'] = self._cw.message
        if self._cw.form.has_key('__action_apply'):
            self._return_to_edition_view(newparams)
        if self._cw.form.has_key('__action_cancel'):
            self._return_to_lastpage(newparams)
        else:
            self._return_to_original_view(newparams)


    def _return_to_original_view(self, newparams):
        """validate-button case"""
        # transforms __redirect[*] parameters into regular form parameters
        newparams.update(redirect_params(self._cw.form))
        # find out if we have some explicit `rql` needs
        rql = newparams.pop('rql', None)
        # if rql is needed (explicit __redirectrql or multiple deletions for
        # instance), we have to use the old `view?rql=...` form
        if rql:
            path = 'view'
            newparams['rql'] = rql
        elif '__redirectpath' in self._cw.form:
            # if redirect path was explicitly specified in the form, use it
            path = self._cw.form['__redirectpath']
            if self._edited_entity and path != self._edited_entity.rest_path():
                # XXX may be here on modification? if yes the message should be
                # modified where __createdpath is detected (cw.web.request)
                newparams['__createdpath'] = self._edited_entity.rest_path()
        elif self._after_deletion_path:
            # else it should have been set during form processing
            path, params = self._after_deletion_path
            params = dict(params) # params given as tuple
            params.update(newparams)
            newparams = params
        elif self._edited_entity:
            path = self._edited_entity.rest_path()
        else:
            path = 'view'
        url = self._cw.build_url(path, **newparams)
        url = append_url_params(url, self._cw.form.get('__redirectparams'))
        raise Redirect(url)


    def _return_to_edition_view(self, newparams):
        """apply-button case"""
        form = self._cw.form
        if self._edited_entity:
            path = self._edited_entity.rest_path()
            newparams.pop('rql', None)
        # else, fallback on the old `view?rql=...` url form
        elif 'rql' in self._cw.form:
            path = 'view'
            newparams['rql'] = form['rql']
        else:
            self.warning("the edited data seems inconsistent")
            path = 'view'
        # pick up the correction edition view
        if form.get('__form_id'):
            newparams['vid'] = form['__form_id']
        # re-insert copy redirection parameters
        for redirectparam in NAV_FORM_PARAMETERS:
            if redirectparam in form:
                newparams[redirectparam] = form[redirectparam]
        raise Redirect(self._cw.build_url(path, **newparams))


    def _return_to_lastpage(self, newparams):
        """cancel-button case: in this case we are always expecting to go back
        where we came from, and this is not easy. Currently we suppose that
        __redirectpath is specifying that place if found, else we look in the
        request breadcrumbs for the last visited page.
        """
        if '__redirectpath' in self._cw.form:
            # if redirect path was explicitly specified in the form, use it
            path = self._cw.form['__redirectpath']
            url = self._cw.build_url(path, **newparams)
            url = append_url_params(url, self._cw.form.get('__redirectparams'))
        else:
            url = self._cw.last_visited_page()
        raise Redirect(url)


from cubicweb import set_log_methods
set_log_methods(Controller, LOGGER)

