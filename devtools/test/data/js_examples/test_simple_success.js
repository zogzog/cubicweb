$(document).ready(function() {

  module("air");

  test("test 1", function() {
      equals(2, 2);
  });

  test("test 2", function() {
      equals('45', '45');
  });

  module("able");
  test("test 3", function() {
      same(1, 1);
  });
});
