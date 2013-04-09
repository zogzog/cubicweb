from cubicweb.devtools.qunit import QUnitTestCase, unittest_main

from os import path as osp


class JScript(QUnitTestCase):

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
            ), (
            "jstests/ajax_url0.html",
            "jstests/ajax_url1.html",
            "jstests/ajax_url2.html",
            "jstests/ajaxresult.json",
            ),
         ),
    )


if __name__ == '__main__':
    unittest_main()
