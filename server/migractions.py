# copyright 2003-2011 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""a class implementing basic actions used in migration scripts.

The following schema actions are supported for now:
* add/drop/rename attribute
* add/drop entity/relation type
* rename entity type

The following data actions are supported for now:
* add an entity
* execute raw RQL queries
"""

from __future__ import with_statement

__docformat__ = "restructuredtext en"

import sys
import os
import tarfile
import tempfile
import shutil
import os.path as osp
from datetime import datetime
from glob import glob
from copy import copy
from warnings import warn
from contextlib import contextmanager

from logilab.common.deprecation import deprecated
from logilab.common.decorators import cached, clear_cache

from yams.constraints import SizeConstraint
from yams.schema2sql import eschema2sql, rschema2sql
from yams.schema import RelationDefinitionSchema

from cubicweb import AuthenticationError, ExecutionError
from cubicweb.selectors import is_instance
from cubicweb.schema import (ETYPE_NAME_MAP, META_RTYPES, VIRTUAL_RTYPES,
                             PURE_VIRTUAL_RTYPES,
                             CubicWebRelationSchema, order_eschemas)
from cubicweb.cwvreg import CW_EVENT_MANAGER
from cubicweb.dbapi import get_repository, repo_connect
from cubicweb.migration import MigrationHelper, yes
from cubicweb.server.session import hooks_control
from cubicweb.server import hook
try:
    from cubicweb.server import SOURCE_TYPES, schemaserial as ss
    from cubicweb.server.utils import manager_userpasswd
    from cubicweb.server.sqlutils import sqlexec, SQL_PREFIX
except ImportError: # LAX
    pass


def mock_object(**params):
    return type('Mock', (), params)()

class ClearGroupMap(hook.Hook):
    __regid__ = 'cw.migration.clear_group_mapping'
    __select__ = hook.Hook.__select__ & is_instance('CWGroup')
    events = ('after_add_entity', 'after_update_entity',)
    def __call__(self):
        clear_cache(self.mih, 'group_mapping')
        self.mih._synchronized.clear()

    @classmethod
    def mih_register(cls, repo):
        # may be already registered in tests (e.g. unittest_migractions at
        # least)
        if not cls.__regid__ in repo.vreg['after_add_entity_hooks']:
            repo.vreg.register(ClearGroupMap)

class ServerMigrationHelper(MigrationHelper):
    """specific migration helper for server side  migration scripts,
    providind actions related to schema/data migration
    """

    def __init__(self, config, schema, interactive=True,
                 repo=None, cnx=None, verbosity=1, connect=True):
        MigrationHelper.__init__(self, config, interactive, verbosity)
        if not interactive:
            assert cnx
            assert repo
        if cnx is not None:
            assert repo
            self._cnx = cnx
            self.repo = repo
        elif connect:
            self.repo_connect()
        # no config on shell to a remote instance
        if config is not None and (cnx or connect):
            repo = self.repo
            self.session.data['rebuild-infered'] = False
            # register a hook to clear our group_mapping cache and the
            # self._synchronized set when some group is added or updated
            ClearGroupMap.mih = self
            ClearGroupMap.mih_register(repo)
            CW_EVENT_MANAGER.bind('after-registry-reload',
                                  ClearGroupMap.mih_register, repo)
            # notify we're starting maintenance (called instead of server_start
            # which is called on regular start
            repo.hm.call_hooks('server_maintenance', repo=repo)
        if not schema and not getattr(config, 'quick_start', False):
            insert_lperms = self.repo.get_versions()['cubicweb'] < (3, 14, 0) and 'localperms' in config.available_cubes()
            if insert_lperms:
                cubes = config._cubes
                config._cubes += ('localperms',)
            try:
                schema = config.load_schema(expand_cubes=True)
            finally:
                if insert_lperms:
                    config._cubes = cubes
        self.fs_schema = schema
        self._synchronized = set()

    # overriden from base MigrationHelper ######################################

    @cached
    def repo_connect(self):
        self.repo = get_repository(method='inmemory', config=self.config)
        return self.repo

    def cube_upgraded(self, cube, version):
        self.cmd_set_property('system.version.%s' % cube.lower(),
                              unicode(version))
        self.commit()

    def shutdown(self):
        if self.repo is not None:
            self.repo.shutdown()

    def migrate(self, vcconf, toupgrade, options):
        if not options.fs_only:
            if options.backup_db is None:
                self.backup_database()
            elif options.backup_db:
                self.backup_database(askconfirm=False)
        # disable notification during migration
        with hooks_control(self.session, self.session.HOOKS_ALLOW_ALL, 'notification'):
            super(ServerMigrationHelper, self).migrate(vcconf, toupgrade, options)

    def cmd_process_script(self, migrscript, funcname=None, *args, **kwargs):
        try:
            return super(ServerMigrationHelper, self).cmd_process_script(
                  migrscript, funcname, *args, **kwargs)
        except ExecutionError, err:
            print >> sys.stderr, "-> %s" % err
        except BaseException:
            self.rollback()
            raise

    # Adjust docstring
    cmd_process_script.__doc__ = MigrationHelper.cmd_process_script.__doc__

    # server specific migration methods ########################################

    def backup_database(self, backupfile=None, askconfirm=True, format='native'):
        config = self.config
        repo = self.repo_connect()
        # paths
        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        instbkdir = osp.join(config.appdatahome, 'backup')
        if not osp.exists(instbkdir):
            os.makedirs(instbkdir)
        backupfile = backupfile or osp.join(instbkdir, '%s-%s.tar.gz'
                                            % (config.appid, timestamp))
        # check backup has to be done
        if osp.exists(backupfile) and not \
                self.confirm('Backup file %s exists, overwrite it?' % backupfile):
            print '-> no backup done.'
            return
        elif askconfirm and not self.confirm('Backup %s database?' % config.appid):
            print '-> no backup done.'
            return
        open(backupfile,'w').close() # kinda lock
        os.chmod(backupfile, 0600)
        # backup
        tmpdir = tempfile.mkdtemp()
        try:
            failed = False
            for source in repo.sources:
                try:
                    source.backup(osp.join(tmpdir, source.uri), self.confirm, format=format)
                except Exception, ex:
                    print '-> error trying to backup %s [%s]' % (source.uri, ex)
                    if not self.confirm('Continue anyway?', default='n'):
                        raise SystemExit(1)
                    else:
                        failed = True
            with open(osp.join(tmpdir, 'format.txt'), 'w') as format_file:
                format_file.write('%s\n' % format)
            with open(osp.join(tmpdir, 'versions.txt'), 'w') as version_file:
                versions = repo.get_versions()
                for cube, version in versions.iteritems():
                    version_file.write('%s %s\n' % (cube, version))
            if not failed:
                bkup = tarfile.open(backupfile, 'w|gz')
                for filename in os.listdir(tmpdir):
                    bkup.add(osp.join(tmpdir, filename), filename)
                bkup.close()
                # call hooks
                repo.hm.call_hooks('server_backup', repo=repo, timestamp=timestamp)
                # done
                print '-> backup file',  backupfile
        finally:
            shutil.rmtree(tmpdir)

    def restore_database(self, backupfile, drop=True, systemonly=True,
                         askconfirm=True, format='native'):
        # check
        if not osp.exists(backupfile):
            raise ExecutionError("Backup file %s doesn't exist" % backupfile)
        if askconfirm and not self.confirm('Restore %s database from %s ?'
                                           % (self.config.appid, backupfile)):
            return
        # unpack backup
        tmpdir = tempfile.mkdtemp()
        try:
            bkup = tarfile.open(backupfile, 'r|gz')
        except tarfile.ReadError:
            # assume restoring old backup
            shutil.copy(backupfile, osp.join(tmpdir, 'system'))
        else:
            for name in bkup.getnames():
                if name[0] in '/.':
                    raise ExecutionError('Security check failed, path starts with "/" or "."')
            bkup.close() # XXX seek error if not close+open !?!
            bkup = tarfile.open(backupfile, 'r|gz')
            bkup.extractall(path=tmpdir)
            bkup.close()
        if osp.isfile(osp.join(tmpdir, 'format.txt')):
            with open(osp.join(tmpdir, 'format.txt')) as format_file:
                written_format = format_file.readline().strip()
                if written_format in ('portable', 'native'):
                    format = written_format
        self.config.init_cnxset_pool = False
        repo = self.repo_connect()
        for source in repo.sources:
            if systemonly and source.uri != 'system':
                continue
            try:
                source.restore(osp.join(tmpdir, source.uri), self.confirm, drop, format)
            except Exception, exc:
                print '-> error trying to restore %s [%s]' % (source.uri, exc)
                if not self.confirm('Continue anyway?', default='n'):
                    raise SystemExit(1)
        shutil.rmtree(tmpdir)
        # call hooks
        repo.init_cnxset_pool()
        repo.hm.call_hooks('server_restore', repo=repo, timestamp=backupfile)
        print '-> database restored.'

    @property
    def cnx(self):
        """lazy connection"""
        try:
            return self._cnx
        except AttributeError:
            sourcescfg = self.repo.config.sources()
            try:
                login = sourcescfg['admin']['login']
                pwd = sourcescfg['admin']['password']
            except KeyError:
                login, pwd = manager_userpasswd()
            while True:
                try:
                    self._cnx = repo_connect(self.repo, login, password=pwd)
                    if not 'managers' in self._cnx.user(self.session).groups:
                        print 'migration need an account in the managers group'
                    else:
                        break
                except AuthenticationError:
                    print 'wrong user/password'
                except (KeyboardInterrupt, EOFError):
                    print 'aborting...'
                    sys.exit(0)
                try:
                    login, pwd = manager_userpasswd()
                except (KeyboardInterrupt, EOFError):
                    print 'aborting...'
                    sys.exit(0)
            self.session.keep_cnxset_mode('transaction')
            self.session.data['rebuild-infered'] = False
            return self._cnx

    @property
    def session(self):
        if self.config is not None:
            session = self.repo._get_session(self.cnx.sessionid)
            if session.cnxset is None:
                session.set_read_security(False)
                session.set_write_security(False)
            session.set_cnxset()
            return session
        # no access to session on remote instance
        return None

    def commit(self):
        if hasattr(self, '_cnx'):
            self._cnx.commit()
        if self.session:
            self.session.set_cnxset()

    def rollback(self):
        if hasattr(self, '_cnx'):
            self._cnx.rollback()
        if self.session:
            self.session.set_cnxset()

    def rqlexecall(self, rqliter, ask_confirm=False):
        for rql, kwargs in rqliter:
            self.rqlexec(rql, kwargs, ask_confirm=ask_confirm)

    @cached
    def _create_context(self):
        """return a dictionary to use as migration script execution context"""
        context = super(ServerMigrationHelper, self)._create_context()
        context.update({'commit': self.checkpoint,
                        'rollback': self.rollback,
                        'checkpoint': deprecated('[3.6] use commit')(self.checkpoint),
                        'sql': self.sqlexec,
                        'rql': self.rqlexec,
                        'rqliter': self.rqliter,
                        'schema': self.repo.get_schema(),
                        'cnx': self.cnx,
                        'fsschema': self.fs_schema,
                        'session' : self.session,
                        'repo' : self.repo,
                        'synchronize_schema': deprecated()(self.cmd_sync_schema_props_perms), # 3.4
                        'synchronize_eschema': deprecated()(self.cmd_sync_schema_props_perms), # 3.4
                        'synchronize_rschema': deprecated()(self.cmd_sync_schema_props_perms), # 3.4
                        })
        return context

    @cached
    def group_mapping(self):
        """cached group mapping"""
        return ss.group_mapping(self._cw)

    @cached
    def cstrtype_mapping(self):
        """cached constraint types mapping"""
        return ss.cstrtype_mapping(self._cw)

    def exec_event_script(self, event, cubepath=None, funcname=None,
                          *args, **kwargs):
        if cubepath:
            apc = osp.join(cubepath, 'migration', '%s.py' % event)
        else:
            apc = osp.join(self.config.migration_scripts_dir(), '%s.py' % event)
        if osp.exists(apc):
            if self.config.free_wheel:
                self.cmd_deactivate_verification_hooks()
            self.info('executing %s', apc)
            confirm = self.confirm
            execscript_confirm = self.execscript_confirm
            self.confirm = yes
            self.execscript_confirm = yes
            try:
                return self.cmd_process_script(apc, funcname, *args, **kwargs)
            finally:
                self.confirm = confirm
                self.execscript_confirm = execscript_confirm
                if self.config.free_wheel:
                    self.cmd_reactivate_verification_hooks()

    def install_custom_sql_scripts(self, directory, driver):
        sql_scripts = []
        for fpath in glob(osp.join(directory, '*.sql.%s' % driver)):
            newname = osp.basename(fpath).replace('.sql.%s' % driver,
                                                  '.%s.sql' % driver)
            warn('[3.5.6] rename %s into %s' % (fpath, newname),
                 DeprecationWarning)
            sql_scripts.append(fpath)
        sql_scripts += glob(osp.join(directory, '*.%s.sql' % driver))
        for fpath in sql_scripts:
            print '-> installing', fpath
            try:
                sqlexec(open(fpath).read(), self.session.system_sql, False,
                        delimiter=';;')
            except Exception, exc:
                print '-> ERROR:', exc, ', skipping', fpath

    # schema synchronization internals ########################################

    def _synchronize_permissions(self, erschema, teid):
        """permission synchronization for an entity or relation type"""
        assert teid, erschema
        if 'update' in erschema.ACTIONS or erschema.final:
            # entity type
            exprtype = u'ERQLExpression'
        else:
            # relation type
            exprtype = u'RRQLExpression'
        gm = self.group_mapping()
        confirm = self.verbosity >= 2
        # * remove possibly deprecated permission (eg in the persistent schema
        #   but not in the new schema)
        # * synchronize existing expressions
        # * add new groups/expressions
        for action in erschema.ACTIONS:
            perm = '%s_permission' % action
            # handle groups
            newgroups = list(erschema.get_groups(action))
            for geid, gname in self.rqlexec('Any G, GN WHERE T %s G, G name GN, '
                                            'T eid %%(x)s' % perm, {'x': teid},
                                            ask_confirm=False):
                if not gname in newgroups:
                    if not confirm or self.confirm('Remove %s permission of %s to %s?'
                                                   % (action, erschema, gname)):
                        self.rqlexec('DELETE T %s G WHERE G eid %%(x)s, T eid %s'
                                     % (perm, teid),
                                     {'x': geid}, ask_confirm=False)
                else:
                    newgroups.remove(gname)
            for gname in newgroups:
                if not confirm or self.confirm('Grant %s permission of %s to %s?'
                                               % (action, erschema, gname)):
                    try:
                        self.rqlexec('SET T %s G WHERE G eid %%(x)s, T eid %s'
                                     % (perm, teid),
                                     {'x': gm[gname]}, ask_confirm=False)
                    except KeyError:
                        self.error('can grant %s perm to unexistant group %s',
                                   action, gname)
            # handle rql expressions
            newexprs = dict((expr.expression, expr) for expr in erschema.get_rqlexprs(action))
            for expreid, expression in self.rqlexec('Any E, EX WHERE T %s E, E expression EX, '
                                                    'T eid %s' % (perm, teid),
                                                    ask_confirm=False):
                if not expression in newexprs:
                    if not confirm or self.confirm('Remove %s expression for %s permission of %s?'
                                                   % (expression, action, erschema)):
                        # deleting the relation will delete the expression entity
                        self.rqlexec('DELETE T %s E WHERE E eid %%(x)s, T eid %s'
                                     % (perm, teid),
                                     {'x': expreid}, ask_confirm=False)
                else:
                    newexprs.pop(expression)
            for expression in newexprs.values():
                expr = expression.expression
                if not confirm or self.confirm('Add %s expression for %s permission of %s?'
                                               % (expr, action, erschema)):
                    self.rqlexec('INSERT RQLExpression X: X exprtype %%(exprtype)s, '
                                 'X expression %%(expr)s, X mainvars %%(vars)s, T %s X '
                                 'WHERE T eid %%(x)s' % perm,
                                 {'expr': expr, 'exprtype': exprtype,
                                  'vars': u','.join(sorted(expression.mainvars)),
                                  'x': teid},
                                 ask_confirm=False)

    def _synchronize_rschema(self, rtype, syncrdefs=True,
                             syncperms=True, syncprops=True):
        """synchronize properties of the persistent relation schema against its
        current definition:

        * description
        * symmetric, meta
        * inlined
        * relation definitions if `syncrdefs`
        * permissions if `syncperms`

        physical schema changes should be handled by repository's schema hooks
        """
        rtype = str(rtype)
        if rtype in self._synchronized:
            return
        self._synchronized.add(rtype)
        rschema = self.fs_schema.rschema(rtype)
        reporschema = self.repo.schema.rschema(rtype)
        if syncprops:
            assert reporschema.eid, reporschema
            self.rqlexecall(ss.updaterschema2rql(rschema, reporschema.eid),
                            ask_confirm=self.verbosity>=2)
        if syncrdefs:
            for subj, obj in rschema.rdefs:
                if (subj, obj) not in reporschema.rdefs:
                    continue
                if rschema in VIRTUAL_RTYPES:
                    continue
                self._synchronize_rdef_schema(subj, rschema, obj,
                                              syncprops=syncprops,
                                              syncperms=syncperms)

    def _synchronize_eschema(self, etype, syncrdefs=True,
                             syncperms=True, syncprops=True):
        """synchronize properties of the persistent entity schema against
        its current definition:

        * description
        * internationalizable, fulltextindexed, indexed, meta
        * relations from/to this entity
        * __unique_together__
        * permissions if `syncperms`
        """
        etype = str(etype)
        if etype in self._synchronized:
            return
        self._synchronized.add(etype)
        repoeschema = self.repo.schema.eschema(etype)
        try:
            eschema = self.fs_schema.eschema(etype)
        except KeyError:
            return # XXX somewhat unexpected, no?...
        if syncprops:
            repospschema = repoeschema.specializes()
            espschema = eschema.specializes()
            if repospschema and not espschema:
                self.rqlexec('DELETE X specializes Y WHERE X is CWEType, X name %(x)s',
                             {'x': str(repoeschema)}, ask_confirm=False)
            elif not repospschema and espschema:
                self.rqlexec('SET X specializes Y WHERE X is CWEType, X name %(x)s, '
                             'Y is CWEType, Y name %(y)s',
                             {'x': str(repoeschema), 'y': str(espschema)},
                             ask_confirm=False)
            self.rqlexecall(ss.updateeschema2rql(eschema, repoeschema.eid),
                            ask_confirm=self.verbosity >= 2)
        if syncperms:
            self._synchronize_permissions(eschema, repoeschema.eid)
        if syncrdefs:
            for rschema, targettypes, role in eschema.relation_definitions(True):
                if rschema in VIRTUAL_RTYPES:
                    continue
                if role == 'subject':
                    if not rschema in repoeschema.subject_relations():
                        continue
                    subjtypes, objtypes = [etype], targettypes
                else: # role == 'object'
                    if not rschema in repoeschema.object_relations():
                        continue
                    subjtypes, objtypes = targettypes, [etype]
                self._synchronize_rschema(rschema, syncrdefs=False,
                                          syncprops=syncprops, syncperms=syncperms)
                reporschema = self.repo.schema.rschema(rschema)
                for subj in subjtypes:
                    for obj in objtypes:
                        if (subj, obj) not in reporschema.rdefs:
                            continue
                        self._synchronize_rdef_schema(subj, rschema, obj,
                                                      syncprops=syncprops, syncperms=syncperms)
        if syncprops: # need to process __unique_together__ after rdefs were processed
            repo_unique_together = set([frozenset(ut)
                                        for ut in repoeschema._unique_together])
            unique_together = set([frozenset(ut)
                                   for ut in eschema._unique_together])
            for ut in repo_unique_together - unique_together:
                restrictions = []
                substs = {'x': repoeschema.eid}
                for i, col in enumerate(ut):
                    restrictions.append('C relations T%(i)d, '
                                       'T%(i)d name %%(T%(i)d)s' % {'i': i})
                    substs['T%d'%i] = col
                self.rqlexec('DELETE CWUniqueTogetherConstraint C '
                             'WHERE C constraint_of E, '
                             '      E eid %%(x)s,'
                             '      %s' % ', '.join(restrictions),
                             substs)
            for ut in unique_together - repo_unique_together:
                rql, substs = ss.uniquetogether2rql(eschema, ut)
                substs['x'] = repoeschema.eid
                self.rqlexec(rql, substs)

    def _synchronize_rdef_schema(self, subjtype, rtype, objtype,
                                 syncperms=True, syncprops=True):
        """synchronize properties of the persistent relation definition schema
        against its current definition:
        * order and other properties
        * constraints
        """
        subjtype, objtype = str(subjtype), str(objtype)
        rschema = self.fs_schema.rschema(rtype)
        reporschema = self.repo.schema.rschema(rschema)
        if (subjtype, rschema, objtype) in self._synchronized:
            return
        self._synchronized.add((subjtype, rschema, objtype))
        if rschema.symmetric:
            self._synchronized.add((objtype, rschema, subjtype))
        rdef = rschema.rdef(subjtype, objtype)
        if rdef.infered:
            return # don't try to synchronize infered relation defs
        repordef = reporschema.rdef(subjtype, objtype)
        confirm = self.verbosity >= 2
        if syncprops:
            # properties
            self.rqlexecall(ss.updaterdef2rql(rdef, repordef.eid),
                            ask_confirm=confirm)
            # constraints
            newconstraints = list(rdef.constraints)
            # 1. remove old constraints and update constraints of the same type
            # NOTE: don't use rschema.constraint_by_type because it may be
            #       out of sync with newconstraints when multiple
            #       constraints of the same type are used
            for cstr in repordef.constraints:
                for newcstr in newconstraints:
                    if newcstr.type() == cstr.type():
                        break
                else:
                    newcstr = None
                if newcstr is None:
                    self.rqlexec('DELETE X constrained_by C WHERE C eid %(x)s',
                                 {'x': cstr.eid}, ask_confirm=confirm)
                else:
                    newconstraints.remove(newcstr)
                    value = unicode(newcstr.serialize())
                    if value != unicode(cstr.serialize()):
                        self.rqlexec('SET X value %(v)s WHERE X eid %(x)s',
                                     {'x': cstr.eid, 'v': value},
                                     ask_confirm=confirm)
            # 2. add new constraints
            cstrtype_map = self.cstrtype_mapping()
            self.rqlexecall(ss.constraints2rql(cstrtype_map, newconstraints,
                                               repordef.eid),
                            ask_confirm=confirm)
        if syncperms and not rschema in VIRTUAL_RTYPES:
            self._synchronize_permissions(rdef, repordef.eid)

    # base actions ############################################################

    def checkpoint(self, ask_confirm=True):
        """checkpoint action"""
        if not ask_confirm or self.confirm('Commit now ?', shell=False):
            self.commit()

    def cmd_add_cube(self, cube, update_database=True):
        self.cmd_add_cubes( (cube,), update_database)

    def cmd_add_cubes(self, cubes, update_database=True):
        """update_database is telling if the database schema should be updated
        or if only the relevant eproperty should be inserted (for the case where
        a cube has been extracted from an existing instance, so the
        cube schema is already in there)
        """
        newcubes = super(ServerMigrationHelper, self).cmd_add_cubes(cubes)
        if not newcubes:
            return
        for cube in newcubes:
            self.cmd_set_property('system.version.'+cube,
                                  self.config.cube_version(cube))
            # ensure added cube is in config cubes
            # XXX worth restoring on error?
            if not cube in self.config._cubes:
                self.config._cubes += (cube,)
        if not update_database:
            self.commit()
            return
        newcubes_schema = self.config.load_schema(construction_mode='non-strict')
        # XXX we have to replace fs_schema, used in cmd_add_relation_type
        # etc. and fsschema of migration script contexts
        self.fs_schema = newcubes_schema
        self.update_context('fsschema', self.fs_schema)
        new = set()
        # execute pre-create files
        driver = self.repo.system_source.dbdriver
        for pack in reversed(newcubes):
            cubedir = self.config.cube_dir(pack)
            self.install_custom_sql_scripts(osp.join(cubedir, 'schema'), driver)
            self.exec_event_script('precreate', cubedir)
        # add new entity and relation types
        for rschema in newcubes_schema.relations():
            if not rschema in self.repo.schema:
                self.cmd_add_relation_type(rschema.type)
                new.add(rschema.type)
        toadd = [eschema for eschema in newcubes_schema.entities()
                 if not eschema in self.repo.schema]
        for eschema in order_eschemas(toadd):
            self.cmd_add_entity_type(eschema.type)
            new.add(eschema.type)
        # check if attributes has been added to existing entities
        for rschema in newcubes_schema.relations():
            existingschema = self.repo.schema.rschema(rschema.type)
            for (fromtype, totype) in rschema.rdefs:
                if (fromtype, totype) in existingschema.rdefs:
                    continue
                # check we should actually add the relation definition
                if not (fromtype in new or totype in new or rschema in new):
                    continue
                self.cmd_add_relation_definition(str(fromtype), rschema.type,
                                                 str(totype))
        # execute post-create files
        for pack in reversed(newcubes):
            self.exec_event_script('postcreate', self.config.cube_dir(pack))
            self.commit()

    def cmd_remove_cube(self, cube, removedeps=False):
        removedcubes = super(ServerMigrationHelper, self).cmd_remove_cube(
            cube, removedeps)
        if not removedcubes:
            return
        fsschema = self.fs_schema
        removedcubes_schema = self.config.load_schema(construction_mode='non-strict')
        reposchema = self.repo.schema
        # execute pre-remove files
        for pack in reversed(removedcubes):
            self.exec_event_script('preremove', self.config.cube_dir(pack))
        # remove cubes'entity and relation types
        for rschema in fsschema.relations():
            if not rschema in removedcubes_schema and rschema in reposchema:
                self.cmd_drop_relation_type(rschema.type)
        toremove = [eschema for eschema in fsschema.entities()
                    if not eschema in removedcubes_schema
                    and eschema in reposchema]
        for eschema in reversed(order_eschemas(toremove)):
            self.cmd_drop_entity_type(eschema.type)
        for rschema in fsschema.relations():
            if rschema in removedcubes_schema and rschema in reposchema:
                # check if attributes/relations has been added to entities from
                # other cubes
                for fromtype, totype in rschema.rdefs:
                    if (fromtype, totype) not in removedcubes_schema[rschema.type].rdefs and \
                           (fromtype, totype) in reposchema[rschema.type].rdefs:
                        self.cmd_drop_relation_definition(
                            str(fromtype), rschema.type, str(totype))
        # execute post-remove files
        for cube in reversed(removedcubes):
            self.exec_event_script('postremove', self.config.cube_dir(cube))
            self.rqlexec('DELETE CWProperty X WHERE X pkey %(pk)s',
                         {'pk': u'system.version.'+cube}, ask_confirm=False)
            self.commit()

    # schema migration actions ################################################

    def cmd_add_attribute(self, etype, attrname, attrtype=None, commit=True):
        """add a new attribute on the given entity type"""
        if attrtype is None:
            rschema = self.fs_schema.rschema(attrname)
            attrtype = rschema.objects(etype)[0]
        self.cmd_add_relation_definition(etype, attrname, attrtype, commit=commit)

    def cmd_drop_attribute(self, etype, attrname, commit=True):
        """drop an existing attribute from the given entity type

        `attrname` is a string giving the name of the attribute to drop
        """
        try:
            rschema = self.repo.schema.rschema(attrname)
            attrtype = rschema.objects(etype)[0]
        except KeyError:
            print 'warning: attribute %s %s is not known, skip deletion' % (
                etype, attrname)
        else:
            self.cmd_drop_relation_definition(etype, attrname, attrtype,
                                              commit=commit)

    def cmd_rename_attribute(self, etype, oldname, newname, commit=True):
        """rename an existing attribute of the given entity type

        `oldname` is a string giving the name of the existing attribute
        `newname` is a string giving the name of the renamed attribute
        """
        eschema = self.fs_schema.eschema(etype)
        attrtype = eschema.destination(newname)
        # have to commit this first step anyway to get the definition
        # actually in the schema
        self.cmd_add_attribute(etype, newname, attrtype, commit=True)
        # skipp NULL values if the attribute is required
        rql = 'SET X %s VAL WHERE X is %s, X %s VAL' % (newname, etype, oldname)
        card = eschema.rdef(newname).cardinality[0]
        if card == '1':
            rql += ', NOT X %s NULL' % oldname
        self.rqlexec(rql, ask_confirm=self.verbosity>=2)
        # XXX if both attributes fulltext indexed, should skip fti rebuild
        # XXX if old attribute was fti indexed but not the new one old value
        # won't be removed from the index (this occurs on other kind of
        # fulltextindexed change...)
        self.cmd_drop_attribute(etype, oldname, commit=commit)

    def cmd_add_entity_type(self, etype, auto=True, commit=True):
        """register a new entity type

        in auto mode, automatically register entity's relation where the
        targeted type is known
        """
        instschema = self.repo.schema
        eschema = self.fs_schema.eschema(etype)
        if etype in instschema and not (eschema.final and eschema.eid is None):
            print 'warning: %s already known, skip addition' % etype
            return
        confirm = self.verbosity >= 2
        groupmap = self.group_mapping()
        cstrtypemap = self.cstrtype_mapping()
        # register the entity into CWEType
        execute = self._cw.execute
        ss.execschemarql(execute, eschema, ss.eschema2rql(eschema, groupmap))
        # add specializes relation if needed
        specialized = eschema.specializes()
        if specialized:
            try:
                specialized.eid = instschema[specialized].eid
            except KeyError:
                raise ExecutionError('trying to add entity type but parent type is '
                                     'not yet in the database schema')
            self.rqlexecall(ss.eschemaspecialize2rql(eschema), ask_confirm=confirm)
        # register entity's attributes
        for rschema, attrschema in eschema.attribute_definitions():
            # ignore those meta relations, they will be automatically added
            if rschema.type in META_RTYPES:
                continue
            if not rschema.type in instschema:
                # need to add the relation type and to commit to get it
                # actually in the schema
                self.cmd_add_relation_type(rschema.type, False, commit=True)
            # register relation definition
            rdef = self._get_rdef(rschema, eschema, eschema.destination(rschema))
            ss.execschemarql(execute, rdef, ss.rdef2rql(rdef, cstrtypemap, groupmap),)
        # take care to newly introduced base class
        # XXX some part of this should probably be under the "if auto" block
        for spschema in eschema.specialized_by(recursive=False):
            try:
                instspschema = instschema[spschema]
            except KeyError:
                # specialized entity type not in schema, ignore
                continue
            if instspschema.specializes() != eschema:
                self.rqlexec('SET D specializes P WHERE D eid %(d)s, P name %(pn)s',
                             {'d': instspschema.eid, 'pn': eschema.type},
                             ask_confirm=confirm)
                for rschema, tschemas, role in spschema.relation_definitions(True):
                    for tschema in tschemas:
                        if not tschema in instschema:
                            continue
                        if role == 'subject':
                            subjschema = spschema
                            objschema = tschema
                            if rschema.final and rschema in instspschema.subjrels:
                                # attribute already set, has_rdef would check if
                                # it's of the same type, we don't want this so
                                # simply skip here
                                continue
                        elif role == 'object':
                            subjschema = tschema
                            objschema = spschema
                        if (rschema.rdef(subjschema, objschema).infered
                            or (instschema.has_relation(rschema) and
                                (subjschema, objschema) in instschema[rschema].rdefs)):
                            continue
                        self.cmd_add_relation_definition(
                            subjschema.type, rschema.type, objschema.type)
        if auto:
            # we have commit here to get relation types actually in the schema
            self.commit()
            added = []
            for rschema in eschema.subject_relations():
                # attribute relation have already been processed and
                # 'owned_by'/'created_by' will be automatically added
                if rschema.final or rschema.type in META_RTYPES:
                    continue
                rtypeadded = rschema.type in instschema
                for targetschema in rschema.objects(etype):
                    # ignore relations where the targeted type is not in the
                    # current instance schema
                    targettype = targetschema.type
                    if not targettype in instschema and targettype != etype:
                        continue
                    if not rtypeadded:
                        # need to add the relation type and to commit to get it
                        # actually in the schema
                        added.append(rschema.type)
                        self.cmd_add_relation_type(rschema.type, False, commit=True)
                        rtypeadded = True
                    # register relation definition
                    # remember this two avoid adding twice non symmetric relation
                    # such as "Emailthread forked_from Emailthread"
                    added.append((etype, rschema.type, targettype))
                    rdef = self._get_rdef(rschema, eschema, targetschema)
                    ss.execschemarql(execute, rdef,
                                     ss.rdef2rql(rdef, cstrtypemap, groupmap))
            for rschema in eschema.object_relations():
                if rschema.type in META_RTYPES:
                    continue
                rtypeadded = rschema.type in instschema or rschema.type in added
                for targetschema in rschema.subjects(etype):
                    # ignore relations where the targeted type is not in the
                    # current instance schema
                    targettype = targetschema.type
                    # don't check targettype != etype since in this case the
                    # relation has already been added as a subject relation
                    if not targettype in instschema:
                        continue
                    if not rtypeadded:
                        # need to add the relation type and to commit to get it
                        # actually in the schema
                        self.cmd_add_relation_type(rschema.type, False, commit=True)
                        rtypeadded = True
                    elif (targettype, rschema.type, etype) in added:
                        continue
                    # register relation definition
                    rdef = self._get_rdef(rschema, targetschema, eschema)
                    ss.execschemarql(execute, rdef,
                                     ss.rdef2rql(rdef, cstrtypemap, groupmap))
        if commit:
            self.commit()

    def cmd_drop_entity_type(self, etype, commit=True):
        """unregister an existing entity type

        This will trigger deletion of necessary relation types and definitions
        """
        # XXX what if we delete an entity type which is specialized by other types
        # unregister the entity from CWEType
        self.rqlexec('DELETE CWEType X WHERE X name %(etype)s', {'etype': etype},
                     ask_confirm=self.verbosity>=2)
        if commit:
            self.commit()

    def cmd_rename_entity_type(self, oldname, newname, attrs=None, commit=True):
        """rename an existing entity type in the persistent schema

        `oldname` is a string giving the name of the existing entity type
        `newname` is a string giving the name of the renamed entity type
        """
        schema = self.repo.schema
        if newname in schema:
            assert oldname in ETYPE_NAME_MAP, \
                   '%s should be mapped to %s in ETYPE_NAME_MAP' % (oldname,
                                                                    newname)
            if attrs is None:
                attrs = ','.join(SQL_PREFIX + rschema.type
                                 for rschema in schema[newname].subject_relations()
                                 if (rschema.final or rschema.inlined)
                                 and not rschema in PURE_VIRTUAL_RTYPES)
            else:
                attrs += ('eid', 'creation_date', 'modification_date', 'cwuri')
                attrs = ','.join(SQL_PREFIX + attr for attr in attrs)
            self.sqlexec('INSERT INTO %s%s(%s) SELECT %s FROM %s%s' % (
                SQL_PREFIX, newname, attrs, attrs, SQL_PREFIX, oldname),
                         ask_confirm=False)
            # old entity type has not been added to the schema, can't gather it
            new = schema.eschema(newname)
            oldeid = self.rqlexec('CWEType ET WHERE ET name %(on)s',
                                  {'on': oldname}, ask_confirm=False)[0][0]
            # backport old type relations to new type
            # XXX workflows, other relations?
            for r1, rr1 in [('from_entity', 'to_entity'),
                            ('to_entity', 'from_entity')]:
                self.rqlexec('SET X %(r1)s NET WHERE X %(r1)s OET, '
                             'NOT EXISTS(X2 %(r1)s NET, X relation_type XRT, '
                             'X2 relation_type XRT, X %(rr1)s XTE, X2 %(rr1)s XTE), '
                             'OET eid %%(o)s, NET eid %%(n)s' % locals(),
                             {'o': oldeid, 'n': new.eid}, ask_confirm=False)
            # backport is / is_instance_of relation to new type
            for rtype in ('is', 'is_instance_of'):
                self.sqlexec('UPDATE %s_relation SET eid_to=%s WHERE eid_to=%s'
                             % (rtype, new.eid, oldeid), ask_confirm=False)
            # delete relations using SQL to avoid relations content removal
            # triggered by schema synchronization hooks.
            session = self.session
            for rdeftype in ('CWRelation', 'CWAttribute'):
                thispending = set( (eid for eid, in self.sqlexec(
                    'SELECT cw_eid FROM cw_%s WHERE cw_from_entity=%%(eid)s OR '
                    ' cw_to_entity=%%(eid)s' % rdeftype,
                    {'eid': oldeid}, ask_confirm=False)) )
                # we should add deleted eids into pending eids else we may
                # get some validation error on commit since integrity hooks
                # may think some required relation is missing... This also ensure
                # repository caches are properly cleanup
                hook.CleanupDeletedEidsCacheOp.get_instance(session).union(thispending)
                # and don't forget to remove record from system tables
                entities = [session.entity_from_eid(eid, rdeftype) for eid in thispending]
                self.repo.system_source.delete_info_multi(session, entities, 'system')
                self.sqlexec('DELETE FROM cw_%s WHERE cw_from_entity=%%(eid)s OR '
                             'cw_to_entity=%%(eid)s' % rdeftype,
                             {'eid': oldeid}, ask_confirm=False)
                # now we have to manually cleanup relations pointing to deleted
                # entities
                thiseids = ','.join(str(eid) for eid in thispending)
                for rschema, ttypes, role in schema[rdeftype].relation_definitions():
                    if rschema.type in VIRTUAL_RTYPES:
                        continue
                    sqls = []
                    if role == 'object':
                        if rschema.inlined:
                            for eschema in ttypes:
                                sqls.append('DELETE FROM cw_%s WHERE cw_%s IN(%%s)'
                                            % (eschema, rschema))
                        else:
                            sqls.append('DELETE FROM %s_relation WHERE eid_to IN(%%s)'
                                        % rschema)
                    elif not rschema.inlined:
                        sqls.append('DELETE FROM %s_relation WHERE eid_from IN(%%s)'
                                    % rschema)
                    for sql in sqls:
                        self.sqlexec(sql % thiseids, ask_confirm=False)
            # remove the old type: use rql to propagate deletion
            self.rqlexec('DELETE CWEType ET WHERE ET name %(on)s', {'on': oldname},
                         ask_confirm=False)
        else:
            self.rqlexec('SET ET name %(newname)s WHERE ET is CWEType, ET name %(on)s',
                         {'newname' : unicode(newname), 'on' : oldname},
                         ask_confirm=False)
        if commit:
            self.commit()

    def cmd_add_relation_type(self, rtype, addrdef=True, commit=True):
        """register a new relation type named `rtype`, as described in the
        schema description file.

        `addrdef` is a boolean value; when True, it will also add all relations
        of the type just added found in the schema definition file. Note that it
        implies an intermediate "commit" which commits the relation type
        creation (but not the relation definitions themselves, for which
        committing depends on the `commit` argument value).

        """
        reposchema = self.repo.schema
        if rtype in reposchema:
            print 'warning: relation type %s is already known, skip addition' % (
                rtype)
            return
        rschema = self.fs_schema.rschema(rtype)
        execute = self._cw.execute
        # register the relation into CWRType and insert necessary relation
        # definitions
        ss.execschemarql(execute, rschema, ss.rschema2rql(rschema, addrdef=False))
        if addrdef:
            self.commit()
            gmap = self.group_mapping()
            cmap = self.cstrtype_mapping()
            done = set()
            for rdef in rschema.rdefs.itervalues():
                if not (reposchema.has_entity(rdef.subject)
                        and reposchema.has_entity(rdef.object)):
                    continue
                # symmetric relations appears twice
                if (rdef.subject, rdef.object) in done:
                    continue
                done.add( (rdef.subject, rdef.object) )
                self._set_rdef_eid(rdef)
                ss.execschemarql(execute, rdef,
                                 ss.rdef2rql(rdef, cmap, gmap))
            if rtype in META_RTYPES:
                # if the relation is in META_RTYPES, ensure we're adding it for
                # all entity types *in the persistent schema*, not only those in
                # the fs schema
                for etype in self.repo.schema.entities():
                    if not etype in self.fs_schema:
                        # get sample object type and rproperties
                        objtypes = rschema.objects()
                        assert len(objtypes) == 1, objtypes
                        objtype = objtypes[0]
                        rdef = copy(rschema.rdef(rschema.subjects(objtype)[0], objtype))
                        rdef.subject = etype
                        rdef.rtype = self.repo.schema.rschema(rschema)
                        rdef.object = self.repo.schema.rschema(objtype)
                        ss.execschemarql(execute, rdef,
                                         ss.rdef2rql(rdef, cmap, gmap))
        if commit:
            self.commit()

    def cmd_drop_relation_type(self, rtype, commit=True):
        """unregister an existing relation type"""
        # unregister the relation from CWRType
        self.rqlexec('DELETE CWRType X WHERE X name %r' % rtype,
                     ask_confirm=self.verbosity>=2)
        if commit:
            self.commit()

    def cmd_rename_relation(self, oldname, newname, commit=True):
        """rename an existing relation

        `oldname` is a string giving the name of the existing relation
        `newname` is a string giving the name of the renamed relation
        """
        self.cmd_add_relation_type(newname, commit=True)
        self.rqlexec('SET X %s Y WHERE X %s Y' % (newname, oldname),
                     ask_confirm=self.verbosity>=2)
        self.cmd_drop_relation_type(oldname, commit=commit)

    def cmd_add_relation_definition(self, subjtype, rtype, objtype, commit=True):
        """register a new relation definition, from its definition found in the
        schema definition file
        """
        rschema = self.fs_schema.rschema(rtype)
        if not rtype in self.repo.schema:
            self.cmd_add_relation_type(rtype, addrdef=False, commit=True)
        if (subjtype, objtype) in self.repo.schema.rschema(rtype).rdefs:
            print 'warning: relation %s %s %s is already known, skip addition' % (
                subjtype, rtype, objtype)
            return
        execute = self._cw.execute
        rdef = self._get_rdef(rschema, subjtype, objtype)
        ss.execschemarql(execute, rdef,
                         ss.rdef2rql(rdef, self.cstrtype_mapping(),
                                     self.group_mapping()))
        if commit:
            self.commit()

    def _get_rdef(self, rschema, subjtype, objtype):
        return self._set_rdef_eid(rschema.rdefs[(subjtype, objtype)])

    def _set_rdef_eid(self, rdef):
        for attr in ('rtype', 'subject', 'object'):
            schemaobj = getattr(rdef, attr)
            if getattr(schemaobj, 'eid', None) is None:
                schemaobj.eid =  self.repo.schema[schemaobj].eid
                assert schemaobj.eid is not None
        return rdef

    def cmd_drop_relation_definition(self, subjtype, rtype, objtype, commit=True):
        """unregister an existing relation definition"""
        rschema = self.repo.schema.rschema(rtype)
        # unregister the definition from CWAttribute or CWRelation
        if rschema.final:
            etype = 'CWAttribute'
        else:
            etype = 'CWRelation'
        rql = ('DELETE %s X WHERE X from_entity FE, FE name "%s",'
               'X relation_type RT, RT name "%s", X to_entity TE, TE name "%s"')
        self.rqlexec(rql % (etype, subjtype, rtype, objtype),
                     ask_confirm=self.verbosity>=2)
        if commit:
            self.commit()

    def cmd_sync_schema_props_perms(self, ertype=None, syncperms=True,
                                    syncprops=True, syncrdefs=True, commit=True):
        """synchronize the persistent schema against the current definition
        schema.

        `ertype` can be :
        - None, in that case everything will be synced ;
        - a string, it should be an entity type or
          a relation type. In that case, only the corresponding
          entities / relations will be synced ;
        - an rdef object to synchronize only this specific relation definition

        It will synch common stuff between the definition schema and the
        actual persistent schema, it won't add/remove any entity or relation.
        """
        assert syncperms or syncprops, 'nothing to do'
        if ertype is not None:
            if isinstance(ertype, RelationDefinitionSchema):
                ertype = ertype.as_triple()
            if isinstance(ertype, (tuple, list)):
                assert len(ertype) == 3, 'not a relation definition'
                self._synchronize_rdef_schema(ertype[0], ertype[1], ertype[2],
                                              syncperms=syncperms,
                                              syncprops=syncprops)
            else:
                erschema = self.repo.schema[ertype]
                if isinstance(erschema, CubicWebRelationSchema):
                    self._synchronize_rschema(erschema, syncrdefs=syncrdefs,
                                              syncperms=syncperms,
                                              syncprops=syncprops)
                else:
                    self._synchronize_eschema(erschema, syncrdefs=syncrdefs,
                                              syncperms=syncperms,
                                              syncprops=syncprops)
        else:
            for etype in self.repo.schema.entities():
                if etype.eid is None:
                     # not yet added final etype (thing to BigInt defined in
                     # yams though 3.13 migration not done yet)
                    continue
                self._synchronize_eschema(etype, syncrdefs=syncrdefs,
                                          syncprops=syncprops, syncperms=syncperms)
        if commit:
            self.commit()

    def cmd_change_relation_props(self, subjtype, rtype, objtype,
                                  commit=True, **kwargs):
        """change some properties of a relation definition

        you usually want to use sync_schema_props_perms instead.
        """
        assert kwargs
        restriction = []
        if subjtype and subjtype != 'Any':
            restriction.append('X from_entity FE, FE name "%s"' % subjtype)
        if objtype and objtype != 'Any':
            restriction.append('X to_entity TE, TE name "%s"' % objtype)
        if rtype and rtype != 'Any':
            restriction.append('X relation_type RT, RT name "%s"' % rtype)
        assert restriction
        values = []
        for k, v in kwargs.items():
            values.append('X %s %%(%s)s' % (k, k))
            if isinstance(v, str):
                kwargs[k] = unicode(v)
        rql = 'SET %s WHERE %s' % (','.join(values), ','.join(restriction))
        self.rqlexec(rql, kwargs, ask_confirm=self.verbosity>=2)
        if commit:
            self.commit()

    def cmd_set_size_constraint(self, etype, rtype, size, commit=True):
        """set change size constraint of a string attribute

        if size is None any size constraint will be removed.

        you usually want to use sync_schema_props_perms instead.
        """
        oldvalue = None
        for constr in self.repo.schema.eschema(etype).rdef(rtype).constraints:
            if isinstance(constr, SizeConstraint):
                oldvalue = constr.max
        if oldvalue == size:
            return
        if oldvalue is None and not size is None:
            ceid = self.rqlexec('INSERT CWConstraint C: C value %(v)s, C cstrtype CT '
                                'WHERE CT name "SizeConstraint"',
                                {'v': SizeConstraint(size).serialize()},
                                ask_confirm=self.verbosity>=2)[0][0]
            self.rqlexec('SET X constrained_by C WHERE X from_entity S, X relation_type R, '
                         'S name "%s", R name "%s", C eid %s' % (etype, rtype, ceid),
                         ask_confirm=self.verbosity>=2)
        elif not oldvalue is None:
            if not size is None:
                self.rqlexec('SET C value %%(v)s WHERE X from_entity S, X relation_type R,'
                             'X constrained_by C, C cstrtype CT, CT name "SizeConstraint",'
                             'S name "%s", R name "%s"' % (etype, rtype),
                             {'v': unicode(SizeConstraint(size).serialize())},
                             ask_confirm=self.verbosity>=2)
            else:
                self.rqlexec('DELETE X constrained_by C WHERE X from_entity S, X relation_type R,'
                             'X constrained_by C, C cstrtype CT, CT name "SizeConstraint",'
                             'S name "%s", R name "%s"' % (etype, rtype),
                             ask_confirm=self.verbosity>=2)
                # cleanup unused constraints
                self.rqlexec('DELETE CWConstraint C WHERE NOT X constrained_by C')
        if commit:
            self.commit()

    @deprecated('[3.2] use sync_schema_props_perms(ertype, syncprops=False)')
    def cmd_synchronize_permissions(self, ertype, commit=True):
        self.cmd_sync_schema_props_perms(ertype, syncprops=False, commit=commit)

    # Workflows handling ######################################################

    def cmd_make_workflowable(self, etype):
        """add workflow relations to an entity type to make it workflowable"""
        self.cmd_add_relation_definition(etype, 'in_state', 'State')
        self.cmd_add_relation_definition(etype, 'custom_workflow', 'Workflow')
        self.cmd_add_relation_definition('TrInfo', 'wf_info_for', etype)

    def cmd_add_workflow(self, name, wfof, default=True, commit=False,
                         ensure_workflowable=True, **kwargs):
        """
        create a new workflow and links it to entity types
         :type name: unicode
         :param name: name of the workflow

         :type wfof: string or list/tuple of strings
         :param wfof: entity type(s) having this workflow

         :type default: bool
         :param default: tells wether this is the default workflow
                   for the specified entity type(s); set it to false in
                   the case of a subworkflow

         :rtype: `Workflow`
        """
        wf = self.cmd_create_entity('Workflow', name=unicode(name),
                                    **kwargs)
        if not isinstance(wfof, (list, tuple)):
            wfof = (wfof,)
        def _missing_wf_rel(etype):
            return 'missing workflow relations, see make_workflowable(%s)' % etype
        for etype in wfof:
            eschema = self.repo.schema[etype]
            if ensure_workflowable:
                assert 'in_state' in eschema.subjrels, _missing_wf_rel(etype)
                assert 'custom_workflow' in eschema.subjrels, _missing_wf_rel(etype)
                assert 'wf_info_for' in eschema.objrels, _missing_wf_rel(etype)
            rset = self.rqlexec(
                'SET X workflow_of ET WHERE X eid %(x)s, ET name %(et)s',
                {'x': wf.eid, 'et': etype}, ask_confirm=False)
            assert rset, 'unexistant entity type %s' % etype
            if default:
                self.rqlexec(
                    'SET ET default_workflow X WHERE X eid %(x)s, ET name %(et)s',
                    {'x': wf.eid, 'et': etype}, ask_confirm=False)
        if commit:
            self.commit()
        return wf

    def cmd_get_workflow_for(self, etype):
        """return default workflow for the given entity type"""
        rset = self.rqlexec('Workflow X WHERE ET default_workflow X, ET name %(et)s',
                            {'et': etype})
        return rset.get_entity(0, 0)

    # XXX remove once cmd_add_[state|transition] are removed
    def _get_or_create_wf(self, etypes):
        if not isinstance(etypes, (list, tuple)):
            etypes = (etypes,)
        rset = self.rqlexec('Workflow X WHERE X workflow_of ET, ET name %(et)s',
                            {'et': etypes[0]})
        if rset:
            return rset.get_entity(0, 0)
        return self.cmd_add_workflow('%s workflow' % ';'.join(etypes), etypes)

    @deprecated('[3.5] use add_workflow and Workflow.add_state method',
                stacklevel=3)
    def cmd_add_state(self, name, stateof, initial=False, commit=False, **kwargs):
        """method to ease workflow definition: add a state for one or more
        entity type(s)
        """
        wf = self._get_or_create_wf(stateof)
        state = wf.add_state(name, initial, **kwargs)
        if commit:
            self.commit()
        return state.eid

    @deprecated('[3.5] use add_workflow and Workflow.add_transition method',
                stacklevel=3)
    def cmd_add_transition(self, name, transitionof, fromstates, tostate,
                           requiredgroups=(), conditions=(), commit=False, **kwargs):
        """method to ease workflow definition: add a transition for one or more
        entity type(s), from one or more state and to a single state
        """
        wf = self._get_or_create_wf(transitionof)
        tr = wf.add_transition(name, fromstates, tostate, requiredgroups,
                               conditions, **kwargs)
        if commit:
            self.commit()
        return tr.eid

    @deprecated('[3.5] use Transition.set_transition_permissions method',
                stacklevel=3)
    def cmd_set_transition_permissions(self, treid,
                                       requiredgroups=(), conditions=(),
                                       reset=True, commit=False):
        """set or add (if `reset` is False) groups and conditions for a
        transition
        """
        tr = self._cw.entity_from_eid(treid)
        tr.set_transition_permissions(requiredgroups, conditions, reset)
        if commit:
            self.commit()

    @deprecated('[3.5] use iworkflowable.fire_transition("transition") or '
                'iworkflowable.change_state("state")', stacklevel=3)
    def cmd_set_state(self, eid, statename, commit=False):
        self._cw.entity_from_eid(eid).cw_adapt_to('IWorkflowable').change_state(statename)
        if commit:
            self.commit()

    # CWProperty handling ######################################################

    def cmd_property_value(self, pkey):
        """retreive the site-wide persistent property value for the given key.

        To get a user specific property value, use appropriate method on CWUser
        instance.
        """
        rset = self.rqlexec(
            'Any V WHERE X is CWProperty, X pkey %(k)s, X value V, NOT X for_user U',
            {'k': pkey}, ask_confirm=False)
        return rset[0][0]

    def cmd_set_property(self, pkey, value):
        """set the site-wide persistent property value for the given key to the
        given value.

        To set a user specific property value, use appropriate method on CWUser
        instance.
        """
        value = unicode(value)
        try:
            prop = self.rqlexec(
                'CWProperty X WHERE X pkey %(k)s, NOT X for_user U',
                {'k': pkey}, ask_confirm=False).get_entity(0, 0)
        except Exception:
            self.cmd_create_entity('CWProperty', pkey=unicode(pkey), value=value)
        else:
            prop.set_attributes(value=value)

    # other data migration commands ###########################################

    @property
    def _cw(self):
        session = self.session
        if session is not None:
            session.set_cnxset()
            return session
        return self.cnx.request()

    def cmd_storage_changed(self, etype, attribute):
        """migrate entities to a custom storage. The new storage is expected to
        be set, it will be temporarily removed for the migration.
        """
        from logilab.common.shellutils import ProgressBar
        source = self.repo.system_source
        storage = source.storage(etype, attribute)
        source.unset_storage(etype, attribute)
        rset = self.rqlexec('Any X WHERE X is %s' % etype, ask_confirm=False)
        pb = ProgressBar(len(rset))
        for entity in rset.entities():
            # fill cache. Do not fetch that attribute using the global rql query
            # since we may exhaust memory doing that....
            getattr(entity, attribute)
            storage.migrate_entity(entity, attribute)
            # remove from entity cache to avoid memory exhaustion
            del entity[attribute]
            pb.update()
        print
        source.set_storage(etype, attribute, storage)

    def cmd_create_entity(self, etype, commit=False, **kwargs):
        """add a new entity of the given type"""
        entity = self._cw.create_entity(etype, **kwargs)
        if commit:
            self.commit()
        return entity

    def cmd_find_entities(self, etype, **kwargs):
        """find entities of the given type and attribute values"""
        return self._cw.find_entities(etype, **kwargs)

    def cmd_find_one_entity(self, etype, **kwargs):
        """find one entity of the given type and attribute values.

        raise :exc:`cubicweb.req.FindEntityError` if can not return one and only
        one entity.
        """
        return self._cw.find_one_entity(etype, **kwargs)

    def cmd_update_etype_fti_weight(self, etype, weight):
        if self.repo.system_source.dbdriver == 'postgres':
            self.sqlexec('UPDATE appears SET weight=%(weight)s '
                         'FROM entities as X '
                         'WHERE X.eid=appears.uid AND X.type=%(type)s',
                         {'type': etype, 'weight': weight}, ask_confirm=False)

    def cmd_reindex_entities(self, etypes=None):
        """force reindexaction of entities of the given types or of all
        indexable entity types
        """
        from cubicweb.server.checkintegrity import reindex_entities
        reindex_entities(self.repo.schema, self.session, etypes=etypes)

    @deprecated('[3.5] use create_entity', stacklevel=3)
    def cmd_add_entity(self, etype, *args, **kwargs):
        """add a new entity of the given type"""
        return self.cmd_create_entity(etype, *args, **kwargs).eid

    @contextmanager
    def cmd_dropped_constraints(self, etype, attrname, cstrtype=None,
                                droprequired=False):
        """context manager to drop constraints temporarily on fs_schema

        `cstrtype` should be a constraint class (or a tuple of classes)
        and will be passed to isinstance directly

        For instance::

            >>> with dropped_constraints('MyType', 'myattr',
            ...                          UniqueConstraint, droprequired=True):
            ...     add_attribute('MyType', 'myattr')
            ...     # + instructions to fill MyType.myattr column
            ...
            >>>

        """
        rdef = self.fs_schema.eschema(etype).rdef(attrname)
        original_constraints = rdef.constraints
        # remove constraints
        if cstrtype:
            rdef.constraints = [cstr for cstr in original_constraints
                                if not (cstrtype and isinstance(cstr, cstrtype))]
        if droprequired:
            original_cardinality = rdef.cardinality
            rdef.cardinality = '?' + rdef.cardinality[1]
        yield
        # restore original constraints
        rdef.constraints = original_constraints
        if droprequired:
            rdef.cardinality = original_cardinality
        # update repository schema
        self.cmd_sync_schema_props_perms(rdef, syncperms=False)

    def sqlexec(self, sql, args=None, ask_confirm=True):
        """execute the given sql if confirmed

        should only be used for low level stuff undoable with existing higher
        level actions
        """
        if not ask_confirm or self.confirm('Execute sql: %s ?' % sql):
            try:
                cu = self.session.system_sql(sql, args)
            except Exception:
                ex = sys.exc_info()[1]
                if self.confirm('Error: %s\nabort?' % ex, pdb=True):
                    raise
                return
            try:
                return cu.fetchall()
            except Exception:
                # no result to fetch
                return

    def rqlexec(self, rql, kwargs=None, cachekey=None, build_descr=True,
                ask_confirm=False):
        """rql action"""
        if cachekey is not None:
            warn('[3.8] cachekey is deprecated, you can safely remove this argument',
                 DeprecationWarning, stacklevel=2)
        if not isinstance(rql, (tuple, list)):
            rql = ( (rql, kwargs), )
        res = None
        execute = self._cw.execute
        for rql, kwargs in rql:
            if kwargs:
                msg = '%s (%s)' % (rql, kwargs)
            else:
                msg = rql
            if not ask_confirm or self.confirm('Execute rql: %s ?' % msg):
                try:
                    res = execute(rql, kwargs, build_descr=build_descr)
                except Exception, ex:
                    if self.confirm('Error: %s\nabort?' % ex, pdb=True):
                        raise
        return res

    def rqliter(self, rql, kwargs=None, ask_confirm=True):
        return ForRqlIterator(self, rql, kwargs, ask_confirm)

    # broken db commands ######################################################

    def cmd_change_attribute_type(self, etype, attr, newtype, commit=True):
        """low level method to change the type of an entity attribute. This is
        a quick hack which has some drawback:
        * only works when the old type can be changed to the new type by the
          underlying rdbms (eg using ALTER TABLE)
        * the actual schema won't be updated until next startup
        """
        rschema = self.repo.schema.rschema(attr)
        oldtype = rschema.objects(etype)[0]
        rdefeid = rschema.rproperty(etype, oldtype, 'eid')
        sql = ("UPDATE cw_CWAttribute "
               "SET cw_to_entity=(SELECT cw_eid FROM cw_CWEType WHERE cw_name='%s')"
               "WHERE cw_eid=%s") % (newtype, rdefeid)
        self.sqlexec(sql, ask_confirm=False)
        dbhelper = self.repo.system_source.dbhelper
        sqltype = dbhelper.TYPE_MAPPING[newtype]
        sql = 'ALTER TABLE cw_%s ALTER COLUMN cw_%s TYPE %s' % (etype, attr, sqltype)
        self.sqlexec(sql, ask_confirm=False)
        if commit:
            self.commit()

    def cmd_add_entity_type_table(self, etype, commit=True):
        """low level method to create the sql table for an existing entity.
        This may be useful on accidental desync between the repository schema
        and a sql database
        """
        dbhelper = self.repo.system_source.dbhelper
        tablesql = eschema2sql(dbhelper, self.repo.schema.eschema(etype),
                               prefix=SQL_PREFIX)
        for sql in tablesql.split(';'):
            if sql.strip():
                self.sqlexec(sql)
        if commit:
            self.commit()

    def cmd_add_relation_type_table(self, rtype, commit=True):
        """low level method to create the sql table for an existing relation.
        This may be useful on accidental desync between the repository schema
        and a sql database
        """
        tablesql = rschema2sql(self.repo.schema.rschema(rtype))
        for sql in tablesql.split(';'):
            if sql.strip():
                self.sqlexec(sql)
        if commit:
            self.commit()

    @deprecated("[3.7] use session.disable_hook_categories('integrity')")
    def cmd_deactivate_verification_hooks(self):
        self.session.disable_hook_categories('integrity')

    @deprecated("[3.7] use session.enable_hook_categories('integrity')")
    def cmd_reactivate_verification_hooks(self):
        self.session.enable_hook_categories('integrity')


class ForRqlIterator:
    """specific rql iterator to make the loop skipable"""
    def __init__(self, helper, rql, kwargs, ask_confirm):
        self._h = helper
        self.rql = rql
        self.kwargs = kwargs
        self.ask_confirm = ask_confirm
        self._rsetit = None

    def __iter__(self):
        return self

    def _get_rset(self):
        rql, kwargs = self.rql, self.kwargs
        if kwargs:
            msg = '%s (%s)' % (rql, kwargs)
        else:
            msg = rql
        if self.ask_confirm:
            if not self._h.confirm('Execute rql: %s ?' % msg):
                raise StopIteration
        try:
            return self._h._cw.execute(rql, kwargs)
        except Exception, ex:
            if self._h.confirm('Error: %s\nabort?' % ex):
                raise
            else:
                raise StopIteration

    def next(self):
        if self._rsetit is not None:
            return self._rsetit.next()
        rset = self._get_rset()
        self._rsetit = iter(rset)
        return self._rsetit.next()

    def entities(self):
        try:
            rset = self._get_rset()
        except StopIteration:
            return []
        return rset.entities()
