import webtest

from cubicweb.devtools.webtest import CubicWebTestTC

from cubicweb.pyramid import config_from_cwconfig


class PyramidCWTest(CubicWebTestTC):
    settings = {}

    @classmethod
    def init_config(cls, config):
        super(PyramidCWTest, cls).init_config(config)
        config.global_set_option('anonymous-user', 'anon')

    def setUp(self):
        # Skip CubicWebTestTC setUp
        super(CubicWebTestTC, self).setUp()
        config = config_from_cwconfig(self.config, self.settings)
        self.includeme(config)
        self.pyr_registry = config.registry
        self.webapp = webtest.TestApp(
            config.make_wsgi_app(),
            extra_environ={'wsgi.url_scheme': 'https'})

    def includeme(self, config):
        pass
