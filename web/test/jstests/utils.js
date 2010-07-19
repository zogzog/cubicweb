function datetuple(d) {
    return [d.getFullYear(), d.getMonth()+1, d.getDate(),
	    d.getHours(), d.getMinutes()];
}

function pprint(obj) {
    print('{');
    for(k in obj) {
	print('  ' + k + ' = ' + obj[k]);
    }
    print('}');
}

function arrayrepr(array) {
    return '[' + array.join(', ') + ']';
}

function assertArrayEquals(array1, array2) {
    if (array1.length != array2.length) {
	throw new crosscheck.AssertionFailure(array1.join(', ') + ' != ' + array2.join(', '));
    }
    for (var i=0; i<array1.length; i++) {
	if (array1[i] != array2[i]) {

	    throw new crosscheck.AssertionFailure(arrayrepr(array1) + ' and ' + arrayrepr(array2)
						 + ' differs at index ' + i);
	}
    }
}
