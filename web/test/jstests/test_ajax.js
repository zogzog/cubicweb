$(document).ready(function() {

    module("ajax", {
        setup: function() {
          this.scriptsLength = $('head script[src]').length-1;
          this.cssLength = $('head link[rel=stylesheet]').length-1;
          // re-initialize cw loaded cache so that each tests run in a
          // clean environment, have a lookt at _loadAjaxHtmlHead implementation
          // in cubicweb.ajax.js for more information.
          cw.loaded_src = [];
          cw.loaded_href = [];
        },
        teardown: function() {
          $('head script[src]:gt(' + this.scriptsLength + ')').remove();
          $('head link[rel=stylesheet]:gt(' + this.cssLength + ')').remove();
        }
      });

    function jsSources() {
        return $.map($('head script[src]'), function(script) {
            return script.getAttribute('src');
        });
    }

    test('test simple h1 inclusion (ajax_url0.html)', function() {
        expect(3);
        equals(jQuery('#main').children().length, 0);
        stop();
        jQuery('#main').loadxhtml('/../ajax_url0.html', {
            callback: function() {
                try {
                    equals(jQuery('#main').children().length, 1);
                    equals(jQuery('#main h1').html(), 'Hello');
                } finally {
                    start();
                };
            }
        });
    });

    test('test simple html head inclusion (ajax_url1.html)', function() {
        expect(6);
        var scriptsIncluded = jsSources();
        equals(jQuery.inArray('http://foo.js', scriptsIncluded), - 1);
        stop();
        jQuery('#main').loadxhtml('/../ajax_url1.html', {
            callback: function() {
                try {
                    var origLength = scriptsIncluded.length;
                    scriptsIncluded = jsSources();
                    // check that foo.js has been *appended* to <head>
                    equals(scriptsIncluded.length, origLength + 1);
                    equals(scriptsIncluded[origLength].indexOf('http://foo.js'), 0);
                    // check that <div class="ajaxHtmlHead"> has been removed
                    equals(jQuery('#main').children().length, 1);
                    equals(jQuery('div.ajaxHtmlHead').length, 0);
                    equals(jQuery('#main h1').html(), 'Hello');
                } finally {
                    start();
                };
            }
        });
    });

    test('test addCallback', function() {
        expect(3);
        equals(jQuery('#main').children().length, 0);
        stop();
        var d = jQuery('#main').loadxhtml('/../ajax_url0.html');
        d.addCallback(function() {
            try {
                equals(jQuery('#main').children().length, 1);
                equals(jQuery('#main h1').html(), 'Hello');
            } finally {
                start();
            };
        });
    });

    test('test callback after synchronous request', function() {
        expect(1);
        var deferred = new Deferred();
        var result = jQuery.ajax({
            url: './ajax_url0.html',
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

    test('test addCallback with parameters', function() {
        expect(3);
        equals(jQuery('#main').children().length, 0);
        stop();
        var d = jQuery('#main').loadxhtml('/../ajax_url0.html');
        d.addCallback(function(data, req, arg1, arg2) {
            try {
                equals(arg1, 'Hello');
                equals(arg2, 'world');
            } finally {
                start();
            };
        },
        'Hello', 'world');
    });

    test('test callback after synchronous request with parameters', function() {
        expect(2);
        var deferred = new Deferred();
        deferred.addCallback(function(data, req, arg1, arg2) {
            // add an assertion to ensure the callback is executed
            try {
                ok(true, "callback is executed");
                equals(arg1, 'Hello');
                equals(arg2, 'world');
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
            url: '/../ajax_url0.html',
            async: false,
            beforeSend: function(xhr) {
                deferred._req = xhr;
            },
            success: function(data, status) {
                deferred.success(data);
            }
        });
    });

  test('test addErrback', function() {
        expect(1);
        stop();
        var d = jQuery('#main').loadxhtml('/../ajax_url0.html');
        d.addCallback(function() {
            // throw an exception to start errback chain
            try {
                throw new Error();
            } finally {
                start();
            };
        });
        d.addErrback(function() {
            try {
                ok(true, "errback is executed");
            } finally {
                start();
            };
        });
    });

    test('test callback / errback execution order', function() {
        expect(4);
        var counter = 0;
        stop();
        var d = jQuery('#main').loadxhtml('/../ajax_url0.html', {
            callback: function() {
                try {
                    equals(++counter, 1); // should be executed first
                } finally {
                    start();
                };
            }
        });
        d.addCallback(function() {
            equals(++counter, 2); // should be executed and break callback chain
            throw new Error();
        });
        d.addCallback(function() {
            // should not be executed since second callback raised an error
            ok(false, "callback is executed");
        });
        d.addErrback(function() {
            // should be executed after the second callback
            equals(++counter, 3);
        });
        d.addErrback(function() {
            // should be executed after the first errback
            equals(++counter, 4);
        });
    });

    test('test already included resources are ignored (ajax_url1.html)', function() {
        expect(10);
        var scriptsIncluded = jsSources();
        // NOTE:
        equals(jQuery.inArray('http://foo.js', scriptsIncluded), -1);
        equals(jQuery('head link').length, 1);
        /* use endswith because in pytest context we have an absolute path */
        ok(jQuery('head link').attr('href').endswith('/qunit.css'));
        stop();
        jQuery('#main').loadxhtml('/../ajax_url1.html', {
            callback: function() {
                var origLength = scriptsIncluded.length;
                scriptsIncluded = jsSources();
                try {
                    // check that foo.js has been inserted in <head>
                    equals(scriptsIncluded.length, origLength + 1);
                    equals(scriptsIncluded[origLength].indexOf('http://foo.js'), 0);
                    // check that <div class="ajaxHtmlHead"> has been removed
                    equals(jQuery('#main').children().length, 1);
                    equals(jQuery('div.ajaxHtmlHead').length, 0);
                    equals(jQuery('#main h1').html(), 'Hello');
                    // qunit.css is not added twice
                    equals(jQuery('head link').length, 1);
                    /* use endswith because in pytest context we have an absolute path */
                    ok(jQuery('head link').attr('href').endswith('/qunit.css'));
                } finally {
                    start();
                }
            }
        });
    });

    test('test synchronous request loadRemote', function() {
        var res = loadRemote('/../ajaxresult.json', {},
        'GET', true);
        same(res, ['foo', 'bar']);
    });

    test('test event on CubicWeb', function() {
        expect(1);
        stop();
        var events = null;
        jQuery(CubicWeb).bind('server-response', function() {
            // check that server-response event on CubicWeb is triggered
            events = 'CubicWeb';
        });
        jQuery('#main').loadxhtml('/../ajax_url0.html', {
            callback: function() {
                try {
                    equals(events, 'CubicWeb');
                } finally {
                    start();
                };
            }
        });
    });

    test('test event on node', function() {
        expect(3);
        stop();
        var nodes = [];
        jQuery('#main').bind('server-response', function() {
            nodes.push('node');
        });
        jQuery(CubicWeb).bind('server-response', function() {
            nodes.push('CubicWeb');
        });
        jQuery('#main').loadxhtml('/../ajax_url0.html', {
            callback: function() {
                try {
                    equals(nodes.length, 2);
                    // check that server-response event on CubicWeb is triggered
                    // only once and event server-response on node is triggered
                    equals(nodes[0], 'CubicWeb');
                    equals(nodes[1], 'node');
                } finally {
                    start();
                };
            }
        });
    });
});

