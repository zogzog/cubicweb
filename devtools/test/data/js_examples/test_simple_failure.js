$(document).ready(function() {

  QUnit.module("air");

  QUnit.test("test 1", function() {
      equal(2, 4);
  });

  QUnit.test("test 2", function() {
      equal('', '45');
      equal('1024', '32');
  });

  QUnit.module("able");
  QUnit.test("test 3", function() {
      deepEqual(1, 1);
  });
});
