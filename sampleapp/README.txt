A sample application to test the pyramid_cubicweb library
=========================================================

Requirements
------------

System requirements
~~~~~~~~~~~~~~~~~~~

On a ubuntu 14.04::

    sudo apt-get install libgecode-dev libxml2-dev libxslt1-dev python-dev \
    libz-dev libpq-dev libtiff5-dev libfreetype6-dev

Python requirements
~~~~~~~~~~~~~~~~~~~

::

    pip install -r requirements.txt
    (cd .. && python setup.py develop)
    python setup.py develop


Cubicweb instance
~~~~~~~~~~~~~~~~~

You need a postgresql server.

::

    export CW_MODE=user
    cubicweb-ctl create blog test


Running the app
---------------

::

    pserve --reload develop.ini
