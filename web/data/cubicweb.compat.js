/* MochiKit -> jQuery compatibility module */

function forEach(array, func) {
    for (var i=0, length=array.length; i<length; i++) {
	func(array[i]);
    }
}

function getElementsByTagAndClassName(tag, klass, root) {
    root = root || document;
    // FIXME root is not used in this compat implementation
    return jQuery(tag + '.' + klass);
}

function map(func, array) {
    // XXX jQUery tends to simplify lists with only one element :
    // >>> y = ['a:b:c']
    // >>> jQuery.map(y, function(y) { return y.split(':');})
    // ["a", "b", "c"]
    // where I would expect :
    // [ ["a", "b", "c"] ]
    // return jQuery.map(array, func);
    var result = [];
    for (var i=0,length=array.length;i<length;i++) {
	result.push(func(array[i]));
    }
    return result;
}

function findValue(array, element) {
    return jQuery.inArray(element, array);
}

function filter(func, array) {
    return jQuery.grep(array, func);
}

function noop() {}

function addElementClass(node, klass) {
    jQuery(node).addClass(klass);
}

function toggleElementClass(node, klass) {
    jQuery(node).toggleClass(klass);
}

function removeElementClass(node, klass) {
    jQuery(node).removeClass(klass);
}

hasElementClass = jQuery.className.has;


function partial(func) {
    var args = sliceList(arguments, 1);
    return function() {
	return func.apply(null, merge(args, arguments));
    };
}


function log() {
    // XXX dummy implementation
    // console.log.apply(arguments); ???
    var args = [];
    for (var i=0; i<arguments.length; i++) {
	args.push(arguments[i]);
    }
    if (typeof(window) != "undefined" && window.console
        && window.console.log) {
	window.console.log(args.join(' '));
    }
}

function getNodeAttribute(node, attribute) {
    return jQuery(node).attr(attribute);
}

function isArray(it){ // taken from dojo
    return it && (it instanceof Array || typeof it == "array");
}

function isString(it){ // taken from dojo
    return !!arguments.length && it != null && (typeof it == "string" || it instanceof String);
}


function isArrayLike(it) { // taken from dojo
    return (it && it !== undefined &&
	    // keep out built-in constructors (Number, String, ...) which have length
	    // properties
	    !isString(it) && !jQuery.isFunction(it) &&
	    !(it.tagName && it.tagName.toLowerCase() == 'form') &&
	    (isArray(it) || isFinite(it.length)));
}


function getNode(node) {
    if (typeof(node) == 'string') {
        return document.getElementById(node);
    }
    return node;
}

/* safe version of jQuery('#nodeid') because we use ':' in nodeids
 * which messes with jQuery selection mechanism
 */
function jqNode(node) {
    node = getNode(node);
    if (node) {
	return jQuery(node);
    }
    return null;
}

function evalJSON(json) { // trust source
    return eval("(" + json + ")");
}

function urlEncode(str) {
    if (typeof(encodeURIComponent) != "undefined") {
        return encodeURIComponent(str).replace(/\'/g, '%27');
    } else {
        return escape(str).replace(/\+/g, '%2B').replace(/\"/g,'%22').rval.replace(/\'/g, '%27');
    }
}

function swapDOM(dest, src) {
    dest = getNode(dest);
    var parent = dest.parentNode;
    if (src) {
        src = getNode(src);
        parent.replaceChild(src, dest);
    } else {
        parent.removeChild(dest);
    }
    return src;
}

function replaceChildNodes(node/*, nodes...*/) {
    var elem = getNode(node);
    arguments[0] = elem;
    var child;
    while ((child = elem.firstChild)) {
        elem.removeChild(child);
    }
    if (arguments.length < 2) {
        return elem;
    } else {
	for (var i=1; i<arguments.length; i++) {
	    elem.appendChild(arguments[i]);
	}
	return elem;
    }
}

update = jQuery.extend;


function createDomFunction(tag) {

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
		node.setAttribute(key, params[key]);
	    }
	}
	if (children) {
	    if (!isArrayLike(children)) {
		children = [children];
		for (var i=2; i<arguments.length; i++) {
		    var arg = arguments[i];
		    if (isArray(arg)) {
			children = merge(children, arg);
		    } else {
			children.push(arg);
		    }
		}
	    }
	    for (var i=0; i<children.length; i++) {
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
}

A = createDomFunction('a');
BUTTON = createDomFunction('button');
BR = createDomFunction('br');
CANVAS = createDomFunction('canvas');
DD = createDomFunction('dd');
DIV = createDomFunction('div');
DL = createDomFunction('dl');
DT = createDomFunction('dt');
FIELDSET = createDomFunction('fieldset');
FORM = createDomFunction('form');
H1 = createDomFunction('H1');
H2 = createDomFunction('H2');
H3 = createDomFunction('H3');
H4 = createDomFunction('H4');
H5 = createDomFunction('H5');
H6 = createDomFunction('H6');
HR = createDomFunction('hr');
IMG = createDomFunction('img');
INPUT = createDomFunction('input');
LABEL = createDomFunction('label');
LEGEND = createDomFunction('legend');
LI = createDomFunction('li');
OL = createDomFunction('ol');
OPTGROUP = createDomFunction('optgroup');
OPTION = createDomFunction('option');
P = createDomFunction('p');
PRE = createDomFunction('pre');
SELECT = createDomFunction('select');
SPAN = createDomFunction('span');
STRONG = createDomFunction('strong');
TABLE = createDomFunction('table');
TBODY = createDomFunction('tbody');
TD = createDomFunction('td');
TEXTAREA = createDomFunction('textarea');
TFOOT = createDomFunction('tfoot');
TH = createDomFunction('th');
THEAD = createDomFunction('thead');
TR = createDomFunction('tr');
TT = createDomFunction('tt');
UL = createDomFunction('ul');

// cubicweb specific
IFRAME = createDomFunction('iframe');

// dummy ultra minimalist implementation on deferred for jQuery
function Deferred() {
    this.__init__(this);
}

jQuery.extend(Deferred.prototype, {
    __init__: function() {
	this.onSuccess = [];
	this.onFailure = [];
	this.req = null;
    },

    addCallback: function(callback) {
	this.onSuccess.push([callback, sliceList(arguments, 1)]);
	return this;
    },

    addErrback: function(callback) {
	this.onFailure.push([callback, sliceList(arguments, 1)]);
	return this;
    },

    success: function(result) {
	try {
	    for (var i=0; i<this.onSuccess.length; i++) {
		var callback = this.onSuccess[i][0];
		var args = merge([result, this.req], this.onSuccess[i][1]);
		callback.apply(null, args);
	    }
	} catch (error) {
	    this.error(this.xhr, null, error);
	}
    },

    error: function(xhr, status, error) {
	for (var i=0; i<this.onFailure.length; i++) {
	    var callback = this.onFailure[i][0];
	    var args = merge([error, this.req], this.onFailure[i][1]);
	    callback.apply(null, args);
	}
    }

});


/** @id MochiKit.DateTime.toISOTime */
toISOTime = function (date, realISO/* = false */) {
    if (typeof(date) == "undefined" || date === null) {
        return null;
    }
    var hh = date.getHours();
    var mm = date.getMinutes();
    var ss = date.getSeconds();
    var lst = [
        ((realISO && (hh < 10)) ? "0" + hh : hh),
        ((mm < 10) ? "0" + mm : mm),
        ((ss < 10) ? "0" + ss : ss)
    ];
    return lst.join(":");
};

_padTwo = function (n) {
    return (n > 9) ? n : "0" + n;
};

/** @id MochiKit.DateTime.toISODate */
toISODate = function (date) {
    if (typeof(date) == "undefined" || date === null) {
        return null;
    }
    return [
        date.getFullYear(),
        _padTwo(date.getMonth() + 1),
        _padTwo(date.getDate())
    ].join("-");
};


/** @id MochiKit.DateTime.toISOTimeStamp */
toISOTimestamp = function (date, realISO/* = false*/) {
    if (typeof(date) == "undefined" || date === null) {
        return null;
    }
    var sep = realISO ? "T" : " ";
    var foot = realISO ? "Z" : "";
    if (realISO) {
        date = new Date(date.getTime() + (date.getTimezoneOffset() * 60000));
    }
    return toISODate(date) + sep + toISOTime(date, realISO) + foot;
};


function loadJSON(url, data, type, dataType) {
    d = new Deferred();
    jQuery.ajax({
	url: url,
	type: type,
	data: data,
	dataType: dataType,

	beforeSend: function(xhr) {
	    d.req = xhr;
	},

	success: function(data, status) {
	    d.success(data);
	},

	error: function(xhr, status, error) {
	    error = evalJSON(xhr.responseText);
	    d.error(xhr, status, error['reason']);
	}
    });
    return d;
}

/* depth-first implementation of the nodeWalk function found
 * in MochiKit.Base
 * cf. http://mochikit.com/doc/html/MochiKit/Base.html#fn-nodewalk
 */
function nodeWalkDepthFirst(node, visitor) {
    var children = visitor(node);
    if (children) {
	for(var i=0; i<children.length; i++) {
	    nodeWalkDepthFirst(children[i], visitor);
	}
    }
}


/* Returns true if all the given Array-like or string arguments are not empty (obj.length > 0) */
function isNotEmpty(obj) {
    for (var i = 0; i < arguments.length; i++) {
        var o = arguments[i];
        if (!(o && o.length)) {
            return false;
        }
    }
    return true;
}

/** this implementation comes from MochiKit  */
function formContents(elem/* = document.body */) {
    var names = [];
    var values = [];
    if (typeof(elem) == "undefined" || elem === null) {
        elem = document.body;
    } else {
        elem = getNode(elem);
    }
    nodeWalkDepthFirst(elem, function (elem) {
        var name = elem.name;
        if (isNotEmpty(name)) {
            var tagName = elem.tagName.toUpperCase();
            if (tagName === "INPUT"
                && (elem.type == "radio" || elem.type == "checkbox")
                && !elem.checked
               ) {
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
            if (tagName === "FORM" || tagName === "P" || tagName === "SPAN"
                || tagName === "DIV"
               ) {
                return elem.childNodes;
            }
            names.push(name);
            values.push(elem.value || '');
            return null;
        }
        return elem.childNodes;
    });
    return [names, values];
}

function merge(array1, array2) {
    var result = [];
    for (var i=0,length=arguments.length; i<length; i++) {
	var array = arguments[i];
	for (var j=0,alength=array.length; j<alength; j++) {
	    result.push(array[j]);
	}
    }
    return result;
}

var KEYS = {
    KEY_ESC: 27,
    KEY_ENTER: 13
}

// XHR = null;
// function test() {
//     var d = loadJSON('http://crater:9876/json?mode=remote&fname=i18n&pageid=xxx&arg=' + jQuery.toJSON(['modify']));
//     d = d.addCallback(function (result, xhr) {
// 	XHR = xhr;
// 	log('got ajax result 1' + result + xhr);
// 	log('got ajax result 1' + xhr);
// 	log('got ajax result 1' + xhr + 'arguments =', arguments.length);
//     });
//     d.addCallback(function (x, req, y, z) {
// 	log('callback 2 x =' + x, ' req=', req, 'y =', y, 'z=',z);
//     }, 12, 13)
//     d.addErrback(function (error, xhr) {
// 	XHR = xhr;
// 	log('got err', error, ' code =', xhr.status, 'arguments length=', arguments.length);
//     })
// }

