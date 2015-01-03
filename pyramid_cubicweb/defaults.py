def includeme(config):
    config.include('pyramid_cubicweb.session')
    config.include('pyramid_cubicweb.auth')
    config.include('pyramid_cubicweb.login')
