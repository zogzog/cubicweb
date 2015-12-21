from __future__ import absolute_import

import webtest

from cubicweb.wsgi import handler
from cubicweb.devtools.testlib import CubicWebTC


class CubicWebTestTC(CubicWebTC):
    def setUp(self):
        super(CubicWebTestTC, self).setUp()
        self.config.global_set_option('base-url', 'http://localhost.local/')
        # call load_configuration again to let the config reset its datadir_url
        self.config.load_configuration()
        webapp = handler.CubicWebWSGIApplication(self.config)
        self.webapp = webtest.TestApp(webapp)

    def tearDown(self):
        del self.webapp
        super(CubicWebTestTC, self).tearDown()

    def login(self, user=None, password=None, **args):
        if user is None:
            user = self.admlogin
        if password is None:
            password = self.admpassword if user == self.admlogin else user
        args.update({
            '__login': user,
            '__password': password
        })
        return self.webapp.get('/login', args)

    def logout(self):
        return self.webapp.get('/logout')
