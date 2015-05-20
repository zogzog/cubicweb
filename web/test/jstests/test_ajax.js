$(document).ready(function() {

    QUnit.module("ajax", {
        setup: function() {
          this.scriptsLength = $('head script[src]').length-1;
          this.cssLength = $('head link[rel=stylesheet]').length-1;
          // re-initialize cw loaded cache so that each tests run in a
          // clean environment, have a lookt at _loadAjaxHtmlHead implementation
          // in cubicweb.ajax.js for more information.
          cw.loaded_scripts = [];
          cw.loaded_links = [];
        },
        teardown: function() {
          $('head script[src]:lt(' + ($('head script[src]').length - 1 - this.scriptsLength) + ')').remove();
          $('head link[rel=stylesheet]:gt(' + this.cssLength + ')').remove();
        }
      });

    function jsSources() {
        return $.map($('head script[src]'), function(script) {
            return script.getAttribute('src');
        });
    }

    QUnit.test('test simple h1 inclusion (ajax_url0.html)', function() {
        expect(3);
        equal(jQuery('#qunit-fixture').children().length, 0);
        stop();
        jQuery('#qunit-fixture').loadxhtml(BASE_URL + 'cwsoftwareroot/web/test/jstests/ajax_url0.html')
        .addCallback(function() {
                try {
                    equal(jQuery('#qunit-fixture').children().length, 1);
                    equal(jQuery('#qunit-fixture h1').html(), 'Hello');
                } finally {
                    start();
                };
            }
        );
    });

    QUnit.test('test simple html head inclusion (ajax_url1.html)', function() {
        expect(6);
        var scriptsIncluded = jsSources();
        equal(jQuery.inArray('http://foo.js', scriptsIncluded), - 1);
        stop();
        jQuery('#qunit-fixture').loadxhtml(BASE_URL + 'cwsoftwareroot/web/test/jstests/ajax_url1.html')
        .addCallback(function() {
                try {
                    var origLength = scriptsIncluded.length;
                    scriptsIncluded = jsSources();
                    // check that foo.js has been prepended to <head>
                    equal(scriptsIncluded.length, origLength + 1);
                    equal(scriptsIncluded.indexOf('http://foo.js'), 0);
                    // check that <div class="ajaxHtmlHead"> has been removed
                    equal(jQuery('#qunit-fixture').children().length, 1);
                    equal(jQuery('div.ajaxHtmlHead').length, 0);
                    equal(jQuery('#qunit-fixture h1').html(), 'Hello');
                } finally {
                    start();
                };
            }
        );
    });

    QUnit.test('test addCallback', function() {
        expect(3);
        equal(jQuery('#qunit-fixture').children().length, 0);
        stop();
        var d = jQuery('#qunit-fixture').loadxhtml(BASE_URL + 'cwsoftwareroot/web/test/jstests/ajax_url0.html');
        d.addCallback(function() {
            try {
                equal(jQuery('#qunit-fixture').children().length, 1);
                equal(jQuery('#qunit-fixture h1').html(), 'Hello');
            } finally {
                start();
            };
        });
    });

    QUnit.test('test callback after synchronous request', function() {
        expect(1);
        var deferred = new Deferred();
        var result = jQuery.ajax({
            url: BASE_URL + 'cwsoftwareroot/web/test/jstests/ajax_url0.html',
            async: false,
            beforeSend: function(xhr) {
                deferred._req = xhr;
            },
            success: function(data, status) {
                deferred.success(data);
            }
        });
        stop();
        deferred.addCallback(function() {
            try {
                // add an assertion to ensure the callback is executed
                ok(true, "callback is executed");
            } finally {
                start();
            };
        });
    });

    QUnit.test('test addCallback with parameters', function() {
        expect(3);
        equal(jQuery('#qunit-fixture').children().length, 0);
        stop();
        var d = jQuery('#qunit-fixture').loadxhtml(BASE_URL + 'cwsoftwareroot/web/test/jstests/ajax_url0.html');
        d.addCallback(function(data, req, arg1, arg2) {
            try {
                equal(arg1, 'Hello');
                equal(arg2, 'world');
            } finally {
                start();
            };
        },
        'Hello', 'world');
    });

    QUnit.test('test callback after synchronous request with parameters', function() {
        expect(3);
        var deferred = new Deferred();
        deferred.addCallback(function(data, req, arg1, arg2) {
            // add an assertion to ensure the callback is executed
            try {
                ok(true, "callback is executed");
                equal(arg1, 'Hello');
                equal(arg2, 'world');
            } finally {
                start();
            };
        },
        'Hello', 'world');
        deferred.addErrback(function() {
            // throw an exception to start errback chain
            try {
                throw this._error;
            } finally {
                start();
            };
        });
        stop();
        var result = jQuery.ajax({
            url: BASE_URL + 'cwsoftwareroot/web/test/jstests/ajax_url0.html',
            async: false,
            beforeSend: function(xhr) {
                deferred._req = xhr;
            },
            success: function(data, status) {
                deferred.success(data);
            }
        });
    });

  QUnit.test('test addErrback', function() {
        expect(1);
        stop();
        var d = jQuery('#qunit-fixture').loadxhtml(BASE_URL + 'cwsoftwareroot/web/test/jstests/nonexistent.html');
        d.addCallback(function() {
            // should not be executed
            ok(false, "callback is executed");
        });
        d.addErrback(function() {
            try {
                ok(true, "errback is executed");
            } finally {
                start();
            };
        });
    });

    QUnit.test('test callback execution order', function() {
        expect(3);
        var counter = 0;
        stop();
        var d = jQuery('#qunit-fixture').loadxhtml(BASE_URL + 'cwsoftwareroot/web/test/jstests/ajax_url0.html');
        d.addCallback(function() {
                try {
                    equal(++counter, 1); // should be executed first
                } finally {
                    start();
                };
            }
        );
        d.addCallback(function() {
            equal(++counter, 2);
        });
        d.addCallback(function() {
            equal(++counter, 3);
        });
    });

    QUnit.test('test already included resources are ignored (ajax_url1.html)', function() {
        expect(10);
        var scriptsIncluded = jsSources();
        // NOTE:
        equal(jQuery.inArray('http://foo.js', scriptsIncluded), -1);
        equal(jQuery('head link').length, 1);
        /* use endswith because in pytest context we have an absolute path */
        ok(jQuery('head link').attr('href').endswith('/qunit.css'), 'qunit.css is loaded');
        stop();
        jQuery('#qunit-fixture').loadxhtml(BASE_URL + 'cwsoftwareroot/web/test/jstests/ajax_url1.html')
        .addCallback(function() {
                var origLength = scriptsIncluded.length;
                scriptsIncluded = jsSources();
                try {
                    // check that foo.js has been inserted in <head>
                    equal(scriptsIncluded.length, origLength + 1);
                    equal(scriptsIncluded.indexOf('http://foo.js'), 0);
                    // check that <div class="ajaxHtmlHead"> has been removed
                    equal(jQuery('#qunit-fixture').children().length, 1);
                    equal(jQuery('div.ajaxHtmlHead').length, 0);
                    equal(jQuery('#qunit-fixture h1').html(), 'Hello');
                    // qunit.css is not added twice
                    equal(jQuery('head link').length, 1);
                    /* use endswith because in pytest context we have an absolute path */
                    ok(jQuery('head link').attr('href').endswith('/qunit.css'), 'qunit.css is loaded');
                } finally {
                    start();
                }
            }
        );
    });

    QUnit.test('test synchronous request loadRemote', function() {
        var res = loadRemote(BASE_URL + 'cwsoftwareroot/web/test/jstests/ajaxresult.json', {},
        'GET', true);
        deepEqual(res, ['foo', 'bar']);
    });

    QUnit.test('test event on CubicWeb', function() {
        expect(1);
        stop();
        var events = null;
        jQuery(CubicWeb).bind('server-response', function() {
            // check that server-response event on CubicWeb is triggered
            events = 'CubicWeb';
        });
        jQuery('#qunit-fixture').loadxhtml(BASE_URL + 'cwsoftwareroot/web/test/jstests/ajax_url0.html')
        .addCallback(function() {
                try {
                    equal(events, 'CubicWeb');
                } finally {
                    start();
                };
            }
        );
    });

    QUnit.test('test event on node', function() {
        expect(3);
        stop();
        var nodes = [];
        jQuery('#qunit-fixture').bind('server-response', function() {
            nodes.push('node');
        });
        jQuery(CubicWeb).bind('server-response', function() {
            nodes.push('CubicWeb');
        });
        jQuery('#qunit-fixture').loadxhtml(BASE_URL + 'cwsoftwareroot/web/test/jstests/ajax_url0.html')
        .addCallback(function() {
                try {
                    equal(nodes.length, 2);
                    // check that server-response event on CubicWeb is triggered
                    // only once and event server-response on node is triggered
                    equal(nodes[0], 'CubicWeb');
                    equal(nodes[1], 'node');
                } finally {
                    start();
                };
            }
        );
    });
});

