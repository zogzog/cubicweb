"""special management views to manage repository content (initialization and
restoration).

:organization: Logilab
:copyright: 2008-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

from os.path import exists, join, abspath
from pickle import loads, dumps

from logilab.common.decorators import cached
from logilab.mtconverter import xml_escape

from cubicweb.selectors import none_rset, match_user_groups
from cubicweb.view import StartupView
from cubicweb.web import Redirect
from cubicweb.goa.dbinit import fix_entities, init_persistent_schema, insert_versions

from google.appengine.api.datastore import Entity, Key, Get, Put, Delete
from google.appengine.api.datastore_types import Blob
from google.appengine.api.datastore_errors import EntityNotFoundError


def _get_status(name, create=True):
    key = Key.from_path('EApplicationStatus', name)
    try:
        status = Get(key)
    except EntityNotFoundError:
        if create:
            status = Entity('EApplicationStatus', name=name)
        else:
            status = None
    return status


class AuthInfo(StartupView):
    """special management view to get cookie values to give to laxctl commands
    which are doing datastore administration requests
    """
    id = 'authinfo'
    __select__ = none_rset() & match_user_groups('managers')

    def call(self):
        cookie = self.req.get_cookie()
        values = []
        if self.config['use-google-auth']:
            for param in ('ACSID', 'dev_appserver_login'):
                morsel = cookie.get(param)
                if morsel:
                    values.append('%s=%s' % (param, morsel.value))
                    break
        values.append('__session=%s' % cookie['__session'].value)
        self.w(u"<p>pass this flag to the client: --cookie='%s'</p>"
               % xml_escape('; '.join(values)))



class ContentInit(StartupView):
    """special management view to initialize content of a repository,
    step by step to avoid depassing quotas
    """
    id = 'contentinit'
    __select__ = none_rset() & match_user_groups('managers')

    def server_session(self):
        ssession = self.config.repo_session(self.req.cnx.sessionid)
        ssession.set_pool()
        return ssession

    def end_core_step(self, msg, status, stepid):
        status['cpath'] = ''
        status['stepid'] = stepid
        Put(status)
        self.msg(msg)

    def call(self):
        status = _get_status('creation')
        if status.get('finished'):
            self.redirect('process already completed')
        config = self.config
        # execute cubicweb's post<event> script
        #mhandler.exec_event_script('post%s' % event)
        # execute cubes'post<event> script if any
        paths = [p for p in config.cubes_path() + [config.apphome]
                 if exists(join(p, 'migration'))]
        paths = [abspath(p) for p in (reversed(paths))]
        cpath = status.get('cpath')
        if cpath is None and status.get('stepid') is None:
            init_persistent_schema(self.server_session(), self.schema)
            self.end_core_step(u'inserted schema entities', status, 0)
            return
        if cpath == '' and status.get('stepid') == 0:
            fix_entities(self.schema)
            self.end_core_step(u'fixed bootstrap groups and users', status, 1)
            return
        if cpath == '' and status.get('stepid') == 1:
            insert_versions(self.server_session(), self.config)
            self.end_core_step(u'inserted software versions', status, None)
            return
        for i, path in enumerate(paths):
            if not cpath or cpath == path:
                self.info('running %s', path)
                stepid = status.get('stepid')
                context = status.get('context')
                if context is not None:
                    context = loads(context)
                else:
                    context = {}
                stepid = self._migrhandler.exec_event_script(
                    'postcreate', path, 'stepable_postcreate', stepid, context)
                if stepid is None: # finished for this script
                    # reset script state
                    context = stepid = None
                    # next time, go to the next script
                    self.msg(u'finished postcreate for %s' % path)
                    try:
                        path = paths[i+1]
                        self.continue_link()
                    except IndexError:
                        status['finished'] = True
                        path = None
                        self.redirect('process completed')
                else:
                    if context.get('stepidx'):
                        self.msg(u'created %s entities for step %s of %s' % (
                            context['stepidx'], stepid, path))
                    else:
                        self.msg(u'finished postcreate step %s for %s' % (
                            stepid, path))
                    context = Blob(dumps(context))
                    self.continue_link()
                status['context'] = context
                status['stepid'] = stepid
                status['cpath'] = path
                break
        else:
            if not cpath:
                # nothing to be done
                status['finished'] = True
                self.redirect('process completed')
            else:
                # Note the error: is expected by the laxctl command line tool,
                # deal with this if internationalization is introduced
                self.msg(u'error: strange creation state, can\'t find %s'
                         % cpath)
                self.w(u'<div>click <a href="%s?vid=contentclear">here</a> to '
                       '<b>delete all datastore content</b> so process can be '
                       'reinitialized</div>' % xml_escape(self.req.base_url()))
        Put(status)

    @property
    @cached
    def _migrhandler(self):
        return self.config.migration_handler(self.schema, interactive=False,
                                             cnx=self.req.cnx,
                                             repo=self.config.repository())

    def msg(self, msg):
        self.w(u'<div class="message">%s</div>' % xml_escape(msg))
    def redirect(self, msg):
        raise Redirect(self.req.build_url('', msg))
    def continue_link(self):
        self.w(u'<a href="%s">continue</a><br/>' % xml_escape(self.req.url()))


class ContentClear(StartupView):
    id = 'contentclear'
    __select__ = none_rset() & match_user_groups('managers')
    skip_etypes = ('CWGroup', 'CWUser')

    def call(self):
        # XXX should use unsafe execute with all hooks deactivated
        # XXX step by catching datastore errors?
        for eschema in self.schema.entities():
            if eschema.final or eschema in self.skip_etypes:
                continue
            self.req.execute('DELETE %s X' % eschema)
            self.w(u'deleted all %s entities<br/>' % eschema)
        status = _get_status('creation', create=False)
        if status:
            Delete(status)
        self.w(u'done<br/>')
        self.w(u'click <a href="%s?vid=contentinit">here</a> to start the data '
               'initialization process<br/>' % self.req.base_url())
