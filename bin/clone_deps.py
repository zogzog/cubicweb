#!/usr/bin/python
import os
import sys
from subprocess import call, Popen, PIPE
try:
    from mercurial.dispatch import dispatch as hg_call
except ImportError:
    print '-' * 20
    print "mercurial module is not reachable from this Python interpreter"
    print "trying from command line ..."
    tryhg = os.system('hg --version')
    if tryhg:
        print 'mercurial seems to unavailable, please install it'
        raise
    print 'found it, ok'
    print '-' * 20
    def hg_call(args):
        call(['hg'] + args)
from urllib import urlopen
from os import path as osp, pardir
from os.path import normpath, join, dirname

BASE_URL = 'http://www.logilab.org/hg/'

to_clone = ['fyzz', 'yams', 'rql',
            'logilab/common', 'logilab/constraint', 'logilab/database',
            'logilab/devtools', 'logilab/mtconverter',
            'cubes/blog', 'cubes/calendar', 'cubes/card', 'cubes/comment',
            'cubes/datafeed', 'cubes/email', 'cubes/file', 'cubes/folder',
            'cubes/forgotpwd', 'cubes/keyword', 'cubes/link',
            'cubes/mailinglist', 'cubes/nosylist', 'cubes/person',
            'cubes/preview', 'cubes/registration', 'cubes/rememberme',
            'cubes/tag', 'cubes/vcsfile', 'cubes/zone']

# a couple of functions to be used to explore available
# repositories and cubes
def list_repos(repos_root):
    assert repos_root.startswith('http://')
    hgwebdir_repos = (repo.strip()
                      for repo in urlopen(repos_root + '?style=raw').readlines()
                      if repo.strip())
    prefix = osp.commonprefix(hgwebdir_repos)
    return (repo[len(prefix):].strip('/')
            for repo in hgwebdir_repos)

def list_all_cubes(base_url=BASE_URL):
    all_repos = list_repos(base_url)
    #search for cubes
    for repo in all_repos:
        if repo.startswith('cubes'):
            to_clone.append(repo)

def get_latest_debian_tag(path):
    proc = Popen(['hg', '-R', path, 'tags'], stdout=PIPE)
    out, _err = proc.communicate()
    for line in out.splitlines():
        if 'debian-version' in line:
            return line.split()[0]

def main():
    if len(sys.argv) == 1:
        base_url = BASE_URL
    elif len(sys.argv) == 2:
        base_url = sys.argv[1]
    else:
        print >> sys.stderr, 'usage %s [base_url]' %  sys.argv[0]
        sys.exit(1)
    print len(to_clone), 'repositories will be cloned'
    base_dir = normpath(join(dirname(__file__), pardir, pardir))
    os.chdir(base_dir)
    not_updated = []
    for repo in to_clone:
        url = base_url + repo
        if '/' not in repo:
            target_path = repo
        else:
            assert repo.count('/') == 1, repo
            directory, repo = repo.split('/')
            if not osp.isdir(directory):
                os.mkdir(directory)
                open(join(directory, '__init__.py'), 'w').close()
            target_path = osp.join(directory, repo)
        if osp.exists(target_path):
            print target_path, 'seems already cloned. Skipping it.'
        else:
            hg_call(['clone', '-U', url, target_path])
            tag = get_latest_debian_tag(target_path)
            if tag:
                print 'updating to', tag
                hg_call(['update', '-R', target_path, tag])
            else:
                not_updated.append(target_path)
    print """
CubicWeb dependencies and standard set of cubes have been fetched and
update to the latest stable version.

You should ensure your PYTHONPATH contains `%(basedir)s`.
You might want to read the environment configuration section of the documentation
at http://docs.cubicweb.org/admin/setup.html#environment-configuration

You can find more cubes at http://www.cubicweb.org.
Clone them from `%(baseurl)scubes/` into the `%(basedir)s%(sep)scubes%(sep)s` directory.

To get started you may read http://docs.cubicweb.org/tutorials/base/index.html.
""" % {'basedir': os.getcwd(), 'baseurl': base_url, 'sep': os.sep}
    if not_updated:
        print >> sys.stderr, 'WARNING: The following repositories were not updated (no debian tag found):'
        for path in not_updated:
            print >> sys.stderr, '\t-', path

if __name__ == '__main__':
    main()



