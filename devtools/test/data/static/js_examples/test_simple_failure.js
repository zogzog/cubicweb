$(document).ready(function() {

  QUnit.module("air");

  QUnit.test("test 1", function (assert) {
      assert.equal(2, 4);
  });

  QUnit.test("test 2", function (assert) {
      assert.equal('', '45');
      assert.equal('1024', '32');
  });

  QUnit.module("able");
  QUnit.test("test 3", function (assert) {
      assert.deepEqual(1, 1);
  });
});
