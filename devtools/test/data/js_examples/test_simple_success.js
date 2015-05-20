$(document).ready(function() {

  QUnit.module("air");

  QUnit.test("test 1", function (assert) {
      assert.equal(2, 2);
  });

  QUnit.test("test 2", function (assert) {
      assert.equal('45', '45');
  });

  QUnit.module("able");
  QUnit.test("test 3", function (assert) {
      assert.deepEqual(1, 1);
  });
});
