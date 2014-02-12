
function Namespace(name) {
   this.__name__ = name;
}

cw = new Namespace('cw');

jQuery.extend(cw, {
    cubes: new Namespace('cubes'),
    /* provide a removeEventListener / detachEvent definition to
     * to bypass a jQuery 1.4.2 bug when unbind() is called on a
     * plain JS object and not a DOM node.
     * see http://dev.jquery.com/ticket/6184 for more details
     */
    removeEventListener: function() {},
    detachEvent: function() {},

    log: function () {
        var args = [];
        for (var i = 0; i < arguments.length; i++) {
            args.push(arguments[i]);
        }
        if (typeof(window) != "undefined" && window.console && window.console.log) {
            window.console.log(args.join(' '));
        }
    },

    //removed: getElementsByTagAndClassName, replaceChildNodes, toggleElementClass
    //         partial, merge, isNotEmpty, update,
    //         String.in_, String.join, list, getattr, attrgetter, methodcaller,
    //         min, max, dict, concat
    jqNode: function (node) {
    /**
     * .. function:: jqNode(node)
     *
     * safe version of jQuery('#nodeid') because we use ':' in nodeids
     * which messes with jQuery selection mechanism
     */
        if (typeof(node) == 'string') {
            node = document.getElementById(node);
        }
        if (node) {
            return $(node);
        }
        return null;
    },

    // escapes string selectors (e.g. "foo.[subject]:42" -> "foo\.\[subject\]\:42"
    escape: function(selector) {
        if (typeof(selector) == 'string') {
            return  selector.replace( /(:|\.|\[|\])/g, "\\$1" );
        }
        // cw.log('non string selector', selector);
        return '';
    },

    getNode: function (node) {
        if (typeof(node) == 'string') {
            return document.getElementById(node);
        }
        return node;
    },

    evalJSON: function (json) { // trust source
        try {
            return eval("(" + json + ")");
        } catch(e) {
          cw.log(e);
          cw.log('The faulty json source was', json);
          throw (e);
       }
    },

    urlEncode: function (str) {
        if (typeof(encodeURIComponent) != "undefined") {
            return encodeURIComponent(str).replace(/\'/g, '%27');
        } else {
            return escape(str).replace(/\+/g, '%2B').replace(/\"/g, '%22').
                    rval.replace(/\'/g, '%27');
        }
    },

    swapDOM: function (dest, src) {
        dest = cw.getNode(dest);
        var parent = dest.parentNode;
        if (src) {
            src = cw.getNode(src);
            parent.replaceChild(src, dest);
        } else {
            parent.removeChild(dest);
        }
        return src;
    },

    sortValueExtraction: function (node) {
        var $node = $(node);
        var sortvalue = $node.attr('cubicweb:sortvalue');
        // No metadata found, use cell content as sort key
        if (sortvalue === undefined) {
            return $node.text();
        }
        return cw.evalJSON(sortvalue);
    }
});


cw.utils = new Namespace('cw.utils');
jQuery.extend(cw.utils, {

    deprecatedFunction: function (msg, newfunc) {
        return function () {
            cw.log(msg);
            return newfunc.apply(this, arguments);
        };
    },

    createDomFunction: function (tag) {
        function builddom(params, children) {
            var node = document.createElement(tag);
            for (key in params) {
                var value = params[key];
                if (key.substring(0, 2) == 'on') {
                    // this is an event handler definition
                    if (typeof value == 'string') {
                        // litteral definition
                        value = new Function(value);
                    }
                    node[key] = value;
                } else { // normal node attribute
                    jQuery(node).attr(key, params[key]);
                }
            }
            if (children) {
                if (!cw.utils.isArrayLike(children)) {
                    children = [children];
                    for (var i = 2; i < arguments.length; i++) {
                        var arg = arguments[i];
                        if (cw.utils.isArray(arg)) {
                            jQuery.merge(children, arg);
                        } else {
                            children.push(arg);
                        }
                    }
                }
                for (var i = 0; i < children.length; i++) {
                    var child = children[i];
                    if (typeof child == "string" || typeof child == "number") {
                        child = document.createTextNode(child);
                    }
                    node.appendChild(child);
                }
            }
            return node;
        }
        return builddom;
    },

    /**
     * .. function:: toISOTimestamp(date)
     *
     */
    toISOTimestamp: function (date) {
        if (typeof(date) == "undefined" || date === null) {
            return null;
        }

        function _padTwo(n) {
            return (n > 9) ? n : "0" + n;
        }
        var isoTime = [_padTwo(date.getHours()), _padTwo(date.getMinutes()),
                       _padTwo(date.getSeconds())].join(':');
        var isoDate = [date.getFullYear(), _padTwo(date.getMonth() + 1),
                       _padTwo(date.getDate())].join("-");
        return isoDate + " " + isoTime;
    },

    /**
     * .. function:: nodeWalkDepthFirst(node, visitor)
     *
     * depth-first implementation of the nodeWalk function found
     * in `MochiKit.Base <http://mochikit.com/doc/html/MochiKit/Base.html#fn-nodewalk>`_
     */
    nodeWalkDepthFirst: function (node, visitor) {
        var children = visitor(node);
        if (children) {
            for (var i = 0; i < children.length; i++) {
                cw.utils.nodeWalkDepthFirst(children[i], visitor);
            }
        }
    },

    isArray: function (it) { // taken from dojo
        return it && (it instanceof Array || typeof it == "array");
    },

    isString: function (it) { // taken from dojo
        return !!arguments.length && it != null && (typeof it == "string" || it instanceof String);
    },

    isArrayLike: function (it) { // taken from dojo
        return (it && it !== undefined &&
                // keep out built-in constructors (Number, String, ...)
                // which have length properties
                !cw.utils.isString(it) && !jQuery.isFunction(it) &&
                !(it.tagName && it.tagName.toLowerCase() == 'form') &&
                (cw.utils.isArray(it) || isFinite(it.length)));
    },

    /**
     * .. function:: formContents(elem \/* = document.body *\/)
     *
     * this implementation comes from MochiKit
     */
    formContents: function (elem /* = document.body */ ) {
        var names = [];
        var values = [];
        if (typeof(elem) == "undefined" || elem === null) {
            elem = document.body;
        } else {
            elem = cw.getNode(elem);
        }
        cw.utils.nodeWalkDepthFirst(elem, function (elem) {
            var name = elem.name;
            if (name && name.length) {
                if (elem.disabled) {
                    return null;
                }
                var tagName = elem.tagName.toUpperCase();
                if (tagName === "INPUT" && (elem.type == "radio" || elem.type == "checkbox") && !elem.checked) {
                    return null;
                }
                if (tagName === "SELECT") {
                    if (elem.type == "select-one") {
                        if (elem.selectedIndex >= 0) {
                            var opt = elem.options[elem.selectedIndex];
                            var v = opt.value;
                            if (!v) {
                                var h = opt.outerHTML;
                                // internet explorer sure does suck.
                                if (h && !h.match(/^[^>]+\svalue\s*=/i)) {
                                    v = opt.text;
                                }
                            }
                            names.push(name);
                            values.push(v);
                            return null;
                        }
                        // no form elements?
                        names.push(name);
                        values.push("");
                        return null;
                    } else {
                        var opts = elem.options;
                        if (!opts.length) {
                            names.push(name);
                            values.push("");
                            return null;
                        }
                        for (var i = 0; i < opts.length; i++) {
                            var opt = opts[i];
                            if (!opt.selected) {
                                continue;
                            }
                            var v = opt.value;
                            if (!v) {
                                var h = opt.outerHTML;
                                // internet explorer sure does suck.
                                if (h && !h.match(/^[^>]+\svalue\s*=/i)) {
                                    v = opt.text;
                                }
                            }
                            names.push(name);
                            values.push(v);
                        }
                        return null;
                    }
                }
                if (tagName === "FORM" || tagName === "P" || tagName === "SPAN" || tagName === "DIV") {
                    return elem.childNodes;
                }
		var value = elem.value;
		if (tagName === "TEXTAREA") {
		    if (typeof(FCKeditor) != 'undefined') {
			var fck = FCKeditorAPI.GetInstance(elem.id);
			if (fck) {
			    value = fck.GetHTML();
			}
		    }
		}
                names.push(name);
                values.push(value || '');
                return null;
            }
            return elem.childNodes;
        });
        return [names, values];
    },

    /**
     * .. function:: sliceList(lst, start, stop, step)
     *
     * returns a subslice of `lst` using `start`/`stop`/`step`
     * start, stop might be negative
     *
     * >>> sliceList(['a', 'b', 'c', 'd', 'e', 'f'], 2)
     * ['c', 'd', 'e', 'f']
     * >>> sliceList(['a', 'b', 'c', 'd', 'e', 'f'], 2, -2)
     * ['c', 'd']
     * >>> sliceList(['a', 'b', 'c', 'd', 'e', 'f'], -3)
     * ['d', 'e', 'f']
     */
    sliceList: function (lst, start, stop, step) {
        start = start || 0;
        stop = stop || lst.length;
        step = step || 1;
        if (stop < 0) {
            stop = Math.max(lst.length + stop, 0);
        }
        if (start < 0) {
            start = Math.min(lst.length + start, lst.length);
        }
        var result = [];
        for (var i = start; i < stop; i += step) {
            result.push(lst[i]);
        }
        return result;
    },

    /**
     * returns the last element of an array-like object or undefined if empty
     */
    lastOf: function(array) {
        if (array.length) {
            return array[array.length-1];
        } else {
            return undefined;
        }
    },


    /**
     * .. function:: extend(array1, array2)
     *
     * equivalent of python ``+=`` statement on lists (array1 += array2)
     */
    extend: function(array1, array2) {
        array1.push.apply(array1, array2);
        return array1; // return array1 for convenience
    },

    /**
     * .. function:: difference(lst1, lst2)
     *
     * returns a list containing all elements in `lst1` that are not
     * in `lst2`.
     */
    difference: function(lst1, lst2) {
        return jQuery.grep(lst1, function(elt, i) {
            return jQuery.inArray(elt, lst2) == -1;
        });
    },
    /**
     * .. function:: domid(string)
     *
     * return a valid DOM id from a string (should also be usable in jQuery
     * search expression...). This is the javascript implementation of
     * :func:`cubicweb.uilib.domid`.
     */
    domid: function (string) {
	var newstring = string.replace(".", "_").replace("-", "_");
	while (newstring != string) {
	    string = newstring;
	    newstring = newstring.replace(".", "_").replace("-", "_");
	}
	return newstring; // XXX
    },

    /**
     * .. function:: strFuncCall(fname, *args)
     *
     * return a string suitable to call the `fname` javascript function with the
     * given arguments (which should be correctly typed).. This is providing
     * javascript implementation equivalent to :func:`cubicweb.uilib.js`.
     */
    strFuncCall: function(fname /* ...*/) {
	    return (fname + '(' +
		    $.map(cw.utils.sliceList(arguments, 1), jQuery.toJSON).join(',')
		    + ')'
		    );
    }

});

/** DOM factories ************************************************************/
A = cw.utils.createDomFunction('a');
BUTTON = cw.utils.createDomFunction('button');
BR = cw.utils.createDomFunction('br');
CANVAS = cw.utils.createDomFunction('canvas');
DD = cw.utils.createDomFunction('dd');
DIV = cw.utils.createDomFunction('div');
DL = cw.utils.createDomFunction('dl');
DT = cw.utils.createDomFunction('dt');
FIELDSET = cw.utils.createDomFunction('fieldset');
FORM = cw.utils.createDomFunction('form');
H1 = cw.utils.createDomFunction('H1');
H2 = cw.utils.createDomFunction('H2');
H3 = cw.utils.createDomFunction('H3');
H4 = cw.utils.createDomFunction('H4');
H5 = cw.utils.createDomFunction('H5');
H6 = cw.utils.createDomFunction('H6');
HR = cw.utils.createDomFunction('hr');
IMG = cw.utils.createDomFunction('img');
INPUT = cw.utils.createDomFunction('input');
LABEL = cw.utils.createDomFunction('label');
LEGEND = cw.utils.createDomFunction('legend');
LI = cw.utils.createDomFunction('li');
OL = cw.utils.createDomFunction('ol');
OPTGROUP = cw.utils.createDomFunction('optgroup');
OPTION = cw.utils.createDomFunction('option');
P = cw.utils.createDomFunction('p');
PRE = cw.utils.createDomFunction('pre');
SELECT = cw.utils.createDomFunction('select');
SPAN = cw.utils.createDomFunction('span');
STRONG = cw.utils.createDomFunction('strong');
TABLE = cw.utils.createDomFunction('table');
TBODY = cw.utils.createDomFunction('tbody');
TD = cw.utils.createDomFunction('td');
TEXTAREA = cw.utils.createDomFunction('textarea');
TFOOT = cw.utils.createDomFunction('tfoot');
TH = cw.utils.createDomFunction('th');
THEAD = cw.utils.createDomFunction('thead');
TR = cw.utils.createDomFunction('tr');
TT = cw.utils.createDomFunction('tt');
UL = cw.utils.createDomFunction('ul');

// cubicweb specific
//IFRAME = cw.utils.createDomFunction('iframe');


function IFRAME(params) {
    if ('name' in params) {
        try {
            var node = document.createElement('<iframe name="' + params['name'] + '">');
        } catch (ex) {
            var node = document.createElement('iframe');
            node.id = node.name = params.name;
        }
    }
    else {
        var node = document.createElement('iframe');
    }
    for (key in params) {
        if (key != 'name') {
            var value = params[key];
            if (key.substring(0, 2) == 'on') {
                // this is an event handler definition
                if (typeof value == 'string') {
                    // litteral definition
                    value = new Function(value);
                }
                node[key] = value;
            } else { // normal node attribute
                node.setAttribute(key, params[key]);
            }
        }
    }
    return node;
}

// cubes: tag, keyword and apycot seem to use this, including require/provide
// backward compat
CubicWeb = cw;

jQuery.extend(cw, {
    require: cw.utils.deprecatedFunction(
        '[3.9] CubicWeb.require() is not used anymore',
        function(module) {}),
    provide: cw.utils.deprecatedFunction(
        '[3.9] CubicWeb.provide() is not used anymore',
        function(module) {})
});

jQuery(document).ready(function() {
    $(cw).trigger('server-response', [false, document]);
});
