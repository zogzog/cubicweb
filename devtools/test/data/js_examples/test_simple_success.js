$(document).ready(function() {

  module("air");

  test("test 1", function() {
      equal(2, 2);
  });

  test("test 2", function() {
      equal('45', '45');
  });

  module("able");
  test("test 3", function() {
      deepEqual(1, 1);
  });
});
