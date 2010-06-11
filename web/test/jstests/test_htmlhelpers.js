$(document).ready(function() {

    module("module2", {
      setup: function() {
        $('#main').append('<select id="theselect" multiple="multiple" size="2">' +
    			'</select>');
      }
    });

    test("test first selected", function() {
        $('#theselect').append('<option value="foo">foo</option>' +
    			     '<option selected="selected" value="bar">bar</option>' +
    			     '<option value="baz">baz</option>' +
    			     '<option selected="selecetd"value="spam">spam</option>');
        var selected = firstSelected(document.getElementById("theselect"));
        equals(selected.value, 'bar');
    });

    test("test first selected 2", function() {
        $('#theselect').append('<option value="foo">foo</option>' +
    			     '<option value="bar">bar</option>' +
    			     '<option value="baz">baz</option>' +
    			     '<option value="spam">spam</option>');
        var selected = firstSelected(document.getElementById("theselect"));
        equals(selected, null);
    });

    module("visibilty");
    test('toggleVisibility', function() {
        $('#main').append('<div id="foo"></div>');
        toggleVisibility('foo');
        ok($('#foo').hasClass('hidden'), 'check hidden class is set');
    });

});

