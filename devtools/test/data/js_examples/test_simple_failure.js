$(document).ready(function() {

  module("air");

  test("test 1", function() {
      equal(2, 4);
  });

  test("test 2", function() {
      equal('', '45');
      equal('1024', '32');
  });

  module("able");
  test("test 3", function() {
      deepEqual(1, 1);
  });
});
