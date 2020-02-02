==========================
Use Windmill with CubicWeb
==========================

Windmill_ implements cross browser testing, in-browser recording and playback,
and functionality for fast accurate debugging and test environment integration.

.. _Windmill: http://www.getwindmill.com/

`Online features list <http://www.getwindmill.com/features>`_ is available.


Installation
============

Windmill
--------

You have to install Windmill manually for now. If you're using Debian, there is
no binary package (`yet <http://bugs.debian.org/cgi-bin/bugreport.cgi?bug=579109>`_).

The simplest solution is to use a *setuptools/pip* command (for a clean
environment, take a look to the `virtualenv
<http://pypi.python.org/pypi/virtualenv>`_ project as well)::

    $ pip install windmill
    $ curl -O http://github.com/windmill/windmill/tarball/master

However, the Windmill project doesn't release frequently. Our recommandation is
to used the last snapshot of the Git repository::

    $ git clone git://github.com/windmill/windmill.git HEAD
    $ cd windmill
    $ python3 setup.py develop

Install instructions are `available <http://wiki.github.com/windmill/windmill/installing>`_.

Be sure to have the windmill module in your PYTHONPATH afterwards::

    $ python3 -c "import windmill"

X dummy
-------

In order to reduce unecessary system load from your test machines, It's
recommended to use X dummy server for testing the Unix web clients, you need a
dummy video X driver (as xserver-xorg-video-dummy package in Debian) coupled
with a light X server as `Xvfb <http://en.wikipedia.org/wiki/Xvfb>`_.

    The dummy driver is a special driver available with the XFree86 DDX. To use
    the dummy driver, simply substitue it for your normal card driver in the
    Device section of your xorg.conf configuration file. For example, if you
    normally uses an ati driver, then you will have a Device section with
    Driver "ati" to let the X server know that you want it to load and use the
    ati driver; however, for these conformance tests, you would change that
    line to Driver "dummy" and remove any other ati specific options from the
    Device section.

    *From: http://www.x.org/wiki/XorgTesting*

Then, you can run the X server with the following command ::

    $ /usr/bin/X11/Xvfb :1 -ac -screen 0 1280x1024x8 -fbdir /tmp


Windmill usage
==============

Record your use case
--------------------

- start your instance manually
- start Windmill_ with url site as last argument (read Usage_ or use *'-h'*
  option to find required command line arguments)
- use the record button
- click on save to obtain python code of your use case
- copy the content to a new file in a *windmill* directory

.. _Usage: http://wiki.github.com/windmill/windmill/running-tests

If you are using firefox as client, consider the "firebug" option.

If you have a running instance, you can refine the test by the *loadtest* windmill option::

    $ windmill -m firebug loadtest=<test_file.py> <instance url>

Or use the internal windmill shell to explore available commands::

    $ windmill -m firebug shell <instance url>

And enter python commands:

.. sourcecode:: python

    >>> load_test(<your test file>)
    >>> run_test(<your test file>)



Integrate Windmill tests into CubicWeb
======================================

Set environment
---------------

You have to create a new unit test file and a `windmill` directory and copy all
your windmill use case into it.

.. sourcecode:: python

    # test_windmill.py

    # Run all scenarii found in windmill directory
    from cubicweb.devtools.cwwindmill import (CubicWebWindmillUseCase,
                                              unittest_main)

    if __name__ == '__main__':
        unittest_main()

Run your tests
--------------

You can easily run your windmill test suite through `pytest` or :mod:`unittest`.
You have to copy a *test_windmill.py* file from :mod:`web.test`.

To run your test series::

    $ pytest test/test_windmill.py

By default, CubicWeb will use **firefox** as the default browser and will try
to run test instance server on localhost. In the general case, You've no need
to change anything.

Check :class:`cubicweb.devtools.cwwindmill.CubicWebWindmillUseCase` for
Windmill configuration. You can edit windmill settings with following class attributes:

* browser
  identification string (firefox|ie|safari|chrome) (firefox by default)
* test_dir
  testing file path or directory (windmill directory under your unit case
  file by default)
* edit_test
  load and edit test for debugging (False by default)

Examples:

.. sourcecode:: python

    browser = 'firefox'
    test_dir = osp.join(__file__, 'windmill')
    edit_test = False

If you want to change cubicweb test server parameters, you can check class
variables from :class:`CubicWebServerConfig` or inherit it with overriding the
:attr:`configcls` attribute in :class:`CubicWebServerTC` ::

.. sourcecode:: python

    class OtherCubicWebServerConfig(CubicWebServerConfig):
        port = 9999

    class NewCubicWebServerTC(CubicWebServerTC):
        configcls = OtherCubicWebServerConfig

For instance, CubicWeb framework windmill tests can be manually run by::

    $ pytest web/test/test_windmill.py

Edit your tests
---------------

You can toggle the `edit_test` variable to enable test edition.

But if you are using `pytest` as test runner, use the `-i` option directly.
The test series will be loaded and you can run assertions step-by-step::

    $ pytest -i test/test_windmill.py

In this case, the `firebug` extension will be loaded automatically for you.

Afterwards, don't forget to save your edited test into the right file (no autosave feature).

Best practises
--------------

Don't run another instance on the same port. You risk to silence some
regressions (test runner will automatically fail in further versions).

Start your use case by using an assert on the expected primary url page.
Otherwise all your tests could fail without clear explanation of the used
navigation.

In the same location of the *test_windmill.py*, create a *windmill/* with your
windmill recorded use cases.


Caveats
=======

File Upload
-----------

Windmill can't do file uploads. This is a limitation of browser Javascript
support / sandboxing, not of Windmill per se.  It would be nice if there were
some command that would prime the Windmill HTTP proxy to add a particular file
to the next HTTP request that comes through, so that uploads could at least be
faked.

.. http://groups.google.com/group/windmill-dev/browse_thread/thread/cf9dc969722bd6bb/01aa18fdd652f7ff?lnk=gst&q=input+type+file#01aa18fdd652f7ff

.. http://davisagli.com/blog/in-browser-integration-testing-with-windmill

.. http://groups.google.com/group/windmill-dev/browse_thread/thread/b7bebcc38ed30dc7


Preferences
===========

A *.windmill/prefs.py* could be used to redefine default configuration values.

.. define CubicWeb preferences in the parent test case instead with a dedicated firefox profile

For managing browser extensions, read `advanced topic chapter
<http://wiki.github.com/windmill/windmill/advanced-topics>`_.

More configuration examples could be seen in *windmill/conf/global_settings.py*
as template.


