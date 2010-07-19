$(document).ready(function() {

  module("air");

  test("test 1", function() {
      equals(2, 4);
  });

  test("test 2", function() {
      equals('', '45');
      equals('1024', '32');
  });

  module("able");
  test("test 3", function() {
      same(1, 1);
  });
});
