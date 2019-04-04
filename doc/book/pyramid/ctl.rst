.. _cubicweb-ctl_pyramid:

The 'pyramid' command
=====================

.. program:: cubicweb-ctl pyramid

The 'pyramid' command is a replacement for the 'start' command of :ref:`cubicweb-ctl`.
It provides the same options and a few other ones.

Options
-------


.. option:: --no-daemon

    Run the server in the foreground.

.. option:: --debug-mode

    Activate the repository debug mode (logs in the console and the debug
    toolbar). Implies :option:`--no-daemon`.

    Also force the following pyramid options:

    .. code-block:: ini

        pyramid.debug_authorization = yes
        pyramid.debug_notfound = yes
        pyramid.debug_routematch = yes
        pyramid.reload_templates = yes

.. option:: -D, --debug

    Equals to :option:`--debug-mode` :option:`--no-daemon` :option:`--reload`

.. option:: --reload

    Restart the server if any source file is changed

.. option:: --reload-interval=RELOAD_INTERVAL

    Interval, in seconds, between file modifications checks [current: 1]

.. option:: -l <log level>, --loglevel=<log level>

    Set the loglevel. debug if -D is set, error otherwise

.. option:: -p, --profile

    Enable profiling. See :ref:`profiling`.

.. option:: --profile-output=PROFILE_OUTPUT

    Profiling output file (default: "program.prof")

.. option:: --profile-dump-every=N

    Dump profile stats to ouput every N requests (default: 100)
