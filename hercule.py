"""RQL client for cubicweb, connecting to application using pyro

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

import os
import sys

from logilab.common import flatten
from logilab.common.cli import CLIHelper
from logilab.common.clcommands import BadCommandUsage, pop_arg, register_commands
from cubicweb.toolsutils import CONNECT_OPTIONS, Command

# result formatter ############################################################

PAGER = os.environ.get('PAGER', 'less')

def pager_format_results(writer, layout):
    """pipe results to a pager like more or less"""
    (r, w) = os.pipe()
    pid = os.fork()
    if pid == 0:
        os.dup2(r, 0)
        os.close(r)
        os.close(w)
        if PAGER == 'less':
            os.execlp(PAGER, PAGER, '-r')
        else:
            os.execlp(PAGER, PAGER)
        sys.exit(0)
    stream = os.fdopen(w, "w")
    os.close(r)
    try:
        format_results(writer, layout, stream)
    finally:
        stream.close()
        os.waitpid(pid, 0)

def izip2(list1, list2):
    for i in xrange(len(list1)):
        yield list1[i] + tuple(list2[i])

def format_results(writer, layout, stream=sys.stdout):
    """format result as text into the given file like object"""
    writer.format(layout, stream)


try:
    encoding = sys.stdout.encoding
except AttributeError: # python < 2.3
    encoding = 'UTF-8'

def to_string(value, encoding=encoding):
    """used to converte arbitrary values to encoded string"""
    if isinstance(value, unicode):
        return value.encode(encoding, 'replace')
    return str(value)

# command line querier ########################################################

class RQLCli(CLIHelper):
    """Interactive command line client for CubicWeb, allowing user to execute
    arbitrary RQL queries and to fetch schema information
    """
    # commands are prefixed by ":"
    CMD_PREFIX = ':'
    # map commands to folders
    CLIHelper.CMD_MAP.update({
        'connect' :      "CubicWeb",
        'schema'  :      "CubicWeb",
        'description'  : "CubicWeb",
        'commit' :       "CubicWeb",
        'rollback' :     "CubicWeb",
        'autocommit'  :  "Others",
        'debug' :        "Others",
        })

    def __init__(self, application=None, user=None, password=None,
                 host=None, debug=0):
        CLIHelper.__init__(self, os.path.join(os.environ["HOME"], ".erqlhist"))
        self.cnx = None
        self.cursor = None
        # XXX give a Request like object, not None
        from cubicweb.schemaviewer import SchemaViewer
        self.schema_viewer = SchemaViewer(None, encoding=encoding)
        from logilab.common.ureports import TextWriter
        self.writer = TextWriter()
        self.autocommit = False
        self._last_result = None
        self._previous_lines = []
        if application is not None:
            self.do_connect(application, user, password, host)
        self.do_debug(debug)

    def do_connect(self, application, user=None, password=None, host=None):
        """connect to an cubicweb application"""
        from cubicweb.dbapi import connect
        if user is None:
            user = raw_input('login: ')
        if password is None:
            from getpass import getpass
            password = getpass('password: ')
        if self.cnx is not None:
            self.cnx.close()
        self.cnx = connect(user=user, password=password, host=host,
                           database=application)
        self.schema = self.cnx.get_schema()
        self.cursor = self.cnx.cursor()
        # add entities types to the completion commands
        self._completer.list = (self.commands.keys() +
                                self.schema.entities() + ['Any'])
        print _('You are now connected to %s') % application


    help_do_connect = ('connect', "connect <application> [<user> [<password> [<host>]]]",
                       _(do_connect.__doc__))

    def do_debug(self, debug=1):
        """set debug level"""
        self._debug = debug
        if debug:
            self._format = format_results
        else:
            self._format = pager_format_results
        if self._debug:
            print _('Debug level set to %s'%debug)

    help_do_debug = ('debug', "debug [debug_level]", _(do_debug.__doc__))

    def do_description(self):
        """display the description of the latest result"""
        if self.rset.description is None:
            print _('No query has been executed')
        else:
            print '\n'.join([', '.join(line_desc)
                             for line_desc in self.rset.description])

    help_do_description = ('description', "description", _(do_description.__doc__))

    def do_schema(self, name=None):
        """display information about the application schema """
        if self.cnx is None:
            print _('You are not connected to an application !')
            return
        done = None
        if name is None:
            # display the full schema
            self.display_schema(self.schema)
            done = 1
        else:
            if self.schema.has_entity(name):
                self.display_schema(self.schema.eschema(name))
                done = 1
            if self.schema.has_relation(name):
                self.display_schema(self.schema.rschema(name))
                done = 1
        if done is None:
            print _('Unable to find anything named "%s" in the schema !') % name

    help_do_schema = ('schema', "schema [keyword]", _(do_schema.__doc__))


    def do_commit(self):
        """commit the current transaction"""
        self.cnx.commit()

    help_do_commit = ('commit', "commit", _(do_commit.__doc__))

    def do_rollback(self):
        """rollback the current transaction"""
        self.cnx.rollback()

    help_do_rollback = ('rollback', "rollback", _(do_rollback.__doc__))

    def do_autocommit(self):
        """toggle autocommit mode"""
        self.autocommit = not self.autocommit

    help_do_autocommit = ('autocommit', "autocommit", _(do_autocommit.__doc__))


    def handle_line(self, stripped_line):
        """handle non command line :
        if the query is complete, executes it and displays results (if any)
        else, stores the query line and waits for the suite
        """
        if self.cnx is None:
            print _('You are not connected to an application !')
            return
        # append line to buffer
        self._previous_lines.append(stripped_line)
        # query are ended by a ';'
        if stripped_line[-1] != ';':
            return
        # extract query from the buffer and flush it
        query = '\n'.join(self._previous_lines)
        self._previous_lines = []
        # search results
        try:
            self.rset = rset = self.cursor.execute(query)
        except:
            if self.autocommit:
                self.cnx.rollback()
            raise
        else:
            if self.autocommit:
                self.cnx.commit()
        self.handle_result(rset)

    def handle_result(self, rset):
        """display query results if any"""
        if not rset:
            print _('No result matching query')
        else:
            from logilab.common.ureports import Table
            children = flatten(izip2(rset.description, rset.rows), to_string)
            layout = Table(cols=2*len(rset.rows[0]), children=children, cheaders=1)
            self._format(self.writer, layout)
            print _('%s results matching query') % rset.rowcount

    def display_schema(self, schema):
        """display a schema object"""
        attr = schema.__class__.__name__.lower().replace('cubicweb', '')
        layout = getattr(self.schema_viewer, 'visit_%s' % attr)(schema)
        self._format(self.writer, layout)


class CubicWebClientCommand(Command):
    """A command line querier for CubicWeb, using the Relation Query Language.

    <application>
      identifier of the application to connect to
    """
    name = 'client'
    arguments = '<application>'
    options = CONNECT_OPTIONS + (
        ("verbose",
         {'short': 'v', 'type' : 'int', 'metavar': '<level>',
          'default': 0,
          'help': 'ask confirmation to continue after an error.',
          }),
        ("batch",
         {'short': 'b', 'type' : 'string', 'metavar': '<file>',
          'help': 'file containing a batch of RQL statements to execute.',
          }),
        )

    def run(self, args):
        """run the command with its specific arguments"""
        appid = pop_arg(args, expected_size_after=None)
        batch_stream = None
        if args:
            if len(args) == 1 and args[0] == '-':
                batch_stream = sys.stdin
            else:
                raise BadCommandUsage('too many arguments')
        if self.config.batch:
            batch_stream = open(self.config.batch)
        cli = RQLCli(appid, self.config.user, self.config.password,
                     self.config.host, self.config.debug)
        if batch_stream:
            cli.autocommit = True
            for line in batch_stream:
                line = line.strip()
                if not line:
                    continue
                print '>>>', line
                cli.handle_line(line)
        else:
            cli.run()

register_commands((CubicWebClientCommand,))
