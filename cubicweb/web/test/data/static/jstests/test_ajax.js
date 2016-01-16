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

    QUnit.test('test simple h1 inclusion (ajax_url0.html)', function (assert) {
        assert.expect(3);
        assert.equal($('#qunit-fixture').children().length, 0);
        var done = assert.async();
        $('#qunit-fixture').loadxhtml('static/jstests/ajax_url0.html', null, 'GET')
        .addCallback(function() {
                try {
                    assert.equal($('#qunit-fixture').children().length, 1);
                    assert.equal($('#qunit-fixture h1').html(), 'Hello');
                } finally {
                    done();
                };
            }
        );
    });

    QUnit.test('test simple html head inclusion (ajax_url1.html)', function (assert) {
        assert.expect(6);
        var scriptsIncluded = jsSources();
        assert.equal(jQuery.inArray('http://foo.js', scriptsIncluded), - 1);
        var done = assert.async();
        $('#qunit-fixture').loadxhtml('static/jstests/ajax_url1.html', null, 'GET')
        .addCallback(function() {
                try {
                    var origLength = scriptsIncluded.length;
                    scriptsIncluded = jsSources();
                    // check that foo.js has been prepended to <head>
                    assert.equal(scriptsIncluded.length, origLength + 1);
                    assert.equal(scriptsIncluded.indexOf('http://foo.js'), 0);
                    // check that <div class="ajaxHtmlHead"> has been removed
                    assert.equal($('#qunit-fixture').children().length, 1);
                    assert.equal($('div.ajaxHtmlHead').length, 0);
                    assert.equal($('#qunit-fixture h1').html(), 'Hello');
                } finally {
                    done();
                };
            }
        );
    });

    QUnit.test('test addCallback', function (assert) {
        assert.expect(3);
        assert.equal($('#qunit-fixture').children().length, 0);
        var done = assert.async();
        var d = $('#qunit-fixture').loadxhtml('static/jstests/ajax_url0.html', null, 'GET');
        d.addCallback(function() {
            try {
                assert.equal($('#qunit-fixture').children().length, 1);
                assert.equal($('#qunit-fixture h1').html(), 'Hello');
            } finally {
                done();
            };
        });
    });

    QUnit.test('test callback after synchronous request', function (assert) {
        assert.expect(1);
        var deferred = new Deferred();
        var result = jQuery.ajax({
            url: 'static/jstests/ajax_url0.html',
            async: false,
            beforeSend: function(xhr) {
                deferred._req = xhr;
            },
            success: function(data, status) {
                deferred.success(data);
            }
        });
        var done = assert.async();
        deferred.addCallback(function() {
            try {
                // add an assertion to ensure the callback is executed
                assert.ok(true, "callback is executed");
            } finally {
                done();
            };
        });
    });

    QUnit.test('test addCallback with parameters', function (assert) {
        assert.expect(3);
        assert.equal($('#qunit-fixture').children().length, 0);
        var done = assert.async();
        var d = $('#qunit-fixture').loadxhtml('static/jstests/ajax_url0.html', null, 'GET');
        d.addCallback(function(data, req, arg1, arg2) {
            try {
                assert.equal(arg1, 'Hello');
                assert.equal(arg2, 'world');
            } finally {
                done();
            };
        },
        'Hello', 'world');
    });

    QUnit.test('test callback after synchronous request with parameters', function (assert) {
        assert.expect(3);
        var deferred = new Deferred();
        deferred.addCallback(function(data, req, arg1, arg2) {
            // add an assertion to ensure the callback is executed
            try {
                assert.ok(true, "callback is executed");
                assert.equal(arg1, 'Hello');
                assert.equal(arg2, 'world');
            } finally {
                done();
            };
        },
        'Hello', 'world');
        deferred.addErrback(function() {
            // throw an exception to start errback chain
            try {
                throw this._error;
            } finally {
                done();
            };
        });
        var done = assert.async();
        var result = jQuery.ajax({
            url: 'static/jstests/ajax_url0.html',
            async: false,
            beforeSend: function(xhr) {
                deferred._req = xhr;
            },
            success: function(data, status) {
                deferred.success(data);
            }
        });
    });

  QUnit.test('test addErrback', function (assert) {
        assert.expect(1);
        var done = assert.async();
        var d = $('#qunit-fixture').loadxhtml('static/jstests/nonexistent.html', null, 'GET');
        d.addCallback(function() {
            // should not be executed
            assert.ok(false, "callback is executed");
        });
        d.addErrback(function() {
            try {
                assert.ok(true, "errback is executed");
            } finally {
                done();
            };
        });
    });

    QUnit.test('test callback execution order', function (assert) {
        assert.expect(3);
        var counter = 0;
        var done = assert.async();
        var d = $('#qunit-fixture').loadxhtml('static/jstests/ajax_url0.html', null, 'GET');
        d.addCallback(function() {
            assert.equal(++counter, 1); // should be executed first
        });
        d.addCallback(function() {
            assert.equal(++counter, 2);
        });
        d.addCallback(function() {
            try {
                assert.equal(++counter, 3);
            } finally {
                done();
            }
        });
    });

    QUnit.test('test already included resources are ignored (ajax_url1.html)', function (assert) {
        assert.expect(10);
        var scriptsIncluded = jsSources();
        // NOTE:
        assert.equal(jQuery.inArray('http://foo.js', scriptsIncluded), -1);
        assert.equal($('head link').length, 1);
        /* use endswith because in pytest context we have an absolute path */
        assert.ok($('head link').attr('href').endswith('/qunit.css'), 'qunit.css is loaded');
        var done = assert.async();
        $('#qunit-fixture').loadxhtml('static/jstests/ajax_url1.html', null, 'GET')
        .addCallback(function() {
                var origLength = scriptsIncluded.length;
                scriptsIncluded = jsSources();
                try {
                    // check that foo.js has been inserted in <head>
                    assert.equal(scriptsIncluded.length, origLength + 1);
                    assert.equal(scriptsIncluded.indexOf('http://foo.js'), 0);
                    // check that <div class="ajaxHtmlHead"> has been removed
                    assert.equal($('#qunit-fixture').children().length, 1);
                    assert.equal($('div.ajaxHtmlHead').length, 0);
                    assert.equal($('#qunit-fixture h1').html(), 'Hello');
                    // qunit.css is not added twice
                    assert.equal($('head link').length, 1);
                    /* use endswith because in pytest context we have an absolute path */
                    assert.ok($('head link').attr('href').endswith('/qunit.css'), 'qunit.css is loaded');
                } finally {
                    done();
                }
            }
        );
    });

    QUnit.test('test synchronous request loadRemote', function (assert) {
        var res = loadRemote('static/jstests/ajaxresult.json', {},
        'GET', true);
        assert.deepEqual(res, ['foo', 'bar']);
    });

    QUnit.test('test event on CubicWeb', function (assert) {
        assert.expect(1);
        var done = assert.async();
        var events = null;
        $(CubicWeb).bind('server-response', function() {
            // check that server-response event on CubicWeb is triggered
            events = 'CubicWeb';
        });
        $('#qunit-fixture').loadxhtml('static/jstests/ajax_url0.html', null, 'GET')
        .addCallback(function() {
                try {
                    assert.equal(events, 'CubicWeb');
                } finally {
                    done();
                };
            }
        );
    });

    QUnit.test('test event on node', function (assert) {
        assert.expect(3);
        var done = assert.async();
        var nodes = [];
        $('#qunit-fixture').bind('server-response', function() {
            nodes.push('node');
        });
        $(CubicWeb).bind('server-response', function() {
            nodes.push('CubicWeb');
        });
        $('#qunit-fixture').loadxhtml('static/jstests/ajax_url0.html', null, 'GET')
        .addCallback(function() {
                try {
                    assert.equal(nodes.length, 2);
                    // check that server-response event on CubicWeb is triggered
                    // only once and event server-response on node is triggered
                    assert.equal(nodes[0], 'CubicWeb');
                    assert.equal(nodes[1], 'node');
                } finally {
                    done();
                };
            }
        );
    });
});

