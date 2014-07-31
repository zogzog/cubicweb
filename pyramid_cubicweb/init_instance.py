from cubicweb.cwconfig import CubicWebConfiguration


def includeme(config):
    appid = config.registry.settings['cubicweb.instance']
    cwconfig = CubicWebConfiguration.config_for(appid)

    config.registry['cubicweb.config'] = cwconfig
    config.registry['cubicweb.repository'] = repo = cwconfig.repository()
    config.registry['cubicweb.registry'] = repo.vreg
