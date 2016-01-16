/**
 * This file contains extensions for standard javascript types
 *
 */

ONE_DAY = 86400000; // (in milliseconds)
// ========== DATE EXTENSIONS ========== ///
Date.prototype.equals = function(other) {
    /* compare with other date ignoring time differences */
    if (this.getYear() == other.getYear() && this.getMonth() == other.getMonth() && this.getDate() == other.getDate()) {
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
    return this.add( - days);
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

/**
 * .. function:: Date.prototype.nextMonth()
 *
 * returns the first day of the next month
 */
Date.prototype.nextMonth = function() {
    if (this.getMonth() == 11) {
        var d = new Date(this.getFullYear() + 1, 0, 1);
        return d;
    } else {
        var d2 = new Date(this.getFullYear(), this.getMonth() + 1, 1);
        return d2;
    }
};

/**
 * .. function:: Date.prototype.getRealDay()
 *
 * returns the day of week, 0 being monday, 6 being sunday
 */
Date.prototype.getRealDay = function() {
    // getDay() returns 0 for Sunday ==> 6 for Saturday
    return (this.getDay() + 6) % 7;
};

Date.prototype.strftime = function(fmt) {
    if (this.toLocaleFormat !== undefined) { // browser dependent
        return this.toLocaleFormat(fmt);
    }
    // XXX implement at least a decent fallback implementation
    return this.getFullYear() + '/' + (this.getMonth() + 1) + '/' + this.getDate();
};

var _DATE_FORMAT_REGXES = {
    'Y': new RegExp('^-?[0-9]+'),
    'd': new RegExp('^[0-9]{1,2}'),
    'm': new RegExp('^[0-9]{1,2}'),
    'H': new RegExp('^[0-9]{1,2}'),
    'M': new RegExp('^[0-9]{1,2}')
};

/**
 * .. function:: _parseDate(datestring, format)
 *
 * _parseData does the actual parsing job needed by `strptime`
 */
function _parseDate(datestring, format) {
    var skip0 = new RegExp('^0*[0-9]+');
    var parsed = {};
    for (var i1 = 0, i2 = 0; i1 < format.length; i1++, i2++) {
        var c1 = format.charAt(i1);
        var c2 = datestring.charAt(i2);
        if (c1 == '%') {
            c1 = format.charAt(++i1);
            var data = _DATE_FORMAT_REGXES[c1].exec(datestring.substring(i2));
            if (!data.length) {
                return null;
            }
            data = data[0];
            i2 += data.length - 1;
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

/**
 * .. function:: strptime(datestring, format)
 *
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
// ========== STRING EXTENSIONS ========== //
/**
 * .. function:: String.prototype.startswith(prefix)
 *
 * python-like startsWith method for js strings
 * >>>
 */
String.prototype.startswith = function(prefix) {
    return this.indexOf(prefix) == 0;
};

/**
 * .. function:: String.prototype.endswith(suffix)
 *
 * python-like endsWith method for js strings
 */
String.prototype.endswith = function(suffix) {
    var startPos = this.length - suffix.length;
    if (startPos < 0) {
        return false;
    }
    return this.lastIndexOf(suffix, startPos) == startPos;
};

/**
 * .. function:: String.prototype.strip()
 *
 * python-like strip method for js strings
 */
String.prototype.strip = function() {
    return this.replace(/^\s*(.*?)\s*$/, "$1");
};

/**
 * .. function:: String.prototype.rstrip()
 *
 * python-like rstrip method for js strings
 */
String.prototype.rstrip = function(str) {
    if (!str) { str = '\s' ; }
    return this.replace(new RegExp('^(.*?)' + str + '*$'), "$1");
};

// ========= class factories ========= //

/**
 * .. function:: makeUnboundMethod(meth)
 *
 * transforms a function into an unbound method
 */
function makeUnboundMethod(meth) {
    function unboundMeth(self) {
        var newargs = cw.utils.sliceList(arguments, 1);
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

/**
 * .. function:: _isAttrSkipped(attrname)
 *
 * simple internal function that tells if the attribute should
 * be copied from baseclasses or not
 */
function _isAttrSkipped(attrname) {
    var skipped = ['__class__', '__dict__', '__bases__', 'prototype'];
    for (var i = 0; i < skipped.length; i++) {
        if (skipped[i] == attrname) {
            return true;
        }
    }
    return false;
}

/**
 * .. function:: makeConstructor(userctor)
 *
 * internal function used to build the class constructor
 */
function makeConstructor(userctor) {
    return function() {
        // this is a proxy to user's __init__
        if (userctor) {
            userctor.apply(this, arguments);
        }
    };
}

/**
 * .. function:: defclass(name, bases, classdict)
 *
 * this is a js class factory. objects returned by this function behave
 * more or less like a python class. The `class` function prototype is
 * inspired by the python `type` builtin
 *
 * .. Note::
 *
 *    * methods are _STATICALLY_ attached when the class it created
 *    * multiple inheritance was never tested, which means it doesn't work ;-)
 */
function defclass(name, bases, classdict) {
    var baseclasses = bases || [];

    // this is the static inheritance approach (<=> differs from python)
    var basemeths = {};
    var reverseLookup = [];
    for (var i = baseclasses.length - 1; i >= 0; i--) {
        reverseLookup.push(baseclasses[i]);
    }
    reverseLookup.push({
        '__dict__': classdict
    });

    for (var i = 0; i < reverseLookup.length; i++) {
        var cls = reverseLookup[i];
        for (prop in cls.__dict__) {
            // XXX hack to avoid __init__, __bases__...
            if (!_isAttrSkipped(prop)) {
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
