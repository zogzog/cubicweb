import webtest

from pyramid.config import Configurator
from cubicweb.devtools.webtest import CubicWebTestTC


class PyramidCWTest(CubicWebTestTC):
    settings = {}

    @classmethod
    def init_config(cls, config):
        super(PyramidCWTest, cls).init_config(config)
        config.global_set_option('anonymous-user', 'anon')

    def setUp(self):
        # Skip CubicWebTestTC setUp
        super(CubicWebTestTC, self).setUp()
        settings = {
            'cubicweb.bwcompat': False,
            'cubicweb.session.secret': 'test',
        }
        settings.update(self.settings)
        config = Configurator(settings=settings)
        config.registry['cubicweb.repository'] = self.repo
        config.include('cubicweb.pyramid')
        self.includeme(config)
        self.pyr_registry = config.registry
        self.webapp = webtest.TestApp(
            config.make_wsgi_app(),
            extra_environ={'wsgi.url_scheme': 'https'})

    def includeme(self, config):
        pass
