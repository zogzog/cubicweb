$(document).ready(function() {

    QUnit.module("module2", {
      setup: function() {
        $('#qunit-fixture').append('<select id="theselect" multiple="multiple" size="2">' +
    			'</select>');
      }
    });

    QUnit.test("test first selected", function (assert) {
        $('#theselect').append('<option value="foo">foo</option>' +
    			     '<option selected="selected" value="bar">bar</option>' +
    			     '<option value="baz">baz</option>' +
    			     '<option selected="selecetd"value="spam">spam</option>');
        var selected = firstSelected(document.getElementById("theselect"));
        assert.equal(selected.value, 'bar');
    });

    QUnit.test("test first selected 2", function (assert) {
        $('#theselect').append('<option value="foo">foo</option>' +
    			     '<option value="bar">bar</option>' +
    			     '<option value="baz">baz</option>' +
    			     '<option value="spam">spam</option>');
        var selected = firstSelected(document.getElementById("theselect"));
        assert.equal(selected, null);
    });

    QUnit.module("visibilty");
    QUnit.test('toggleVisibility', function (assert) {
        $('#qunit-fixture').append('<div id="foo"></div>');
        toggleVisibility('foo');
        assert.ok($('#foo').hasClass('hidden'), 'check hidden class is set');
    });

});

