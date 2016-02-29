import webtest

from cubicweb.devtools.webtest import CubicWebTestTC

from pyramid_cubicweb import make_cubicweb_application


class PyramidCWTest(CubicWebTestTC):
    settings = {}

    @classmethod
    def init_config(cls, config):
        super(PyramidCWTest, cls).init_config(config)
        config.global_set_option('https-url', 'https://localhost.local/')
        config.global_set_option('anonymous-user', 'anon')
        config.https_uiprops = None
        config.https_datadir_url = None

    def setUp(self):
        # Skip CubicWebTestTC setUp
        super(CubicWebTestTC, self).setUp()
        config = make_cubicweb_application(self.config, self.settings)
        self.includeme(config)
        self.pyr_registry = config.registry
        self.webapp = webtest.TestApp(
            config.make_wsgi_app(),
            extra_environ={'wsgi.url_scheme': 'https'})

    def includeme(self, config):
        pass
