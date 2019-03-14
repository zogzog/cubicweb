/**
 * .. function:: cw.utils.deprecatedFunction(msg, function)
 *
 * jQUery flattens arrays returned by the mapping function: ::
 *
 *   >>> y = ['a:b:c', 'd:e']
 *   >>> jQuery.map(y, function(y) { return y.split(':');})
 *   ["a", "b", "c", "d", "e"]
 *   // where one would expect:
 *   [ ["a", "b", "c"], ["d", "e"] ]
 */
 // XXX why not the same argument order as $.map and forEach ?

function map(func, array) {
    var result = [];
    for (var i = 0, length = array.length; i < length; i++) {
        result.push(func(array[i]));
    }
    return result;
}
