"""a class implementing basic actions used in migration scripts.

The following schema actions are supported for now:
* add/drop/rename attribute
* add/drop entity/relation type
* rename entity type

The following data actions are supported for now:
* add an entity
* execute raw RQL queries


:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

import sys
import os
from os.path import join, exists

from mx.DateTime import now
from logilab.common.decorators import cached
from logilab.common.adbh import get_adv_func_helper

from yams.constraints import SizeConstraint
from yams.schema2sql import eschema2sql, rschema2sql

from cubicweb import AuthenticationError
from cubicweb.dbapi import get_repository, repo_connect
from cubicweb.common.migration import MigrationHelper, yes

try:
    from cubicweb.server import schemaserial as ss
    from cubicweb.server.utils import manager_userpasswd
    from cubicweb.server.sqlutils import sqlexec
except ImportError: # LAX
    pass

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
        if not schema:
            schema = config.load_schema(expand_cubes=True)
        self.fs_schema = schema
        self._synchronized = set()

    @cached
    def repo_connect(self):
        self.repo = get_repository(method='inmemory', config=self.config)
        return self.repo
    
    def shutdown(self):
        if self.repo is not None:
            self.repo.shutdown()
        
    def rewrite_vcconfiguration(self):
        """write current installed versions (of cubicweb software
        and of each used cube) into the database
        """
        self.cmd_set_property('system.version.cubicweb', self.config.cubicweb_version())
        for pkg in self.config.cubes():
            pkgversion = self.config.cube_version(pkg)
            self.cmd_set_property('system.version.%s' % pkg.lower(), pkgversion)
        self.commit()
        
    def backup_database(self, backupfile=None, askconfirm=True):
        config = self.config
        source = config.sources()['system']
        helper = get_adv_func_helper(source['db-driver'])
        date = now().strftime('%Y-%m-%d_%H:%M:%S')
        app = config.appid
        backupfile = backupfile or join(config.backup_dir(),
                                        '%s-%s.dump' % (app, date))
        if exists(backupfile):
            if not self.confirm('a backup already exists for %s, overwrite it?' % app):
                return
        elif askconfirm and not self.confirm('backup %s database?' % app):
            return
        cmd = helper.backup_command(source['db-name'], source.get('db-host'),
                                    source.get('db-user'), backupfile,
                                    keepownership=False)
        while True:
            print cmd
            if os.system(cmd):
                print 'error while backuping the base'
                answer = self.confirm('continue anyway?',
                                      shell=False, abort=False, retry=True)
                if not answer:
                    raise SystemExit(1)
                if answer == 1: # 1: continue, 2: retry
                    break
            else:
                from cubicweb.toolsutils import restrict_perms_to_user
                print 'database backup:', backupfile
                restrict_perms_to_user(backupfile, self.info)
                break
        
    def restore_database(self, backupfile, drop=True):
        config = self.config
        source = config.sources()['system']
        helper = get_adv_func_helper(source['db-driver'])
        app = config.appid
        if not exists(backupfile):
            raise Exception("backup file %s doesn't exist" % backupfile)
        if self.confirm('restore %s database from %s ?' % (app, backupfile)):
            for cmd in helper.restore_commands(source['db-name'], source.get('db-host'),
                                               source.get('db-user'), backupfile,
                                               source['db-encoding'],
                                               keepownership=False, drop=drop):
                while True:
                    print cmd
                    if os.system(cmd):
                        print 'error while restoring the base'
                        answer = self.confirm('continue anyway?',
                                              shell=False, abort=False, retry=True)
                        if not answer:
                            raise SystemExit(1)
                        if answer == 1: # 1: continue, 2: retry
                            break
                    else:
                        break
            print 'database restored'
        
    def migrate(self, vcconf, toupgrade, options):
        if not options.fs_only:
            if options.backup_db is None:
                self.backup_database()
            elif options.backup_db:
                self.backup_database(askconfirm=False)
        super(ServerMigrationHelper, self).migrate(vcconf, toupgrade, options)
    
    def process_script(self, migrscript, funcname=None, *args, **kwargs):
        """execute a migration script
        in interactive mode,  display the migration script path, ask for
        confirmation and execute it if confirmed
        """
        if migrscript.endswith('.sql'):
            if self.execscript_confirm(migrscript):
                sqlexec(open(migrscript).read(), self.session.system_sql)
        else:
            return super(ServerMigrationHelper, self).process_script(
                migrscript, funcname, *args, **kwargs)
        
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
                    self._cnx = repo_connect(self.repo, login, pwd)
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
            return self._cnx

    @property
    def session(self):
        return self.repo._get_session(self.cnx.sessionid)
    
    @property
    @cached
    def rqlcursor(self):
        """lazy rql cursor"""
        # should not give session as cnx.cursor(), else we may try to execute
        # some query while no pool is set on the session (eg on entity attribute
        # access for instance)
        return self.cnx.cursor()
    
    def commit(self):
        if hasattr(self, '_cnx'):
            self._cnx.commit()
            
    def rollback(self):
        if hasattr(self, '_cnx'):
            self._cnx.rollback()
                   
    def rqlexecall(self, rqliter, cachekey=None, ask_confirm=True):
        for rql, kwargs in rqliter:
            self.rqlexec(rql, kwargs, cachekey, ask_confirm)

    @cached
    def _create_context(self):
        """return a dictionary to use as migration script execution context"""
        context = super(ServerMigrationHelper, self)._create_context()
        context.update({'checkpoint': self.checkpoint,
                        'sql': self.sqlexec,
                        'rql': self.rqlexec,
                        'rqliter': self.rqliter,
                        'schema': self.repo.schema,
                        # XXX deprecate
                        'newschema': self.fs_schema,
                        'fsschema': self.fs_schema,
                        'cnx': self.cnx,
                        'session' : self.session,
                        'repo' : self.repo,
                        })
        return context

    @cached
    def group_mapping(self):
        """cached group mapping"""
        return ss.group_mapping(self.rqlcursor)
        
    def exec_event_script(self, event, cubepath=None, funcname=None,
                          *args, **kwargs):            
        if cubepath:
            apc = join(cubepath, 'migration', '%s.py' % event)
        else:
            apc = join(self.config.migration_scripts_dir(), '%s.py' % event)
        if exists(apc):
            if self.config.free_wheel:
                from cubicweb.server.hooks import setowner_after_add_entity
                self.repo.hm.unregister_hook(setowner_after_add_entity,
                                             'after_add_entity', '')
                self.deactivate_verification_hooks()
            self.info('executing %s', apc)
            confirm = self.confirm
            execscript_confirm = self.execscript_confirm
            self.confirm = yes
            self.execscript_confirm = yes
            try:
                return self.process_script(apc, funcname, *args, **kwargs)
            finally:
                self.confirm = confirm
                self.execscript_confirm = execscript_confirm
                if self.config.free_wheel:
                    self.repo.hm.register_hook(setowner_after_add_entity,
                                               'after_add_entity', '')
                    self.reactivate_verification_hooks()
    
    # base actions ############################################################

    def checkpoint(self):
        """checkpoint action"""
        if self.confirm('commit now ?', shell=False):
            self.commit()

    def cmd_add_cube(self, cube, update_database=True):
        self.cmd_add_cubes( (cube,), update_database)
    
    def cmd_add_cubes(self, cubes, update_database=True):
        """update_database is telling if the database schema should be updated
        or if only the relevant eproperty should be inserted (for the case where
        a cube has been extracted from an existing application, so the
        cube schema is already in there)
        """
        newcubes = super(ServerMigrationHelper, self).cmd_add_cubes(cubes)
        if not newcubes:
            return
        for pack in newcubes:
            self.cmd_set_property('system.version.'+pack,
                                  self.config.cube_version(pack))
        if not update_database:
            self.commit()
            return
        newcubes_schema = self.config.load_schema()
        new = set()
        # execute pre-create files
        for pack in reversed(newcubes):
            self.exec_event_script('precreate', self.config.cube_dir(pack))
        # add new entity and relation types
        for rschema in newcubes_schema.relations():
            if not rschema in self.repo.schema:
                self.cmd_add_relation_type(rschema.type)
                new.add(rschema.type)
        for eschema in newcubes_schema.entities():
            if not eschema in self.repo.schema:
                self.cmd_add_entity_type(eschema.type)
                new.add(eschema.type)
        # check if attributes has been added to existing entities
        for rschema in newcubes_schema.relations():
            existingschema = self.repo.schema.rschema(rschema.type)
            for (fromtype, totype) in rschema.iter_rdefs():
                if existingschema.has_rdef(fromtype, totype):
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
                
    def cmd_remove_cube(self, cube):
        removedcubes = super(ServerMigrationHelper, self).cmd_remove_cube(cube)
        if not removedcubes:
            return
        fsschema = self.fs_schema
        removedcubes_schema = self.config.load_schema()
        reposchema = self.repo.schema
        # execute pre-remove files
        for pack in reversed(removedcubes):
            self.exec_event_script('preremove', self.config.cube_dir(pack))
        # remove cubes'entity and relation types
        for rschema in fsschema.relations():
            if not rschema in removedcubes_schema and rschema in reposchema:
                self.cmd_drop_relation_type(rschema.type)
        for eschema in fsschema.entities():
            if not eschema in removedcubes_schema and eschema in reposchema:
                self.cmd_drop_entity_type(eschema.type)
        for rschema in fsschema.relations():
            if rschema in removedcubes_schema and rschema in reposchema: 
                # check if attributes/relations has been added to entities from 
                # other cubes
                for fromtype, totype in rschema.iter_rdefs():
                    if not removedcubes_schema[rschema.type].has_rdef(fromtype, totype) and \
                           reposchema[rschema.type].has_rdef(fromtype, totype):
                        self.cmd_drop_relation_definition(
                            str(fromtype), rschema.type, str(totype))
        # execute post-remove files
        for pack in reversed(removedcubes):
            self.exec_event_script('postremove', self.config.cube_dir(pack))
            self.rqlexec('DELETE EProperty X WHERE X pkey %(pk)s',
                         {'pk': u'system.version.'+pack}, ask_confirm=False)
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
        rschema = self.repo.schema.rschema(attrname)
        attrtype = rschema.objects(etype)[0]
        self.cmd_drop_relation_definition(etype, attrname, attrtype, commit=commit)

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
        card = eschema.rproperty(newname, 'cardinality')[0]
        if card == '1':
            rql += ', NOT X %s NULL' % oldname
        self.rqlexec(rql, ask_confirm=self.verbosity>=2)
        self.cmd_drop_attribute(etype, oldname, commit=commit)
            
    def cmd_add_entity_type(self, etype, auto=True, commit=True):
        """register a new entity type
        
        in auto mode, automatically register entity's relation where the
        targeted type is known
        """
        applschema = self.repo.schema
        if etype in applschema:
            eschema = applschema[etype]
            if eschema.is_final():
                applschema.del_entity_type(etype)
        else:
            eschema = self.fs_schema.eschema(etype)
        confirm = self.verbosity >= 2
        # register the entity into EEType
        self.rqlexecall(ss.eschema2rql(eschema), ask_confirm=confirm)
        # add specializes relation if needed
        self.rqlexecall(ss.eschemaspecialize2rql(eschema), ask_confirm=confirm)
        # register groups / permissions for the entity
        self.rqlexecall(ss.erperms2rql(eschema, self.group_mapping()),
                        ask_confirm=confirm)
        # register entity's attributes
        for rschema, attrschema in eschema.attribute_definitions():
            # ignore those meta relations, they will be automatically added
            if rschema.type in ('eid', 'creation_date', 'modification_date'):
                continue
            if not rschema.type in applschema:
                # need to add the relation type and to commit to get it
                # actually in the schema
                self.cmd_add_relation_type(rschema.type, False, commit=True)
            # register relation definition
            self.rqlexecall(ss.rdef2rql(rschema, etype, attrschema.type),
                            ask_confirm=confirm)
        if auto:
            # we have commit here to get relation types actually in the schema
            self.commit()
            added = []
            for rschema in eschema.subject_relations():
                # attribute relation have already been processed and
                # 'owned_by'/'created_by' will be automatically added
                if rschema.final or rschema.type in ('owned_by', 'created_by', 'is', 'is_instance_of'): 
                    continue
                rtypeadded = rschema.type in applschema
                for targetschema in rschema.objects(etype):
                    # ignore relations where the targeted type is not in the
                    # current application schema
                    targettype = targetschema.type
                    if not targettype in applschema and targettype != etype:
                        continue
                    if not rtypeadded:
                        # need to add the relation type and to commit to get it
                        # actually in the schema
                        added.append(rschema.type)
                        self.cmd_add_relation_type(rschema.type, False, commit=True)
                        rtypeadded = True
                    # register relation definition
                    # remember this two avoid adding twice non symetric relation
                    # such as "Emailthread forked_from Emailthread"
                    added.append((etype, rschema.type, targettype))
                    self.rqlexecall(ss.rdef2rql(rschema, etype, targettype),
                                    ask_confirm=confirm)
            for rschema in eschema.object_relations():
                rtypeadded = rschema.type in applschema or rschema.type in added
                for targetschema in rschema.subjects(etype):
                    # ignore relations where the targeted type is not in the
                    # current application schema
                    targettype = targetschema.type
                    # don't check targettype != etype since in this case the
                    # relation has already been added as a subject relation
                    if not targettype in applschema:
                        continue
                    if not rtypeadded:
                        # need to add the relation type and to commit to get it
                        # actually in the schema
                        self.cmd_add_relation_type(rschema.type, False, commit=True)
                        rtypeadded = True
                    elif (targettype, rschema.type, etype) in added:
                        continue
                    # register relation definition
                    self.rqlexecall(ss.rdef2rql(rschema, targettype, etype),
                                    ask_confirm=confirm)
        if commit:
            self.commit()
                
    def cmd_drop_entity_type(self, etype, commit=True):
        """unregister an existing entity type
        
        This will trigger deletion of necessary relation types and definitions
        """
        # XXX what if we delete an entity type which is specialized by other types
        # unregister the entity from EEType
        self.rqlexec('DELETE EEType X WHERE X name %(etype)s', {'etype': etype},
                     ask_confirm=self.verbosity>=2)
        if commit:
            self.commit()

    def cmd_rename_entity_type(self, oldname, newname, commit=True):
        """rename an existing entity type in the persistent schema
        
        `oldname` is a string giving the name of the existing entity type
        `newname` is a string giving the name of the renamed entity type
        """
        self.rqlexec('SET ET name %(newname)s WHERE ET is EEType, ET name %(oldname)s',
                     {'newname' : unicode(newname), 'oldname' : oldname})
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
        rschema = self.fs_schema.rschema(rtype)
        # register the relation into ERType and insert necessary relation
        # definitions
        self.rqlexecall(ss.rschema2rql(rschema, addrdef=False),
                        ask_confirm=self.verbosity>=2)
        # register groups / permissions for the relation
        self.rqlexecall(ss.erperms2rql(rschema, self.group_mapping()),
                        ask_confirm=self.verbosity>=2)
        if addrdef:
            self.commit()
            self.rqlexecall(ss.rdef2rql(rschema),
                            ask_confirm=self.verbosity>=2)
        if commit:
            self.commit()
        
    def cmd_drop_relation_type(self, rtype, commit=True):
        """unregister an existing relation type"""
        # unregister the relation from ERType
        self.rqlexec('DELETE ERType X WHERE X name %r' % rtype,
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
        self.rqlexecall(ss.rdef2rql(rschema, subjtype, objtype),
                        ask_confirm=self.verbosity>=2)
        if commit:
            self.commit()
        
    def cmd_drop_relation_definition(self, subjtype, rtype, objtype, commit=True):
        """unregister an existing relation definition"""
        rschema = self.repo.schema.rschema(rtype)
        # unregister the definition from EFRDef or ENFRDef
        if rschema.is_final():
            etype = 'EFRDef'
        else:
            etype = 'ENFRDef'
        rql = ('DELETE %s X WHERE X from_entity FE, FE name "%s",'
               'X relation_type RT, RT name "%s", X to_entity TE, TE name "%s"')
        self.rqlexec(rql % (etype, subjtype, rtype, objtype),
                     ask_confirm=self.verbosity>=2)
        if commit:
            self.commit()
        
    def cmd_synchronize_permissions(self, ertype, commit=True):
        """permission synchronization for an entity or relation type"""
        if ertype in ('eid', 'has_text', 'identity'):
            return
        newrschema = self.fs_schema[ertype]
        teid = self.repo.schema[ertype].eid
        if 'update' in newrschema.ACTIONS or newrschema.is_final():
            # entity type
            exprtype = u'ERQLExpression'
        else:
            # relation type
            exprtype = u'RRQLExpression'
        assert teid, ertype
        gm = self.group_mapping()
        confirm = self.verbosity >= 2
        # * remove possibly deprecated permission (eg in the persistent schema
        #   but not in the new schema)
        # * synchronize existing expressions
        # * add new groups/expressions
        for action in newrschema.ACTIONS:
            perm = '%s_permission' % action
            # handle groups
            newgroups = list(newrschema.get_groups(action))
            for geid, gname in self.rqlexec('Any G, GN WHERE T %s G, G name GN, '
                                            'T eid %%(x)s' % perm, {'x': teid}, 'x',
                                            ask_confirm=False):
                if not gname in newgroups:
                    if not confirm or self.confirm('remove %s permission of %s to %s?'
                                                   % (action, ertype, gname)):
                        self.rqlexec('DELETE T %s G WHERE G eid %%(x)s, T eid %s'
                                     % (perm, teid),
                                     {'x': geid}, 'x', ask_confirm=False)
                else:
                    newgroups.remove(gname)
            for gname in newgroups:
                if not confirm or self.confirm('grant %s permission of %s to %s?'
                                               % (action, ertype, gname)):
                    self.rqlexec('SET T %s G WHERE G eid %%(x)s, T eid %s'
                                 % (perm, teid),
                                 {'x': gm[gname]}, 'x', ask_confirm=False)
            # handle rql expressions
            newexprs = dict((expr.expression, expr) for expr in newrschema.get_rqlexprs(action))
            for expreid, expression in self.rqlexec('Any E, EX WHERE T %s E, E expression EX, '
                                                    'T eid %s' % (perm, teid),
                                                    ask_confirm=False):
                if not expression in newexprs:
                    if not confirm or self.confirm('remove %s expression for %s permission of %s?'
                                                   % (expression, action, ertype)):
                        # deleting the relation will delete the expression entity
                        self.rqlexec('DELETE T %s E WHERE E eid %%(x)s, T eid %s'
                                     % (perm, teid),
                                     {'x': expreid}, 'x', ask_confirm=False)
                else:
                    newexprs.pop(expression)
            for expression in newexprs.values():
                expr = expression.expression
                if not confirm or self.confirm('add %s expression for %s permission of %s?'
                                               % (expr, action, ertype)):
                    self.rqlexec('INSERT RQLExpression X: X exprtype %%(exprtype)s, '
                                 'X expression %%(expr)s, X mainvars %%(vars)s, T %s X '
                                 'WHERE T eid %%(x)s' % perm,
                                 {'expr': expr, 'exprtype': exprtype,
                                  'vars': expression.mainvars, 'x': teid}, 'x',
                                 ask_confirm=False)
        if commit:
            self.commit()
        
    def cmd_synchronize_rschema(self, rtype, syncrdefs=True, syncperms=True,
                                commit=True):
        """synchronize properties of the persistent relation schema against its
        current definition:
        
        * description
        * symetric, meta
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
        self.rqlexecall(ss.updaterschema2rql(rschema),
                        ask_confirm=self.verbosity>=2)
        reporschema = self.repo.schema.rschema(rtype)
        if syncrdefs:
            for subj, obj in rschema.iter_rdefs():
                if not reporschema.has_rdef(subj, obj):
                    continue
                self.cmd_synchronize_rdef_schema(subj, rschema, obj,
                                                 commit=False)
        if syncperms:
            self.cmd_synchronize_permissions(rtype, commit=False)
        if commit:
            self.commit()
                
    def cmd_synchronize_eschema(self, etype, syncperms=True, commit=True):
        """synchronize properties of the persistent entity schema against
        its current definition:
        
        * description
        * internationalizable, fulltextindexed, indexed, meta
        * relations from/to this entity
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
            return
        repospschema = repoeschema.specializes()
        espschema = eschema.specializes()
        if repospschema and not espschema:
            self.rqlexec('DELETE X specializes Y WHERE X is EEType, X name %(x)s',
                         {'x': str(repoeschema)})
        elif not repospschema and espschema:
            self.rqlexec('SET X specializes Y WHERE X is EEType, X name %(x)s, '
                         'Y is EEType, Y name %(y)s',
                         {'x': str(repoeschema), 'y': str(espschema)})
        self.rqlexecall(ss.updateeschema2rql(eschema),
                        ask_confirm=self.verbosity >= 2)
        for rschema, targettypes, x in eschema.relation_definitions(True):
            if x == 'subject':
                if not rschema in repoeschema.subject_relations():
                    continue
                subjtypes, objtypes = [etype], targettypes
            else: # x == 'object'
                if not rschema in repoeschema.object_relations():
                    continue
                subjtypes, objtypes = targettypes, [etype]
            self.cmd_synchronize_rschema(rschema, syncperms=syncperms,
                                         syncrdefs=False, commit=False)
            reporschema = self.repo.schema.rschema(rschema)
            for subj in subjtypes:
                for obj in objtypes:
                    if not reporschema.has_rdef(subj, obj):
                        continue
                    self.cmd_synchronize_rdef_schema(subj, rschema, obj,
                                                     commit=False)
        if syncperms:
            self.cmd_synchronize_permissions(etype, commit=False)
        if commit:
            self.commit()

    def cmd_synchronize_rdef_schema(self, subjtype, rtype, objtype,
                                    commit=True):
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
        if rschema.symetric:
            self._synchronized.add((objtype, rschema, subjtype))
        confirm = self.verbosity >= 2
        # properties
        self.rqlexecall(ss.updaterdef2rql(rschema, subjtype, objtype),
                        ask_confirm=confirm)
        # constraints
        newconstraints = list(rschema.rproperty(subjtype, objtype, 'constraints'))
        # 1. remove old constraints and update constraints of the same type
        # NOTE: don't use rschema.constraint_by_type because it may be
        #       out of sync with newconstraints when multiple
        #       constraints of the same type are used
        for cstr in reporschema.rproperty(subjtype, objtype, 'constraints'):
            for newcstr in newconstraints:
                if newcstr.type() == cstr.type():
                    break
            else:
                newcstr = None
            if newcstr is None:
                self.rqlexec('DELETE X constrained_by C WHERE C eid %(x)s',
                             {'x': cstr.eid}, 'x',
                             ask_confirm=confirm)
                self.rqlexec('DELETE EConstraint C WHERE C eid %(x)s',
                             {'x': cstr.eid}, 'x',
                             ask_confirm=confirm)
            else:
                newconstraints.remove(newcstr)
                values = {'x': cstr.eid,
                          'v': unicode(newcstr.serialize())}
                self.rqlexec('SET X value %(v)s WHERE X eid %(x)s',
                             values, 'x', ask_confirm=confirm)
        # 2. add new constraints
        for newcstr in newconstraints:
            self.rqlexecall(ss.constraint2rql(rschema, subjtype, objtype,
                                              newcstr),
                            ask_confirm=confirm)
        if commit:
            self.commit()
        
    def cmd_synchronize_schema(self, syncperms=True, commit=True):
        """synchronize the persistent schema against the current definition
        schema.
        
        It will synch common stuff between the definition schema and the
        actual persistent schema, it won't add/remove any entity or relation.
        """
        for etype in self.repo.schema.entities():
            self.cmd_synchronize_eschema(etype, syncperms=syncperms, commit=False)
        if commit:
            self.commit()
                
    def cmd_change_relation_props(self, subjtype, rtype, objtype,
                                  commit=True, **kwargs):
        """change some properties of a relation definition"""
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

        if size is None any size constraint will be removed
        """
        oldvalue = None
        for constr in self.repo.schema.eschema(etype).constraints(rtype):
            if isinstance(constr, SizeConstraint):
                oldvalue = constr.max
        if oldvalue == size:
            return
        if oldvalue is None and not size is None:
            ceid = self.rqlexec('INSERT EConstraint C: C value %(v)s, C cstrtype CT '
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
                self.rqlexec('DELETE EConstraint C WHERE NOT X constrained_by C')
        if commit:
            self.commit()
    
    # Workflows handling ######################################################
    
    def cmd_add_state(self, name, stateof, initial=False, commit=False, **kwargs):
        """method to ease workflow definition: add a state for one or more
        entity type(s)
        """
        stateeid = self.cmd_add_entity('State', name=name, **kwargs)
        if not isinstance(stateof, (list, tuple)):
            stateof = (stateof,)
        for etype in stateof:
            # XXX ensure etype validity
            self.rqlexec('SET X state_of Y WHERE X eid %(x)s, Y name %(et)s',
                         {'x': stateeid, 'et': etype}, 'x', ask_confirm=False)
            if initial:
                self.rqlexec('SET ET initial_state S WHERE ET name %(et)s, S eid %(x)s',
                             {'x': stateeid, 'et': etype}, 'x', ask_confirm=False)
        if commit:
            self.commit()
        return stateeid
    
    def cmd_add_transition(self, name, transitionof, fromstates, tostate,
                           requiredgroups=(), conditions=(), commit=False, **kwargs):
        """method to ease workflow definition: add a transition for one or more
        entity type(s), from one or more state and to a single state
        """
        treid = self.cmd_add_entity('Transition', name=name, **kwargs)
        if not isinstance(transitionof, (list, tuple)):
            transitionof = (transitionof,)
        for etype in transitionof:
            # XXX ensure etype validity
            self.rqlexec('SET X transition_of Y WHERE X eid %(x)s, Y name %(et)s',
                         {'x': treid, 'et': etype}, 'x', ask_confirm=False)
        for stateeid in fromstates:
            self.rqlexec('SET X allowed_transition Y WHERE X eid %(x)s, Y eid %(y)s',
                         {'x': stateeid, 'y': treid}, 'x', ask_confirm=False)
        self.rqlexec('SET X destination_state Y WHERE X eid %(x)s, Y eid %(y)s',
                     {'x': treid, 'y': tostate}, 'x', ask_confirm=False)
        self.cmd_set_transition_permissions(treid, requiredgroups, conditions,
                                            reset=False)
        if commit:
            self.commit()
        return treid

    def cmd_set_transition_permissions(self, treid,
                                       requiredgroups=(), conditions=(),
                                       reset=True, commit=False):
        """set or add (if `reset` is False) groups and conditions for a
        transition
        """
        if reset:
            self.rqlexec('DELETE T require_group G WHERE T eid %(x)s',
                         {'x': treid}, 'x', ask_confirm=False)
            self.rqlexec('DELETE T condition R WHERE T eid %(x)s',
                         {'x': treid}, 'x', ask_confirm=False)
        for gname in requiredgroups:
            ### XXX ensure gname validity
            self.rqlexec('SET T require_group G WHERE T eid %(x)s, G name %(gn)s',
                         {'x': treid, 'gn': gname}, 'x', ask_confirm=False)
        if isinstance(conditions, basestring):
            conditions = (conditions,)
        for expr in conditions:
            if isinstance(expr, str):
                expr = unicode(expr)
            self.rqlexec('INSERT RQLExpression X: X exprtype "ERQLExpression", '
                         'X expression %(expr)s, T condition X '
                         'WHERE T eid %(x)s',
                         {'x': treid, 'expr': expr}, 'x', ask_confirm=False)
        if commit:
            self.commit()

    def cmd_set_state(self, eid, statename, commit=False):
        self.session.set_pool() # ensure pool is set
        entity = self.session.eid_rset(eid).get_entity(0, 0)
        entity.change_state(entity.wf_state(statename).eid)
        if commit:
            self.commit()
        
    # EProperty handling ######################################################

    def cmd_property_value(self, pkey):
        rql = 'Any V WHERE X is EProperty, X pkey %(k)s, X value V'
        rset = self.rqlexec(rql, {'k': pkey}, ask_confirm=False)
        return rset[0][0]

    def cmd_set_property(self, pkey, value):
        value = unicode(value)
        try:
            prop = self.rqlexec('EProperty X WHERE X pkey %(k)s', {'k': pkey},
                                ask_confirm=False).get_entity(0, 0)
        except:
            self.cmd_add_entity('EProperty', pkey=unicode(pkey), value=value)
        else:
            self.rqlexec('SET X value %(v)s WHERE X pkey %(k)s',
                         {'k': pkey, 'v': value}, ask_confirm=False)

    # other data migration commands ###########################################
        
    def cmd_add_entity(self, etype, *args, **kwargs):
        """add a new entity of the given type"""
        rql = 'INSERT %s X' % etype
        relations = []
        restrictions = []
        for rtype, rvar in args:
            relations.append('X %s %s' % (rtype, rvar))
            restrictions.append('%s eid %s' % (rvar, kwargs.pop(rvar)))
        commit = kwargs.pop('commit', False)
        for attr in kwargs:
            relations.append('X %s %%(%s)s' % (attr, attr))
        if relations:
            rql = '%s: %s' % (rql, ', '.join(relations))
        if restrictions:
            rql = '%s WHERE %s' % (rql, ', '.join(restrictions))
        eid = self.rqlexec(rql, kwargs, ask_confirm=self.verbosity>=2).rows[0][0]
        if commit:
            self.commit()
        return eid
    
    def sqlexec(self, sql, args=None, ask_confirm=True):
        """execute the given sql if confirmed
        
        should only be used for low level stuff undoable with existing higher
        level actions
        """
        if not ask_confirm or self.confirm('execute sql: %s ?' % sql):
            self.session.set_pool() # ensure pool is set
            try:
                cu = self.session.system_sql(sql, args)
            except:
                ex = sys.exc_info()[1]
                if self.confirm('error: %s\nabort?' % ex):
                    raise
                return
            try:
                return cu.fetchall()
            except:
                # no result to fetch
                return
    
    def rqlexec(self, rql, kwargs=None, cachekey=None, ask_confirm=True):
        """rql action"""
        if not isinstance(rql, (tuple, list)):
            rql = ( (rql, kwargs), )
        res = None
        for rql, kwargs in rql:
            if kwargs:
                msg = '%s (%s)' % (rql, kwargs)
            else:
                msg = rql
            if not ask_confirm or self.confirm('execute rql: %s ?' % msg):
                try:
                    res = self.rqlcursor.execute(rql, kwargs, cachekey)
                except Exception, ex:
                    if self.confirm('error: %s\nabort?' % ex):
                        raise
        return res

    def rqliter(self, rql, kwargs=None, ask_confirm=True):
        return ForRqlIterator(self, rql, None, ask_confirm)

    def cmd_deactivate_verification_hooks(self):
        self.repo.hm.deactivate_verification_hooks()

    def cmd_reactivate_verification_hooks(self):
        self.repo.hm.reactivate_verification_hooks()
        
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
        sql = ("UPDATE EFRDef "
               "SET to_entity=(SELECT eid FROM EEType WHERE name='%s')"
               "WHERE eid=%s") % (newtype, rdefeid)
        self.sqlexec(sql, ask_confirm=False)
        dbhelper = self.repo.system_source.dbhelper
        sqltype = dbhelper.TYPE_MAPPING[newtype]
        sql = 'ALTER TABLE %s ALTER COLUMN %s TYPE %s' % (etype, attr, sqltype)
        self.sqlexec(sql, ask_confirm=False)
        if commit:
            self.commit()
        
    def cmd_add_entity_type_table(self, etype, commit=True):
        """low level method to create the sql table for an existing entity.
        This may be useful on accidental desync between the repository schema
        and a sql database
        """
        dbhelper = self.repo.system_source.dbhelper
        tablesql = eschema2sql(dbhelper, self.repo.schema.eschema(etype))
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
        dbhelper = self.repo.system_source.dbhelper
        tablesql = rschema2sql(dbhelper, self.repo.schema.rschema(rtype))
        for sql in tablesql.split(';'):
            if sql.strip():
                self.sqlexec(sql)
        if commit:
            self.commit()
            

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
    
    def next(self):
        if self._rsetit is not None:
            return self._rsetit.next()
        rql, kwargs = self.rql, self.kwargs
        if kwargs:
            msg = '%s (%s)' % (rql, kwargs)
        else:
            msg = rql
        if self.ask_confirm:
            if not self._h.confirm('execute rql: %s ?' % msg):
                raise StopIteration
        try:
            #print rql, kwargs
            rset = self._h.rqlcursor.execute(rql, kwargs)
        except Exception, ex:
            if self._h.confirm('error: %s\nabort?' % ex):
                raise
            else:
                raise StopIteration
        self._rsetit = iter(rset)
        return self._rsetit.next()
