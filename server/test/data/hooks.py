from cubicweb.server.hooksmanager import SystemHook

CALLED_EVENTS = {}

class StartupHook(SystemHook):
    events = ('server_startup',)
    def call(self, repo):
        CALLED_EVENTS['server_startup'] = True

class ShutdownHook(SystemHook):
    events = ('server_shutdown',)
    def call(self, repo):
        CALLED_EVENTS['server_shutdown'] = True


class LoginHook(SystemHook):
    events = ('session_open',)
    def call(self, session):
        CALLED_EVENTS['session_open'] = session.user.login

class LogoutHook(SystemHook):
    events = ('session_close',)
    def call(self, session):
        CALLED_EVENTS['session_close'] = session.user.login
