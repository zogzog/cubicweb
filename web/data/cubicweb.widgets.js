/*
 *  :organization: Logilab
 *  :copyright: 2003-2008 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
 *  :contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
 *
 *
 */

// widget namespace
Widgets = {};


/* this function takes a DOM node defining a widget and
 * instantiates / builds the appropriate widget class
 */
function buildWidget(wdgnode) {
    var wdgclass = Widgets[wdgnode.getAttribute('cubicweb:wdgtype')];
    if (wdgclass) {
	var wdg = new wdgclass(wdgnode);
    }
}

/* This function is called on load and is in charge to build
 * JS widgets according to DOM nodes found in the page
 */
function buildWidgets(root) {
    root = root || document;
    jQuery(root).find('.widget').each(function() {
	if (this.getAttribute('cubicweb:loadtype') == 'auto') {
	    buildWidget(this);
	}
    });
}


// we need to differenciate cases where initFacetBoxEvents is called
// with one argument or without any argument. If we use `initFacetBoxEvents`
// as the direct callback on the jQuery.ready event, jQuery will pass some argument
// of his, so we use this small anonymous function instead.
jQuery(document).ready(function() {buildWidgets();});


Widgets.SuggestField = defclass('SuggestField', null, {
    __init__: function(node, options) {
	var multi = node.getAttribute('cubicweb:multi') || "no";
	options = options || {};
	options.multiple = (multi == "yes") ? true : false;
	var dataurl = node.getAttribute('cubicweb:dataurl');
        var method = postJSON;
	if (options.method == 'get'){
	  method = function(url, data, callback) {
	    // We can't rely on jQuery.getJSON because the server
	    // might set the Content-Type's response header to 'text/plain'
	    jQuery.get(url, data, function(response) {
	      callback(evalJSON(response));
	    });
	  };
	}
	var self = this; // closure
	method(dataurl, null, function(data) {
	    // in case we received a list of couple, we assume that the first
	    // element is the real value to be sent, and the second one is the
	    // value to be displayed
	    if (data.length && data[0].length == 2) {
		options.formatItem = function(row) { return row[1]; };
		self.hideRealValue(node);
		self.setCurrentValue(node, data);
	    }
	    jQuery(node).autocomplete(data, options);
	});
    },

    hideRealValue: function(node) {
	var hidden = INPUT({'type': "hidden", 'name': node.name, 'value': node.value});
	node.parentNode.appendChild(hidden);
	// remove 'name' attribute from visible input so that it is not submitted
	// and set correct value in the corresponding hidden field
	jQuery(node).removeAttr('name').bind('result', function(_, row, _) {
	    hidden.value = row[0];
	});
    },

    setCurrentValue: function(node, data) {
	// called when the data is loaded to reset the correct displayed
	// value in the visible input field (typically replacing an eid
	// by a displayable value)
	var curvalue = node.value;
	if (!node.value) {
	    return;
	}
	for (var i=0,length=data.length; i<length; i++) {
	    var row = data[i];
	    if (row[0] == curvalue) {
		node.value = row[1];
		return;
	    }
	}
    }
});

Widgets.StaticFileSuggestField = defclass('StaticSuggestField', [Widgets.SuggestField], {

    __init__ : function(node) {
	Widgets.SuggestField.__init__(this, node, {method: 'get'});
    }

});

Widgets.RestrictedSuggestField = defclass('RestrictedSuggestField', [Widgets.SuggestField], {

    __init__ : function(node) {
	Widgets.SuggestField.__init__(this, node, {mustMatch: true});
    }

});


/*
 * suggestform displays a suggest field and associated validate / cancel buttons
 * constructor's argumemts are the same that BaseSuggestField widget
 */
Widgets.SuggestForm = defclass("SuggestForm", null, {

    __init__ : function(inputid, initfunc, varargs, validatefunc, options) {
	this.validatefunc = validatefunc || noop;
	this.sgfield = new Widgets.BaseSuggestField(inputid, initfunc,
						    varargs, options);
	this.oklabel = options.oklabel || 'ok';
	this.cancellabel = options.cancellabel || 'cancel';
	bindMethods(this);
	connect(this.sgfield, 'validate', this, this.entryValidated);
    },

    show : function(parentnode) {
	var sgnode = this.sgfield.builddom();
	var buttons = DIV({'class' : "sgformbuttons"},
			  [A({'href' : "javascript: noop();",
			      'onclick' : this.onValidateClicked}, this.oklabel),
			   ' / ',
			   A({'href' : "javascript: noop();",
			      'onclick' : this.destroy}, escapeHTML(this.cancellabel))]);
	var formnode = DIV({'class' : "sgform"}, [sgnode, buttons]);
 	appendChildNodes(parentnode, formnode);
	this.sgfield.textinput.focus();
	this.formnode = formnode;
	return formnode;
    },

    destroy : function() {
	signal(this, 'destroy');
	this.sgfield.destroy();
	removeElement(this.formnode);
    },

    onValidateClicked : function() {
	this.validatefunc(this, this.sgfield.taglist());
    },
    /* just an indirection to pass the form instead of the sgfield as first parameter */
    entryValidated : function(sgfield, taglist) {
	this.validatefunc(this, taglist);
    }
});


/* called when the use clicks on a tree node
 *  - if the node has a `cubicweb:loadurl` attribute, replace the content of the node
 *    by the url's content.
 *  - else, there's nothing to do, let the jquery plugin handle it.
 */
function toggleTree(event) {
    var linode = jQuery(this);
    var url = linode.attr('cubicweb:loadurl');
    linode.find('ul.placeholder').remove();
    if (url) {
	linode.loadxhtml(url, {callback: function(domnode) {
	    linode.removeAttr('cubicweb:loadurl');
	    jQuery(domnode).treeview({toggle: toggleTree,
				      prerendered: true});
	    return null;
	}}, 'post', 'append');
    }
}

Widgets.TreeView = defclass("TreeView", null, {
    __init__: function(wdgnode) {
	jQuery(wdgnode).treeview({toggle: toggleTree,
				  prerendered: true
				 });
    }
});


/* widget based on SIMILE's timeline widget
 * http://code.google.com/p/simile-widgets/
 *
 * Beware not to mess with SIMILE's Timeline JS namepsace !
 */

Widgets.TimelineWidget = defclass("TimelineWidget", null, {
    __init__: function (wdgnode) {
 	var tldiv = DIV({id: "tl", style: 'height: 200px; border: 1px solid #ccc;'});
	wdgnode.appendChild(tldiv);
	var tlunit = wdgnode.getAttribute('cubicweb:tlunit') || 'YEAR';
	var eventSource = new Timeline.DefaultEventSource();
	var bandData = {
	  eventPainter:     Timeline.CubicWebEventPainter,
	  eventSource:    eventSource,
	  width:          "100%",
	  intervalUnit:   Timeline.DateTime[tlunit.toUpperCase()],
	  intervalPixels: 100
	};
	var bandInfos = [ Timeline.createBandInfo(bandData) ];
	var tl = Timeline.create(tldiv, bandInfos);
	var loadurl = wdgnode.getAttribute('cubicweb:loadurl');
	Timeline.loadJSON(loadurl, function(json, url) {
			    eventSource.loadJSON(json, url); });

    }
});

Widgets.TemplateTextField = defclass("TemplateTextField", null, {

    __init__ : function(wdgnode) {
	this.variables = getNodeAttribute(wdgnode, 'cubicweb:variables').split(',');
	this.options = {'name' : wdgnode.getAttribute('cubicweb:inputname'),
			'id'   : wdgnode.getAttribute('cubicweb:inputid'),
			'rows' : wdgnode.getAttribute('cubicweb:rows') || 40,
			'cols' : wdgnode.getAttribute('cubicweb:cols') || 80
		       };
	// this.variableRegexp = /%\((\w+)\)s/;
	this.parentnode = wdgnode;
    },

    show : function(parentnode) {
	parentnode = parentnode || this.parentnode;
	this.errorField = DIV({'class' : "textfieldErrors"});
	this.textField = TEXTAREA(this.options);
	connect(this.textField, 'onkeyup', this, this.highlightInvalidVariables);
	appendChildNodes(parentnode, this.textField, this.errorField);
	appendChildNodes(parentnode, this.textField);
    },

    /* signal callbacks */

    highlightInvalidVariables : function() {
	var text = this.textField.value;
	var unknownVariables = [];
	var it=0;
	var group = null;
	var variableRegexp = /%\((\w+)\)s/g;
	// emulates rgx.findAll()
	while ( group=variableRegexp.exec(text) ) {
	    if ( !this.variables.contains(group[1]) ) {
		unknownVariables.push(group[1]);
	    }
	    it++;
	    if (it > 5)
		break;
	}
	var errText = '';
	if (unknownVariables.length) {
	    errText = "Detected invalid variables : " + ", ".join(unknownVariables);
	}
	this.errorField.innerHTML = errText;
    }

});

/*
 * ComboBox with a textinput : allows to add a new value
 */

Widgets.AddComboBox = defclass('AddComboBox', null, {
   __init__ : function(wdgnode) {
       jQuery("#add_newopt").click(function() {
	  var new_val = jQuery("#newopt").val();
	      if (!new_val){
		  return false;
	      }
          name = wdgnode.getAttribute('name').split(':');
	  this.rel = name[0];
	  this.eid_to = name[1];
          this.etype_to = wdgnode.getAttribute('cubicweb:etype_to');
          this.etype_from = wdgnode.getAttribute('cubicweb:etype_from');
     	  var d = async_remote_exec('add_and_link_new_entity', this.etype_to, this.rel, this.eid_to, this.etype_from, 'new_val');
          d.addCallback(function (eid) {
          jQuery(wdgnode).find("option[selected]").removeAttr("selected");
          var new_option = OPTION({'value':eid, 'selected':'selected'}, value=new_val);
          wdgnode.appendChild(new_option);
          });
          d.addErrback(function (xxx) {
             log('xxx =', xxx);
          });
     });
   }
});


CubicWeb.provide('widgets.js');
