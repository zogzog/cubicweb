from cubicweb.devtools import qunit

from os import path as osp


class JScript(qunit.QUnitTestCase):

    all_js_tests = (
        ("jstests/test_utils.js", (
            "../../web/data/cubicweb.js",
            "../../web/data/cubicweb.compat.js",
            "../../web/data/cubicweb.python.js",
            "jstests/utils.js",
            ),
         ),

        ("jstests/test_htmlhelpers.js", (
            "../../web/data/cubicweb.js",
            "../../web/data/cubicweb.compat.js",
            "../../web/data/cubicweb.python.js",
            "../../web/data/cubicweb.htmlhelpers.js",
            ),
         ),

        ("jstests/test_ajax.js", (
            "../../web/data/cubicweb.python.js",
            "../../web/data/cubicweb.js",
            "../../web/data/cubicweb.compat.js",
            "../../web/data/cubicweb.htmlhelpers.js",
            "../../web/data/cubicweb.ajax.js",
            ),
         ),
    )


if __name__ == '__main__':
    from unittest import main
    main()
