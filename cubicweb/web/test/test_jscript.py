from unittest import SkipTest

from cubicweb.devtools import qunit

from os import path as osp


class JScript(qunit.QUnitTestCase):

    timeout_error = SkipTest
    all_js_tests = (
        ("/static/jstests/test_utils.js", (
            "/data/cubicweb.js",
            "/data/cubicweb.compat.js",
            "/data/cubicweb.python.js",
            "/static/jstests/utils.js",
            ),
         ),

        ("/static/jstests/test_htmlhelpers.js", (
            "/data/cubicweb.js",
            "/data/cubicweb.compat.js",
            "/data/cubicweb.python.js",
            "/data/cubicweb.htmlhelpers.js",
            ),
         ),

        ("/static/jstests/test_ajax.js", (
            "/data/cubicweb.python.js",
            "/data/cubicweb.js",
            "/data/cubicweb.compat.js",
            "/data/cubicweb.htmlhelpers.js",
            "/data/cubicweb.ajax.js",
            ),
         ),
    )


if __name__ == '__main__':
    from unittest import main
    main()
