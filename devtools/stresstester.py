""" Usage: %s [OPTIONS] <instance id> <queries file>

Stress test a CubicWeb repository

OPTIONS:
  -h / --help
     Display this help message and exit.

  -u / --user <user>
     Connect as <user> instead of being prompted to give it.
  -p / --password <password>
     Automatically give <password> for authentication instead of being prompted
     to give it.

  -n / --nb-times <num>
     Repeat queries <num> times.
  -t / --nb-threads <num>
     Execute queries in <num> parallel threads.
  -P / --profile <prof_file>
     dumps profile results (hotshot) in <prof_file>
  -o / --report-output <filename>
     Write profiler report into <filename> rather than on stdout

Copyright (c) 2003-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""

import os
import sys
import threading
import getopt
import traceback
from getpass import getpass
from os.path import basename
from time import clock

from logilab.common.fileutils import lines
from logilab.common.ureports import Table, TextWriter
from cubicweb.server.repository import Repository
from cubicweb.dbapi import Connection

TB_LOCK = threading.Lock()

class QueryExecutor:
    def __init__(self, cursor, times, queries, reporter = None):
        self._cursor = cursor
        self._times = times
        self._queries = queries
        self._reporter = reporter

    def run(self):
        cursor = self._cursor
        times = self._times
        while times:
            for index, query in enumerate(self._queries):
                start = clock()
                try:
                    cursor.execute(query)
                except KeyboardInterrupt:
                    raise
                except:
                    TB_LOCK.acquire()
                    traceback.print_exc()
                    TB_LOCK.release()
                    return
                if self._reporter is not None:
                    self._reporter.add_proftime(clock() - start, index)
            times -= 1

def usage(status=0):
    """print usage string and exit"""
    print __doc__ % basename(sys.argv[0])
    sys.exit(status)


class ProfileReporter:
    """a profile reporter gathers all profile informations from several
    threads and can write a report that summarizes all profile informations
    """
    profiler_lock = threading.Lock()

    def __init__(self, queries):
        self._queries = tuple(queries)
        self._profile_results = [(0., 0)] * len(self._queries)
        # self._table_report = Table(3, rheaders = True)
        len_max = max([len(query) for query in self._queries]) + 5
        self._query_fmt = '%%%ds' % len_max

    def add_proftime(self, elapsed_time, query_index):
        """add a new time measure for query"""
        ProfileReporter.profiler_lock.acquire()
        cumul_time, times = self._profile_results[query_index]
        cumul_time += elapsed_time
        times += 1.
        self._profile_results[query_index] = (cumul_time, times)
        ProfileReporter.profiler_lock.release()

    def dump_report(self, output = sys.stdout):
        """dump report in 'output'"""
        table_elems = ['RQL Query', 'Times', 'Avg Time']
        total_time = 0.
        for query, (cumul_time, times) in zip(self._queries, self._profile_results):
            avg_time = cumul_time / float(times)
            table_elems += [str(query), '%f' % times, '%f' % avg_time ]
            total_time += cumul_time
        table_elems.append('Total time :')
        table_elems.append(str(total_time))
        table_elems.append(' ')
        table_layout = Table(3, rheaders = True, children = table_elems)
        TextWriter().format(table_layout, output)
        # output.write('\n'.join(tmp_output))


def run(args):
    """run the command line tool"""
    try:
        opts, args = getopt.getopt(args, 'hn:t:u:p:P:o:', ['help', 'user=', 'password=',
                                                           'nb-times=', 'nb-threads=',
                                                           'profile', 'report-output=',])
    except Exception, ex:
        print ex
        usage(1)
    repeat = 100
    threads = 1
    user = os.environ.get('USER', os.environ.get('LOGNAME'))
    password = None
    report_output = sys.stdout
    prof_file = None
    for opt, val in opts:
        if opt in ('-h', '--help'):
            usage()
        if opt in ('-u', '--user'):
            user = val
        elif opt in ('-p', '--password'):
            password = val
        elif opt in ('-n', '--nb-times'):
            repeat = int(val)
        elif opt in ('-t', '--nb-threads'):
            threads = int(val)
        elif opt in ('-P', '--profile'):
            prof_file = val
        elif opt in ('-o', '--report-output'):
            report_output = file(val, 'w')
    if len(args) != 2:
        usage(1)
    queries =  [query for query in lines(args[1]) if not query.startswith('#')]
    if user is None:
        user = raw_input('login: ')
    if password is None:
        password = getpass('password: ')
    from cubicweb.cwconfig import instance_configuration
    config = instance_configuration(args[0])
    # get local access to the repository
    print "Creating repo", prof_file
    repo = Repository(config, prof_file)
    cnxid = repo.connect(user, password=password)
    # connection to the CubicWeb repository
    repo_cnx = Connection(repo, cnxid)
    repo_cursor = repo_cnx.cursor()
    reporter = ProfileReporter(queries)
    if threads > 1:
        executors = []
        while threads:
            qe = QueryExecutor(repo_cursor, repeat, queries, reporter = reporter)
            executors.append(qe)
            thread = threading.Thread(target=qe.run)
            qe.thread = thread
            thread.start()
            threads -= 1
        for qe in executors:
            qe.thread.join()
##         for qe in executors:
##             print qe.thread, repeat - qe._times, 'times'
    else:
        QueryExecutor(repo_cursor, repeat, queries, reporter = reporter).run()
    reporter.dump_report(report_output)


if __name__ == '__main__':
    run(sys.argv[1:])
