.. -*- coding: utf-8 -*-

Deploy a *CubicWeb* application
===============================

Deployment with uwsgi
---------------------

`uWSGI <https://uwsgi-docs.readthedocs.io/>`_ is often used to deploy CubicWeb
applications.

Short version is install `uwsgi`:

.. sourcecode:: console

  apt install uwsgi

Deploy a configuration file for your application
`/etc/uwsgi/apps-enabled/example.ini`:

.. sourcecode:: ini

    [uwsgi]
    master = true
    http = 0.0.0.0:8080
    env = CW_INSTANCE=example
    wsgi-file = /etc/cubicweb.d/example/wsgiapp.py
    processes = 8
    threads = 1
    plugins = http,python3
    auto-procname = true
    lazy-apps = true
    log-master = true
    # disable uwsgi request logging
    disable-logging = true
    stats = 127.0.0.1:1717

The `wsgiapp.py` file looks like this:

.. sourcecode:: python

    import os
    from cubicweb.pyramid import wsgi_application_from_cwconfig
    from cubicweb.cwconfig import CubicWebConfiguration as cwcfg

    appid = os.environ['CW_INSTANCE']  # instance name
    cwconfig = cwcfg.config_for(appid)

    cwconfig.log_format = ('{0} pid:{1} (%(name)s) %(levelname)s: %(message)s'
                           .format(appid, os.getpid()))

    application = wsgi_application_from_cwconfig(cwconfig)
    repo = application.application.registry['cubicweb.repository']


Deployment with SaltStack
-------------------------

To deploy with SaltStack one can refer themselves to the
`cubicweb-formula <https://hg.logilab.org/master/salt/cubicweb-formula/>`_.

Deployment with Kubernetes
--------------------------

To deploy in a Kubernetes cluster, you can take inspiration from the
instructions included in
`the fresh cube  <https://hg.logilab.org/master/cubes/fresh/file/tip/README.rst#l20>`_
and the `deployment yaml files <https://hg.logilab.org/master/cubes/fresh/file/tip/deploy>`_.
