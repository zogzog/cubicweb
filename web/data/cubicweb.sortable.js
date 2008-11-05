/* Adapted from MochiKit's example to use custom cubicweb attribute
   and a stable sort (merge sort) instead of default's js array sort

merge sort JS implementation was found here :
http://en.literateprograms.org/Merge_sort_(JavaScript)


On page load, the SortableManager:

- Finds the table by its id (sortable_table).
- Parses its thead for columns with a "mochi:format" attribute.
- Parses the data out of the tbody based upon information given in the
 "cubicweb:sorvalue" attribute, and clones the tr elements for later re-use.
- Clones the column header th elements for use as a template when drawing
 sort arrow columns.
- Stores away a reference to the tbody, as it will be replaced on each sort.

On sort request:

- Sorts the data based on the given key and direction
- Creates a new tbody from the rows in the new ordering
- Replaces the column header th elements with clickable versions, adding an
 indicator (&uarr; or &darr;) to the most recently sorted column.

*/

//************** merge sort implementation ***************//
Sortable = {}

Sortable.msort = function(array, begin, end, cmpfunc) {
    var size=end-begin;
    if(size<2) return;
    
    var begin_right=begin+Math.floor(size/2);
    
    Sortable.msort(array, begin, begin_right, cmpfunc);
    Sortable.msort(array, begin_right, end, cmpfunc);
    Sortable.merge(array, begin, begin_right, end, cmpfunc);
}

Sortable.merge_sort = function(array, cmpfunc) {
    Sortable.msort(array, 0, array.length, cmpfunc);
}

Sortable.merge = function(array, begin, begin_right, end, cmpfunc) {
    for(;begin<begin_right; ++begin) {
	// if array[begin] > array[begin_right]
	if(cmpfunc(array[begin], array[begin_right]) == 1) {
	    var v = array[begin];
	    array[begin] = array[begin_right];
	    Sortable.insert(array, begin_right, end, v, cmpfunc);
	}
    }
}

Array.prototype.swap=function(a, b) {
    var tmp = this[a];
    this[a] = this[b];
    this[b] = tmp;
}


Sortable.insert = function(array, begin, end, v, cmpfunc) {
    // while(begin+1<end && array[begin+1]<v) {
    while(begin+1<end && cmpfunc(array[begin+1], v) == -1) {
	array.swap(begin, begin+1);
	++begin;
    }
    array[begin]=v;
}

//************** auto-sortable tables ***************//

Sortable.SortableManager = function () {
    this.thead = null;
    this.tbody = null;
    this.columns = [];
    this.rows = [];
    this.sortState = {};
    this.sortkey = 0;
};

mouseOverFunc = function () {
    addElementClass(this, "over");
};

mouseOutFunc = function () {
    removeElementClass(this, "over");
};

Sortable.ignoreEvent = function (ev) {
    if (ev && ev.preventDefault) {
	ev.preventDefault();
	ev.stopPropagation();
    } else if (typeof(event) != 'undefined') {
	event.cancelBubble = false;
	event.returnValue = false;
    }
};


Sortable.getTableHead = function(table) {
    var thead = table.getElementsByTagName('thead')[0];
    if ( !thead ) {
	thead = table.getElementsByTagName('tr')[0];
    }
    return thead;
}

Sortable.getTableBody = function(table) {
    var tbody = table.getElementsByTagName('tbody')[0];
    if ( !tbody ) {
	tobdy = table; // XXX
    }
    return tbody;
}

jQuery.extend(Sortable.SortableManager.prototype, {
    
    "initWithTable" : function (table) {
	/***  Initialize the SortableManager with a table object  ***/
	// Find the thead
	this.thead = Sortable.getTableHead(table);
	// get the mochi:format key and contents for each column header
	var cols = this.thead.getElementsByTagName('th');
	for (var i = 0; i < cols.length; i++) {
	    var node = cols[i];
	    var o = node.childNodes;
	    node.onclick = this.onSortClick(i);
	    node.onmousedown = Sortable.ignoreEvent;
	    node.onmouseover = mouseOverFunc;
	    node.onmouseout = mouseOutFunc;
	    this.columns.push({
		"element": node,
		"proto": node.cloneNode(true)
	    });
	}
	// scrape the tbody for data
	this.tbody = Sortable.getTableBody(table);
	// every row
	var rows = this.tbody.getElementsByTagName('tr');
	for (var i = 0; i < rows.length; i++) {
	    // every cell
	    var row = rows[i];
	    var cols = row.getElementsByTagName('td');
	    var rowData = [];
	    for (var j = 0; j < cols.length; j++) {
		// scrape the text and build the appropriate object out of it
		var cell = cols[j];
		rowData.push([evalJSON(cell.getAttribute('cubicweb:sortvalue'))]);
	    }
	    // stow away a reference to the TR and save it
	    rowData.row = row.cloneNode(true);
	    this.rows.push(rowData);
	}
	// do initial sort on first column
	// this.drawSortedRows(null, true, false);

    },

    "onSortClick" : function (name) {
	/*** Return a sort function for click events  ***/
	return method(this, function () {
	    var order = this.sortState[name];
	    if (order == null) {
		order = true;
	    } else if (name == this.sortkey) {
		order = !order;
	    }
	    this.drawSortedRows(name, order, true);
	});
    },
    
    "drawSortedRows" : function (key, forward, clicked) {
	/***  Draw the new sorted table body, and modify the column headers
              if appropriate
         ***/
	this.sortkey = key;
	// sort based on the state given (forward or reverse)
	var cmp = (forward ? keyComparator : reverseKeyComparator);
	Sortable.merge_sort(this.rows, cmp(key));
	
	// save it so we can flip next time
	this.sortState[key] = forward;
	// get every "row" element from this.rows and make a new tbody
	var newRows = [];
	for (var i=0; i < this.rows.length; i++){
	    var row = this.rows[i].row;
	    if (i%2) {
		removeElementClass(row, 'even');
		addElementClass(row, 'odd');
	    } else {
		removeElementClass(row, 'odd');
		addElementClass(row, 'even');
	    }
	    newRows.push(row);
	}
	// var newBody = TBODY(null, map(itemgetter("row"), this.rows));
	var newBody = TBODY(null, newRows);
	// swap in the new tbody
	this.tbody = swapDOM(this.tbody, newBody);
	for (var i = 0; i < this.columns.length; i++) {
	    var col = this.columns[i];
	    var node = col.proto.cloneNode(true);
	    // remove the existing events to minimize IE leaks
	    col.element.onclick = null;
	    col.element.onmousedown = null;
	    col.element.onmouseover = null;
	    col.element.onmouseout = null;
	    // set new events for the new node
	    node.onclick = this.onSortClick(i);
	    node.onmousedown = Sortable.ignoreEvent;
	    node.onmouseover = mouseOverFunc;
	    node.onmouseout = mouseOutFunc;
	    // if this is the sorted column
	    if (key == i) {
		// \u2193 is down arrow, \u2191 is up arrow
		// forward sorts mean the rows get bigger going down
		var arrow = (forward ? "\u2193" : "\u2191");
		// add the character to the column header
		node.appendChild(SPAN(null, arrow));
		if (clicked) {
		    node.onmouseover();
		}
	    }

	    // swap in the new th
	    col.element = swapDOM(col.element, node);
	}
    }
});

var sortableManagers = [];

/*
 * Find each table under `rootNode` and make them sortable
 */
Sortable.makeTablesSortable = function(rootNode) {
    var tables = getElementsByTagAndClassName('table', 'listing', rootNode);
    for(var i=0; i < tables.length; i++) {
	var sortableManager = new Sortable.SortableManager();
	sortableManager.initWithTable(tables[i]);
	sortableManagers.push(sortableManagers);
    }
}

jQuery(document).ready(Sortable.makeTablesSortable);

CubicWeb.provide('sortable.js');
