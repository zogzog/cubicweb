$(document).ready(function() {

  module("datetime");

  test("test full datetime", function() {
      equals(cw.utils.toISOTimestamp(new Date(1986, 3, 18, 10, 30, 0, 0)),
	     '1986-04-18 10:30:00');
  });

  test("test only date", function() {
      equals(cw.utils.toISOTimestamp(new Date(1986, 3, 18)), '1986-04-18 00:00:00');
  });

  test("test null", function() {
      equals(cw.utils.toISOTimestamp(null), null);
  });

  module("parsing");
  test("test basic number parsing", function() {
      var d = strptime('2008/08/08', '%Y/%m/%d');
      same(datetuple(d), [2008, 8, 8, 0, 0]);
      d = strptime('2008/8/8', '%Y/%m/%d');
      same(datetuple(d), [2008, 8, 8, 0, 0]);
      d = strptime('8/8/8', '%Y/%m/%d');
      same(datetuple(d), [8, 8, 8, 0, 0]);
      d = strptime('0/8/8', '%Y/%m/%d');
      same(datetuple(d), [0, 8, 8, 0, 0]);
      d = strptime('-10/8/8', '%Y/%m/%d');
      same(datetuple(d), [-10, 8, 8, 0, 0]);
      d = strptime('-35000', '%Y');
      same(datetuple(d), [-35000, 1, 1, 0, 0]);
  });

  test("test custom format parsing", function() {
      var d = strptime('2008-08-08', '%Y-%m-%d');
      same(datetuple(d), [2008, 8, 8, 0, 0]);
      d = strptime('2008 - !  08: 08', '%Y - !  %m: %d');
      same(datetuple(d), [2008, 8, 8, 0, 0]);
      d = strptime('2008-08-08 12:14', '%Y-%m-%d %H:%M');
      same(datetuple(d), [2008, 8, 8, 12, 14]);
      d = strptime('2008-08-08 1:14', '%Y-%m-%d %H:%M');
      same(datetuple(d), [2008, 8, 8, 1, 14]);
      d = strptime('2008-08-08 01:14', '%Y-%m-%d %H:%M');
      same(datetuple(d), [2008, 8, 8, 1, 14]);
  });

  module("sliceList");
  test("test slicelist", function() {
      var list = ['a', 'b', 'c', 'd', 'e', 'f'];
      same(cw.utils.sliceList(list, 2),  ['c', 'd', 'e', 'f']);
      same(cw.utils.sliceList(list, 2, -2), ['c', 'd']);
      same(cw.utils.sliceList(list, -3), ['d', 'e', 'f']);
      same(cw.utils.sliceList(list, 0, -2), ['a', 'b', 'c', 'd']);
      same(cw.utils.sliceList(list),  list);
  });

  module("formContents", {
    setup: function() {
      $('#main').append('<form id="test-form"></form>');
    }
  });
  // XXX test fckeditor
  test("test formContents", function() {
      $('#test-form').append('<input name="input-text" ' +
			     'type="text" value="toto" />');
      $('#test-form').append('<textarea rows="10" cols="30" '+
			     'name="mytextarea">Hello World!</textarea> ');
      $('#test-form').append('<input name="choice" type="radio" ' +
			     'value="yes" />');
      $('#test-form').append('<input name="choice" type="radio" ' +
			     'value="no" checked="checked"/>');
      $('#test-form').append('<input name="check" type="checkbox" ' +
			     'value="yes" />');
      $('#test-form').append('<input name="check" type="checkbox" ' +
			     'value="no" checked="checked"/>');
      $('#test-form').append('<select id="theselect" name="theselect" ' +
			     'multiple="multiple" size="2"></select>');
      $('#theselect').append('<option selected="selected" ' +
			     'value="foo">foo</option>' +
  			     '<option value="bar">bar</option>');
      //Append an unchecked radio input : should not be in formContents list
      $('#test-form').append('<input name="unchecked-choice" type="radio" ' +
			     'value="one" />');
      $('#test-form').append('<input name="unchecked-choice" type="radio" ' +
			     'value="two"/>');
      same(cw.utils.formContents($('#test-form')[0]), [
	['input-text', 'mytextarea', 'choice', 'check', 'theselect'],
	['toto', 'Hello World!', 'no', 'no', 'foo']
      ]);
  });
});

