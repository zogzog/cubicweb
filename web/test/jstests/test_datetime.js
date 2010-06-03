$(document).ready(function() {

  module("datetime tests");

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


});

