"""provides all lax instances management commands into a single utility script

:organization: Logilab
:copyright: 2008-2009 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

import sys
import os
import os.path as osp
import time
import re
import urllib2
from urllib import urlencode
from Cookie import SimpleCookie

from logilab.common.clcommands import Command, register_commands, main_run

from cubicweb.common.uilib import remove_html_tags
APPLROOT = osp.abspath(osp.join(osp.dirname(osp.abspath(__file__)), '..'))


def initialize_vregistry(applroot):
    # apply monkey patches first
    from cubicweb.goa import do_monkey_patch    
    do_monkey_patch()
    from cubicweb.goa.goavreg import GAERegistry
    from cubicweb.goa.goaconfig import GAEConfiguration
    #WebConfiguration.ext_resources['JAVASCRIPTS'].append('DATADIR/goa.js')
    config = GAEConfiguration('toto', applroot)
    vreg = GAERegistry(config)
    vreg.set_schema(config.load_schema())
    return vreg
        
def alistdir(directory):
    return [osp.join(directory, f) for f in os.listdir(directory)]


class LaxCommand(Command):
    """base command class for all lax commands
    creates vreg, schema and calls 
    """
    min_args = max_args = 0

    def run(self, args):
        self.vreg = initialize_vregistry(APPLROOT)
        self._run(args)
        

class GenerateSchemaCommand(LaxCommand):
    """generates the schema's png file"""
    name = 'genschema'

    def _run(self, args):
        assert not args, 'no argument expected'
        from yams import schema2dot        
        schema = self.vreg.schema
        skip_rels = ('owned_by', 'created_by', 'identity', 'is', 'is_instance_of')
        path = osp.join(APPLROOT, 'data', 'schema.png')
        schema2dot.schema2dot(schema, path, #size=size,
                              skiprels=skip_rels, skipmeta=True)
        print 'generated', path
        path = osp.join(APPLROOT, 'data', 'metaschema.png')
        schema2dot.schema2dot(schema, path, #size=size,
                              skiprels=skip_rels, skipmeta=False)
        print 'generated', path


class PopulateDataDirCommand(LaxCommand):
    """populate application's data directory according to used cubes"""
    name = 'populatedata'

    def _run(self, args):
        assert not args, 'no argument expected'
        # first clean everything which is a symlink from the data directory
        datadir = osp.join(APPLROOT, 'data')
        if not osp.exists(datadir):
            print 'created data directory'
            os.mkdir(datadir)
        for filepath in alistdir(datadir):
            if osp.islink(filepath):
                print 'removing', filepath
                os.remove(filepath)
        cubes = list(self.vreg.config.cubes()) + ['shared']
        for templ in cubes:
            templpath = self.vreg.config.cube_dir(templ)
            templdatadir = osp.join(templpath, 'data')
            if not osp.exists(templdatadir):
                print 'no data provided by', templ
                continue
            for resource in os.listdir(templdatadir):
                if resource == 'external_resources':
                    continue
                if not osp.exists(osp.join(datadir, resource)):
                    print 'symlinked %s from %s' % (resource, templ)
                    os.symlink(osp.join(templdatadir, resource),
                               osp.join(datadir, resource))


class NoRedirectHandler(urllib2.HTTPRedirectHandler):
    def http_error_302(self, req, fp, code, msg, headers):
        raise urllib2.HTTPError(req.get_full_url(), code, msg, headers, fp)
    http_error_301 = http_error_303 = http_error_307 = http_error_302


class GetSessionIdHandler(urllib2.HTTPRedirectHandler):
    def __init__(self, config):
        self.config = config
        
    def http_error_303(self, req, fp, code, msg, headers):
        cookie = SimpleCookie(headers['Set-Cookie'])
        sessionid = cookie['__session'].value
        print 'session id', sessionid
        setattr(self.config, 'cookie', '__session=' + sessionid)
        return 1 # on exception should be raised

    
class URLCommand(LaxCommand):
    """abstract class for commands doing stuff by accessing the web application
    """
    min_args = max_args = 1
    arguments = '<site url>'

    options = (
        ('cookie',
         {'short': 'C', 'type' : 'string', 'metavar': 'key=value',
          'default': None,
          'help': 'session/authentication cookie.'}),
        ('user',
         {'short': 'u', 'type' : 'string', 'metavar': 'login',
          'default': None,
          'help': 'user login instead of giving raw cookie string (require lax '
          'based authentication).'}),
        ('password',
         {'short': 'p', 'type' : 'string', 'metavar': 'password',
          'default': None,
          'help': 'user password instead of giving raw cookie string (require '
          'lax based authentication).'}),
        )
    
    def _run(self, args):
        baseurl = args[0]
        if not baseurl.startswith('http'):
            baseurl = 'http://' + baseurl
        if not baseurl.endswith('/'):
            baseurl += '/'
        self.base_url = baseurl
        if not self.config.cookie and self.config.user:
            # no cookie specified but a user is. Try to open a session using
            # given authentication info
            print 'opening session for', self.config.user
            opener = urllib2.build_opener(GetSessionIdHandler(self.config))
            urllib2.install_opener(opener)
            data = urlencode(dict(__login=self.config.user,
                                  __password=self.config.password))
            self.open_url(urllib2.Request(baseurl, data))            
        opener = urllib2.build_opener(NoRedirectHandler())
        urllib2.install_opener(opener)        
        self.do_base_url(baseurl)

    def build_req(self, url):
        req = urllib2.Request(url)
        if self.config.cookie:
            req.headers['Cookie'] = self.config.cookie
        return req
    
    def open_url(self, req):
        try:
            return urllib2.urlopen(req)
        except urllib2.HTTPError, ex:
            if ex.code == 302:
                self.error_302(req, ex)
            elif ex.code == 500:
                self.error_500(req, ex)
            else:
                raise

    def error_302(self, req, ex):
        print 'authentication required'
        print ('visit %s?vid=authinfo with your browser to get '
               'authentication info' % self.base_url)
        sys.exit(1)

    def error_500(self, req, ex):
        print 'an unexpected error occured on the server'
        print ('you may get more information by visiting '
               '%s' % req.get_full_url())
        sys.exit(1)

    def extract_message(self, data):
        match = re.search(r'<div class="message">(.*?)</div>', data.read(), re.M|re.S)
        if match:
            msg = remove_html_tags(match.group(1))
            print msg
            return msg
        
    def do_base_url(self, baseurl):
        raise NotImplementedError()

        
class DSInitCommand(URLCommand):
    """initialize the datastore"""
    name = 'db-init'

    options = URLCommand.options + (
        ('sleep',
         {'short': 's', 'type' : 'int', 'metavar': 'nb seconds',
          'default': None,
          'help': 'number of seconds to wait between each request to avoid '
          'going out of quota.'}),
        )
        
    def do_base_url(self, baseurl):
        req = self.build_req(baseurl + '?vid=contentinit')
        while True:
            try:
                data = self.open_url(req)
            except urllib2.HTTPError, ex:
                if ex.code == 303: # redirect
                    print 'process completed'
                    break
                raise
            msg = self.extract_message(data)
            if msg and msg.startswith('error: '):
                print ('you may to cleanup datastore by visiting '
                       '%s?vid=contentclear (ALL ENTITIES WILL BE DELETED)'
                       % baseurl)
                break
            if self.config.sleep:
                time.sleep(self.config.sleep)


class CleanSessionsCommand(URLCommand):
    """cleanup sessions on the server. This command should usually be called
    regularly by a cron job or equivalent.
    """
    name = "cleansessions"
    def do_base_url(self, baseurl):
        req = self.build_req(baseurl + '?vid=cleansessions')
        data = self.open_url(req)
        self.extract_message(data)
            
    
register_commands([GenerateSchemaCommand,
                   PopulateDataDirCommand,
                   DSInitCommand,
                   CleanSessionsCommand,
                   ])

def run():
    main_run(sys.argv[1:])
    
if __name__ == '__main__':
    run()
