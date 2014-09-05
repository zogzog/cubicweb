from cubicweb.cwconfig import CubicWebConfiguration as cwcfg
from cubicweb.cwctl import CWCTL, InstanceCommand, init_cmdline_log_threshold


class PyramidStartHandler(InstanceCommand):
    """Start an interactive pyramid server.

    This command requires http://hg.logilab.org/review/pyramid_cubicweb/

    <instance>
      identifier of the instance to configure.
    """
    name = 'pyramid'

    options = (
        ("debug",
         {'short': 'D', 'action': 'store_true',
          'help': 'start server in debug mode.'}),
        ('loglevel',
         {'short': 'l', 'type': 'choice', 'metavar': '<log level>',
          'default': None, 'choices': ('debug', 'info', 'warning', 'error'),
          'help': 'debug if -D is set, error otherwise',
          }),
    )

    def pyramid_instance(self, appid):
        from pyramid_cubicweb import make_cubicweb_application
        from waitress import serve
        cwconfig = cwcfg.config_for(appid, debugmode=self['debug'])
        init_cmdline_log_threshold(cwconfig, self['loglevel'])

        host = cwconfig['interface']
        port = cwconfig['port'] or 8080

        pyramid_config = make_cubicweb_application(cwconfig)

        repo = cwconfig.repository()
        try:
            repo.start_looping_tasks()
            serve(pyramid_config.make_wsgi_app(), host=host, port=port)
        finally:
            repo.shutdown()

CWCTL.register(PyramidStartHandler)
