/*
 * This file contains extensions for standard javascript types
 *
 */

ONE_DAY = 86400000; // (in milliseconds)

// ========== DATE EXTENSIONS ========== ///

Date.prototype.equals = function(other) {
    /* compare with other date ignoring time differences */
    if (this.getYear() == other.getYear() &&
	this.getMonth() == other.getMonth() &&
	this.getDate() == other.getDate()) {
	return true;
    }
    return false;
};

Date.prototype.add = function(days) {
    var res = new Date();
    res.setTime(this.getTime() + (days * ONE_DAY));
    return res;
};

Date.prototype.sub = function(days) {
    return this.add(-days);
};

Date.prototype.iadd = function(days) {
    // in-place add
    this.setTime(this.getTime() + (days * ONE_DAY));
    // avoid strange rounding problems !!
    this.setHours(12);
};

Date.prototype.isub = function(days) {
    // in-place sub
    this.setTime(this.getTime() - (days * ONE_DAY));
};

/*
 * returns the first day of the next month
 */
Date.prototype.nextMonth = function() {
    if (this.getMonth() == 11) {
	var d =new Date(this.getFullYear()+1, 0, 1);
	return d;
    } else {
	var d2 = new Date(this.getFullYear(), this.getMonth()+1, 1);
	return d2;
    }
};

/*
 * returns the day of week, 0 being monday, 6 being sunday
 */
Date.prototype.getRealDay = function() {
    // getDay() returns 0 for Sunday ==> 6 for Saturday
    return (this.getDay()+6) % 7;
};

Date.prototype.strftime = function(fmt) {
    if (this.toLocaleFormat !== undefined) { // browser dependent
	return this.toLocaleFormat(fmt);
    }
    // XXX implement at least a decent fallback implementation
    return this.getFullYear() + '/' + (this.getMonth()+1) + '/' + this.getDate();
};

var _DATE_FORMAT_REGXES = {
    'Y': new RegExp('^-?[0-9]+'),
    'd': new RegExp('^[0-9]{1,2}'),
    'm': new RegExp('^[0-9]{1,2}'),
    'H': new RegExp('^[0-9]{1,2}'),
    'M': new RegExp('^[0-9]{1,2}')
}

/*
 * _parseData does the actual parsing job needed by `strptime`
 */
function _parseDate(datestring, format) {
    var skip0 = new RegExp('^0*[0-9]+');
    var parsed = {};
    for (var i1=0,i2=0;i1<format.length;i1++,i2++) {
	var c1 = format.charAt(i1);
	var c2 = datestring.charAt(i2);
	if (c1 == '%') {
	    c1 = format.charAt(++i1);
	    var data = _DATE_FORMAT_REGXES[c1].exec(datestring.substring(i2));
	    if (!data.length) {
		return null;
	    }
	    data = data[0];
	    i2 += data.length-1;
	    var value = parseInt(data, 10);
	    if (isNaN(value)) {
		return null;
	    }
	    parsed[c1] = value;
	    continue;
	}
	if (c1 != c2) {
	    return null;
	}
    }
    return parsed;
}

/*
 * basic implementation of strptime. The only recognized formats
 * defined in _DATE_FORMAT_REGEXES (i.e. %Y, %d, %m, %H, %M)
 */
function strptime(datestring, format) {
    var parsed = _parseDate(datestring, format);
    if (!parsed) {
	return null;
    }
    // create initial date (!!! year=0 means 1900 !!!)
    var date = new Date(0, 0, 1, 0, 0);
    date.setFullYear(0); // reset to year 0
    if (parsed.Y) {
	date.setFullYear(parsed.Y);
    }
    if (parsed.m) {
	if (parsed.m < 1 || parsed.m > 12) {
	    return null;
	}
	// !!! month indexes start at 0 in javascript !!!
	date.setMonth(parsed.m - 1);
    }
    if (parsed.d) {
	if (parsed.m < 1 || parsed.m > 31) {
	    return null;
	}
	date.setDate(parsed.d);
    }
    if (parsed.H) {
	if (parsed.H < 0 || parsed.H > 23) {
	    return null;
	}
	date.setHours(parsed.H);
    }
    if (parsed.M) {
	if (parsed.M < 0 || parsed.M > 59) {
	    return null;
	}
	date.setMinutes(parsed.M);
    }
    return date;
}

// ========== END OF DATE EXTENSIONS ========== ///



// ========== ARRAY EXTENSIONS ========== ///
Array.prototype.contains = function(element) {
    return findValue(this, element) != -1;
};

// ========== END OF ARRAY EXTENSIONS ========== ///



// ========== STRING EXTENSIONS ========== //

/* python-like startsWith method for js strings
 * >>>
 */
String.prototype.startsWith = function(prefix) {
    return this.indexOf(prefix) == 0;
};

/* python-like endsWith method for js strings */
String.prototype.endsWith = function(suffix) {
    var startPos = this.length - suffix.length;
    if (startPos < 0) { return false; }
    return this.lastIndexOf(suffix, startPos) == startPos;
};

/* python-like strip method for js strings */
String.prototype.strip = function() {
    return this.replace(/^\s*(.*?)\s*$/, "$1");
};

/* py-equiv: string in list */
String.prototype.in_ = function(values) {
    return findValue(values, this) != -1;
};

/* py-equiv: str.join(list) */
String.prototype.join = function(args) {
    return args.join(this);
};

/* python-like list builtin
 * transforms an iterable in a js sequence
 * >>> gen = ifilter(function(x) {return x%2==0}, range(10))
 * >>> s = list(gen)
 * [0,2,4,6,8]
 */
function list(iterable) {
    var iterator = iter(iterable);
    var result = [];
    while (true) {
	/* iterates until StopIteration occurs */
	try {
	    result.push(iterator.next());
	} catch (exc) {
	    if (exc != StopIteration) { throw exc; }
	    return result;
	}
    }
}

/* py-equiv: getattr(obj, attrname, default=None) */
function getattr(obj, attrname, defaultValue) {
    // when not passed, defaultValue === undefined
    return obj[attrname] || defaultValue;
}

/* py-equiv: operator.attrgetter */
function attrgetter(attrname) {
    return function(obj) { return getattr(obj, attrname); };
}


/* returns a subslice of `lst` using `start`/`stop`/`step`
 * start, stop might be negative
 *
 * >>> sliceList(['a', 'b', 'c', 'd', 'e', 'f'], 2)
 * ['c', 'd', 'e', 'f']
 * >>> sliceList(['a', 'b', 'c', 'd', 'e', 'f'], 2, -2)
 * ['c', 'd']
 * >>> sliceList(['a', 'b', 'c', 'd', 'e', 'f'], -3)
 * ['d', 'e', 'f']
 */
function sliceList(lst, start, stop, step) {
    var start = start || 0;
    var stop = stop || lst.length;
    var step = step || 1;
    if (stop < 0) {
	stop = max(lst.length+stop, 0);
    }
    if (start < 0) {
	start = min(lst.length+start, lst.length);
    }
    var result = [];
    for (var i=start; i < stop; i+=step) {
	result.push(lst[i]);
    }
    return result;
}

/* returns a partial func that calls a mehod on its argument
 * py-equiv: return lambda obj: getattr(obj, methname)(*args)
 */
function methodcaller(methname) {
    var args = sliceList(arguments, 1);
    return function(obj) {
	return obj[methname].apply(obj, args);
    };
}

/* use MochiKit's listMin / listMax */
function min() { return listMin(arguments); }
function max() { return listMax(arguments); }

/*
 * >>> d = dict(["x", "y", "z"], [0, 1, 2])
 * >>> d['y']
 * 1
 * >>> d.y
 * 1
 */
function dict(keys, values) {
    if (keys.length != values.length) {
	throw "got different number of keys and values !";
    }
    var newobj = {};
    for(var i=0; i<keys.length; i++) {
	newobj[keys[i]] = values[i];
    }
    return newobj;
}


function concat() {
    return ''.join(list(arguments));
}


/**** class factories ****/

// transforms a function into an unbound method
function makeUnboundMethod(meth) {
    function unboundMeth(self) {
	var newargs = sliceList(arguments, 1);
	return meth.apply(self, newargs);
    }
    unboundMeth.__name__ = meth.__name__;
    return unboundMeth;
}

function attachMethodToClass(cls, methname, meth) {
    meth.__name__ = methname;
    // XXX : this is probably bad for memory usage
    cls.__dict__[methname] = meth;
    cls[methname] = makeUnboundMethod(meth); // for the class itself
    cls.prototype[methname] = meth; // for the instance
}

// simple internal function that tells if the attribute should
// be copied from baseclasses or not
function _isAttrSkipped(attrname) {
    var skipped = ['__class__', '__dict__', '__bases__', 'prototype'];
    for (var i=0; i < skipped.length; i++) {
	if (skipped[i] == attrname) {
	    return true;
	}
    }
    return false;
}

// internal function used to build the class constructor
function makeConstructor(userctor) {
    return function() {
	// this is a proxy to user's __init__
	if (userctor) {
	    userctor.apply(this, arguments);
	}
    };
}

/* this is a js class factory. objects returned by this function behave
 * more or less like a python class. The `class` function prototype is
 * inspired by the python `type` builtin
 * Important notes :
 *  -> methods are _STATICALLY_ attached when the class it created
 *  -> multiple inheritance was never tested, which means it doesn't work ;-)
 */
function defclass(name, bases, classdict) {
    var baseclasses = bases || [];

    // this is the static inheritance approach (<=> differs from python)
    var basemeths = {};
    var reverseLookup = [];
    for(var i=baseclasses.length-1; i >= 0; i--) {
	reverseLookup.push(baseclasses[i]);
    }
    reverseLookup.push({'__dict__' : classdict});

    for(var i=0; i < reverseLookup.length; i++) {
	var cls = reverseLookup[i];
	for (prop in cls.__dict__) {
	    // XXX hack to avoid __init__, __bases__...
	    if ( !_isAttrSkipped(prop) ) {
		basemeths[prop] = cls.__dict__[prop];
	    }
	}
    }
    var userctor = basemeths['__init__'];
    var constructor = makeConstructor(userctor);

    // python-like interface
    constructor.__name__ = name;
    constructor.__bases__ = baseclasses;
    constructor.__dict__ = {};
    constructor.prototype.__class__ = constructor;
    // make bound / unbound methods
    for (methname in basemeths) {
	attachMethodToClass(constructor, methname, basemeths[methname]);
    }

    return constructor;
}

// Not really python-like
CubicWeb = {};
// XXX backward compatibility
Erudi = CubicWeb;
CubicWeb.loaded = [];
CubicWeb.require = function(module) {
    if (!CubicWeb.loaded.contains(module)) {
	// a CubicWeb.load_javascript(module) function would require a dependency on ajax.js
	log(module, ' is required but not loaded');
    }
};

CubicWeb.provide = function(module) {
    if (!CubicWeb.loaded.contains(module)) {
	CubicWeb.loaded.push(module);
    }
};

CubicWeb.provide('python.js');
