"""abstract controler classe for CubicWeb web client


:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

import datetime

from cubicweb import typed_eid
from cubicweb.utils import strptime, todate, todatetime
from cubicweb.selectors import yes, require_group_compat
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

def parse_relations_descr(rdescr):
    """parse a string describing some relations, in the form
    subjeids:rtype:objeids
    where subjeids and objeids are eids separeted by a underscore

    return an iterator on (subject eid, relation type, object eid) found
    """
    for rstr in rdescr:
        subjs, rtype, objs = rstr.split(':')
        for subj in subjs.split('_'):
            for obj in objs.split('_'):
                yield typed_eid(subj), rtype, typed_eid(obj)

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
    registered = require_group_compat(AppObject.registered)

    def __init__(self, *args, **kwargs):
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
        if rql:
            self.ensure_ro_rql(rql)
            if not isinstance(rql, unicode):
                rql = unicode(rql, self.req.encoding)
            pp = self.vreg.select_component('magicsearch', self.req)
            self.rset = pp.process_query(rql, self.req)
            return self.rset
        return None

    def check_expected_params(self, params):
        """check that the given list of parameters are specified in the form
        dictionary
        """
        missing = []
        for param in params:
            if not self.req.form.get(param):
                missing.append(param)
        if missing:
            raise RequestError('missing required parameter(s): %s'
                               % ','.join(missing))

    def parse_datetime(self, value, etype='Datetime'):
        """get a datetime or time from a string (according to etype)
        Datetime formatted as Date are accepted
        """
        assert etype in ('Datetime', 'Date', 'Time'), etype
        # XXX raise proper validation error
        if etype == 'Datetime':
            format = self.req.property_value('ui.datetime-format')
            try:
                return todatetime(strptime(value, format))
            except:
                pass
        elif etype == 'Time':
            format = self.req.property_value('ui.time-format')
            try:
                # (adim) I can't find a way to parse a Time with a custom format
                date = strptime(value, format) # this returns a DateTime
                return datetime.time(date.hour, date.minute, date.second)
            except:
                raise ValueError('can\'t parse %r (expected %s)' % (value, format))
        try:
            format = self.req.property_value('ui.date-format')
            dt = strptime(value, format)
            if etype == 'Datetime':
                return todatetime(dt)
            return todate(dt)
        except:
            raise ValueError('can\'t parse %r (expected %s)' % (value, format))


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
            entity = self.req.eid_rset(eid, etype).get_entity(0, 0)
            path, params = entity.after_deletion_path()
            redirect_info.add( (path, tuple(params.iteritems())) )
            entity.delete()
        if len(redirect_info) > 1:
            # In the face of ambiguity, refuse the temptation to guess.
            self._after_deletion_path = 'view', ()
        else:
            self._after_deletion_path = iter(redirect_info).next()
        if len(eidtypes) > 1:
            self.req.set_message(self.req._('entities deleted'))
        else:
            self.req.set_message(self.req._('entity deleted'))

    def delete_relations(self, rdefs):
        """delete relations from the repository"""
        # FIXME convert to using the syntax subject:relation:eids
        execute = self.req.execute
        for subj, rtype, obj in rdefs:
            rql = 'DELETE X %s Y where X eid %%(x)s, Y eid %%(y)s' % rtype
            execute(rql, {'x': subj, 'y': obj}, ('x', 'y'))
        self.req.set_message(self.req._('relations deleted'))

    def insert_relations(self, rdefs):
        """insert relations into the repository"""
        execute = self.req.execute
        for subj, rtype, obj in rdefs:
            rql = 'SET X %s Y where X eid %%(x)s, Y eid %%(y)s' % rtype
            execute(rql, {'x': subj, 'y': obj}, ('x', 'y'))


    def reset(self):
        """reset form parameters and redirect to a view determinated by given
        parameters
        """
        newparams = {}
        # sets message if needed
        if self.req.message:
            newparams['__message'] = self.req.message
        if self.req.form.has_key('__action_apply'):
            self._return_to_edition_view(newparams)
        if self.req.form.has_key('__action_cancel'):
            self._return_to_lastpage(newparams)
        else:
            self._return_to_original_view(newparams)


    def _return_to_original_view(self, newparams):
        """validate-button case"""
        # transforms __redirect[*] parameters into regular form parameters
        newparams.update(redirect_params(self.req.form))
        # find out if we have some explicit `rql` needs
        rql = newparams.pop('rql', None)
        # if rql is needed (explicit __redirectrql or multiple deletions for
        # instance), we have to use the old `view?rql=...` form
        if rql:
            path = 'view'
            newparams['rql'] = rql
        elif '__redirectpath' in self.req.form:
            # if redirect path was explicitly specified in the form, use it
            path = self.req.form['__redirectpath']
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
        url = self.build_url(path, **newparams)
        url = append_url_params(url, self.req.form.get('__redirectparams'))
        raise Redirect(url)


    def _return_to_edition_view(self, newparams):
        """apply-button case"""
        form = self.req.form
        if self._edited_entity:
            path = self._edited_entity.rest_path()
            newparams.pop('rql', None)
        # else, fallback on the old `view?rql=...` url form
        elif 'rql' in self.req.form:
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
        raise Redirect(self.build_url(path, **newparams))


    def _return_to_lastpage(self, newparams):
        """cancel-button case: in this case we are always expecting to go back
        where we came from, and this is not easy. Currently we suppose that
        __redirectpath is specifying that place if found, else we look in the
        request breadcrumbs for the last visited page.
        """
        if '__redirectpath' in self.req.form:
            # if redirect path was explicitly specified in the form, use it
            path = self.req.form['__redirectpath']
            url = self.build_url(path, **newparams)
            url = append_url_params(url, self.req.form.get('__redirectparams'))
        else:
            url = self.req.last_visited_page()
        raise Redirect(url)


from cubicweb import set_log_methods
set_log_methods(Controller, LOGGER)

