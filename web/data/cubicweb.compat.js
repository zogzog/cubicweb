cw.utils.movedToNamespace(['log', 'jqNode', 'getNode', 'evalJSON', 'urlEncode',
                           'swapDOM'], cw);
cw.utils.movedToNamespace(['nodeWalkDepthFirst', 'formContents', 'isArray',
                           'isString', 'isArrayLike', 'sliceList',
                           'toISOTimestamp'], cw.utils);


if ($.noop === undefined) {
    function noop() {}
} else {
    noop = cw.utils.deprecatedFunction(
        '[3.9] noop() is deprecated, use $.noop() instead (XXX requires jQuery 1.4)',
        $.noop);
}

// ========== ARRAY EXTENSIONS ========== ///
Array.prototype.contains = cw.utils.deprecatedFunction(
    '[3.9] array.contains(elt) is deprecated, use $.inArray(elt, array)!=-1 instead',
    function(element) {
        return jQuery.inArray(element, this) != - 1;
    }
);

// ========== END OF ARRAY EXTENSIONS ========== ///
forEach = cw.utils.deprecatedFunction(
    '[3.9] forEach() is deprecated, use $.each() instead',
    function(array, func) {
        return $.each(array, func);
    }
);

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
map = cw.utils.deprecatedFunction(
    '[3.9] map() is deprecated, use $.map instead',
    function(func, array) {
        var result = [];
        for (var i = 0, length = array.length; i < length; i++) {
            result.push(func(array[i]));
        }
        return result;
    }
);

findValue = cw.utils.deprecatedFunction(
    '[3.9] findValue(array, elt) is deprecated, use $.inArray(elt, array) instead',
    function(array, element) {
        return jQuery.inArray(element, array);
    }
);

filter = cw.utils.deprecatedFunction(
    '[3.9] filter(func, array) is deprecated, use $.grep(array, f) instead',
    function(func, array) {
        return $.grep(array, func);
    }
);

addElementClass = cw.utils.deprecatedFunction(
    '[3.9] addElementClass(node, cls) is deprecated, use $(node).addClass(cls) instead',
    function(node, klass) {
        $(node).addClass(klass);
    }
);

removeElementClass = cw.utils.deprecatedFunction(
    '[3.9] removeElementClass(node, cls) is deprecated, use $(node).removeClass(cls) instead',
    function(node, klass) {
        $(node).removeClass(klass);
    }
);

hasElementClass = cw.utils.deprecatedFunction(
    '[3.9] hasElementClass(node, cls) is deprecated, use $(node).hasClass(cls)',
    function(node, klass) {
        return $(node).hasClass(klass);
    }
);

getNodeAttribute = cw.utils.deprecatedFunction(
    '[3.9] getNodeAttribute(node, attr) is deprecated, use $(node).attr(attr)',
    function(node, attribute) {
        return $(node).attr(attribute);
    }
);

/**
 * The only known usage of KEYS is in the tag cube. Once cubicweb-tag 1.7.0 is out,
 * this current definition can be removed.
 */
var KEYS = {
    KEY_ESC: 27,
    KEY_ENTER: 13
};
