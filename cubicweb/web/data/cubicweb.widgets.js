/**
 * Functions dedicated to widgets.
 *
 *  :organization: Logilab
 *  :copyright: 2003-2010 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
 *  :contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
 *
 *
 */

// widget namespace
Widgets = {};

/**
 * .. function:: buildWidget(wdgnode)
 *
 * this function takes a DOM node defining a widget and
 * instantiates / builds the appropriate widget class
 */
function buildWidget(wdgnode) {
    var wdgclass = Widgets[wdgnode.getAttribute('cubicweb:wdgtype')];
    if (wdgclass) {
        return new wdgclass(wdgnode);
    }
    return null;
}

function renderJQueryDatePicker(subject, button_image, date_format, min_date, max_date){
    $widget = cw.jqNode(subject);
    $widget.datepicker({buttonImage: button_image, dateFormat: date_format,
                        firstDay: 1, showOn: "button", buttonImageOnly: true,
                        minDate: min_date, maxDate: max_date});
    $widget.change(function(ev) {
        maxOfId = $(this).data('max-of');
        if (maxOfId) {
            cw.jqNode(maxOfId).datepicker("option", "maxDate", this.value);
        }
        minOfId = $(this).data('min-of');
        if (minOfId) {
            cw.jqNode(minOfId).datepicker("option", "minDate", this.value);
        }
    });
}

/**
 * .. function:: buildWidgets(root)
 *
 * This function is called on load and is in charge to build
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

jQuery(document).ready(function() {
    buildWidgets();
});

function postJSON(url, data, callback) {
    return jQuery.post(url, data, callback, AJAX_BASE_URL);
}

function getJSON(url, data, callback) {
    return jQuery.get(url, data, callback, AJAX_BASE_URL);
}


(function ($) {
    var defaultSettings = {
        initialvalue: '',
        multiple: false,
        mustMatch: false,
        delay: 50,
        limit: 50
    };
    function split(val) { return val.split( /\s*,\s*/ ); }
    function extractLast(term) { return split(term).pop(); }
    function allButLast(val) {
        var terms = split(val);
        terms.pop();
        return terms;
    }

    var methods = {
        __init__: function(suggestions, options) {
            return this.each(function() {
                // here, `this` refers to the DOM element (e.g. input) being wrapped
                // by cwautomplete plugin
                var instanceData = $(this).data('cwautocomplete');
                if (instanceData) {
                    // already initialized
                    return;
                }
                var settings = $.extend({}, defaultSettings, options);
                instanceData =  {
                    initialvalue: settings.initialvalue,
                    userInput: this,
                    hiddenInput: null
                };
                var hiHandlers = methods.hiddenInputHandlers;
                $(this).data('cwautocomplete', instanceData);
                // in case of an existing value, the hidden input must be initialized even if
                // the value is not changed
                if (($(instanceData.userInput).attr('cubicweb:initialvalue') !== undefined) && !instanceData.hiddenInput){
                    hiHandlers.initializeHiddenInput(instanceData);
                }
                $.ui.autocomplete.prototype._value = methods._value;
                $.data(this, 'settings', settings);
                if (settings.multiple) {
                    $.ui.autocomplete.filter = methods.multiple.makeFilter(this);
                    $(this).bind({
                        autocompleteselect: methods.multiple.select,
                        autocompletefocus: methods.multiple.focus,
                        keydown: methods.multiple.keydown
                        });
                }
                // XXX katia we dont need it if minLength == 0, but by setting minLength = 0
                // we probably break the backward compatibility
                $(this).bind('blur', methods.blur);
                if ($.isArray(suggestions)) { // precomputed list of suggestions
                    settings.source = hiHandlers.checkSuggestionsDataFormat(instanceData, suggestions);
                } else { // url to call each time something is typed
                    settings.source = function(request, response) {
                        var d = loadRemote(suggestions, {q: request.term, limit: settings.limit}, 'POST');
                        d.addCallback(function (suggestions) {
                            suggestions = hiHandlers.checkSuggestionsDataFormat(instanceData, suggestions);
                            response(suggestions);
                            if((suggestions.length) == 0){
                                methods.resetValues(instanceData);
                            }
                        });
                    };
                }
                $(this).autocomplete(settings);
                if (settings.mustMatch) {
                    $(this).keypress(methods.ensureExactMatch);
                }
            });
        },

        _value: function() {
            /* We extend the widget with the ability to lookup and
               handle several terms at once ('multiple' option). E.g.:
               toto, titi, tu....  The autocompletion must be
               performed only on the last of such a list of terms.
              */
            var settings = $(this.element).data('settings');
            var value = this.valueMethod.apply( this.element, arguments );
            if (settings.multiple && arguments.length === 0) {
                return extractLast(value);
            }
            return value
        },

        multiple: {
            focus: function() {
                // prevent value inserted on focus
                return false;
            },
            select: function(event, ui) {
                var terms = allButLast(this.value);
                // add the selected item
                terms.push(ui.item.value);
                // add placeholder to get the comma-and-space at the end
                terms.push("");
                this.value = terms.join( ", " );
                return false;
            },
            keydown: function(evt) {
                if (evt.keyCode == $.ui.keyCode.TAB) {
                    evt.preventDefault();
                }
            },
            makeFilter: function(userInput) {
                return function(array, term) {
                    // remove already entered terms from suggestion list
                    array = cw.utils.difference(array, allButLast(userInput.value));
                    var matcher = new RegExp( $.ui.autocomplete.escapeRegex(term), "i" );
                    return $.grep( array, function(value) {
                        return matcher.test( value.label || value.value || value );
                    });
                };
            }
        },
        blur: function(evt){
            var instanceData = $(this).data('cwautocomplete');
            if($(instanceData.userInput).val().strip().length==0){
                methods.resetValues(instanceData);
            }
        },

        ensureExactMatch: function(evt) {
            var instanceData = $(this).data('cwautocomplete');
            if (evt.keyCode == $.ui.keyCode.ENTER || evt.keyCode == $.ui.keyCode.TAB) {
                var validChoices = $.map($('ul.ui-autocomplete li'),
                                         function(li) {return $(li).text();});
                if ($.inArray($(instanceData.userInput).val(), validChoices) == -1) {
                    $(instanceData.userInput).val('');
                    $(instanceData.hiddenInput).val(instanceData.initialvalue || '');
                }
            }
        },

        resetValues: function(instanceData){
            $(instanceData.userInput).val('');
            $(instanceData.hiddenInput).val('');
        },


        hiddenInputHandlers: {
            /**
             * `hiddenInputHandlers` defines all methods specific to handle the
             * hidden input created along the standard text input.
             * An hiddenInput is necessary when displayed suggestions are
             * different from actual values to submit.
             * Imagine an autocompletion widget to choose among a list of CWusers.
             * Suggestions would be the list of logins, but actual values would
             * be the corresponding eids.
             * To handle such cases, suggestions list should be a list of JS objects
             * with two `label` and `value` properties.
             **/
            suggestionSelected: function(evt, ui) {
                var instanceData = $(this).data('cwautocomplete');
                instanceData.hiddenInput.value = ui.item.value;
                instanceData.value = ui.item.label;
                return false; // stop propagation
            },

            suggestionFocusChanged: function(evt, ui) {
                var instanceData = $(this).data('cwautocomplete');
                instanceData.userInput.value = ui.item.label;
                return false; // stop propagation
            },

            needsHiddenInput: function(suggestions) {
                return suggestions[0].label !== undefined;
            },
            initializeHiddenInput: function(instanceData) {
                var userInput = instanceData.userInput;
                var hiddenInput = INPUT({
                    type: "hidden",
                    name: userInput.name,
                    // XXX katia : this must be handeled in .SuggestField widget, but
                    // it seems not to be used anymore
                    value: $(userInput).attr('cubicweb:initialvalue') || userInput.value
                });
                $(userInput).removeAttr('name').after(hiddenInput);
                instanceData.hiddenInput = hiddenInput;
                $(userInput).bind({
                    autocompleteselect: methods.hiddenInputHandlers.suggestionSelected,
                    autocompletefocus: methods.hiddenInputHandlers.suggestionFocusChanged
                });
            },

            /*
             * internal convenience function: old jquery plugin accepted to be fed
             * with a list of couples (value, label). The new (jquery-ui) autocomplete
             * plugin expects a list of objects with "value" and "label" properties.
             *
             * This function converts the old format to the new one.
             */
            checkSuggestionsDataFormat: function(instanceData, suggestions) {
                // check for old (value, label) format
                if ($.isArray(suggestions) && suggestions.length &&
                    $.isArray(suggestions[0])){
                    if (suggestions[0].length == 2) {
                        cw.log('[3.10] autocomplete init func should return {label,value} dicts instead of lists');
                        suggestions = $.map(suggestions, function(sugg) {
                                            return {value: sugg[0], label: sugg[1]};
                                            });
                    } else {
                        if(suggestions[0].length == 1){
                            suggestions = $.map(suggestions, function(sugg) {
                                return {value: sugg[0], label: sugg[0]};
                            });
                        }
                    }
                }
                var hiHandlers = methods.hiddenInputHandlers;
                if (suggestions.length && hiHandlers.needsHiddenInput(suggestions)
                    && !instanceData.hiddenInput) {
                    hiHandlers.initializeHiddenInput(instanceData);
                    hiHandlers.fixUserInputInitialValue(instanceData, suggestions);
                }
                // otherwise, assume data shape is correct
                return suggestions;
            },

            fixUserInputInitialValue: function(instanceData, suggestions) {
                // called when the data is loaded to reset the correct displayed
                // value in the visible input field (typically replacing an eid
                // by a displayable value)
                var curvalue = instanceData.userInput.value;
                if (!curvalue) {
                    return;
                }
                for (var i=0, length=suggestions.length; i < length; i++) {
                    var sugg = suggestions[i];
                    if (sugg.value == curvalue) {
                        instanceData.userInput.value = sugg.label;
                        return;
                    }
                }
            }
        }
    };

    $.fn.cwautocomplete = function(data, options) {
        return methods.__init__.apply(this, [data, options]);
    };
})(jQuery);


Widgets.SuggestField = defclass('SuggestField', null, {
    __init__: function(node, options) {
        options = options || {};
        var multi = node.getAttribute('cubicweb:multi');
        options.multiple = (multi == "yes") ? true: false;
        var d = loadRemote(node.getAttribute('cubicweb:dataurl'));
        d.addCallback(function(data) {
            $(node).cwautocomplete(data, options);
        });
    }
});

Widgets.StaticFileSuggestField = defclass('StaticSuggestField', [Widgets.SuggestField], {

    __init__: function(node) {
        Widgets.SuggestField.__init__(this, node, {
            method: 'get' // XXX
        });
    }

});

Widgets.RestrictedSuggestField = defclass('RestrictedSuggestField', [Widgets.SuggestField], {
    __init__: function(node) {
        Widgets.SuggestField.__init__(this, node, {
            mustMatch: true
        });
    }
});

//remote version of RestrictedSuggestField
Widgets.LazySuggestField = defclass('LazySuggestField', [Widgets.SuggestField], {
    __init__: function(node, options) {
        var self = this;
        options = options || {};
        options.delay = 50;
        // multiple selection not supported yet (still need to formalize correctly
        // initial values / display values)
        var initialvalue = cw.evalJSON(node.getAttribute('cubicweb:initialvalue') || 'null');
        if (!initialvalue) {
            initialvalue = node.value;
        }
        options.initialvalue = initialvalue;
        Widgets.SuggestField.__init__(this, node, options);
    }
});

/**
 * .. function:: toggleTree(event)
 *
 * called when the use clicks on a tree node
 *  - if the node has a `cubicweb:loadurl` attribute, replace the content of the node
 *    by the url's content.
 *  - else, there's nothing to do, let the jquery plugin handle it.
 */
function toggleTree(event) {
    var linode = jQuery(this);
    var url = linode.attr('cubicweb:loadurl');
    if (url) {
        linode.find('ul.placeholder').remove();
        var d = linode.loadxhtml(url, null, 'post', 'append');
        d.addCallback(function(domnode) {
                linode.removeAttr('cubicweb:loadurl');
                linode.find('> ul.treeview').treeview({
                    toggle: toggleTree,
                    prerendered: true
                });
                return null;
            }
        );
    }
}

Widgets.TemplateTextField = defclass("TemplateTextField", null, {

    __init__: function(wdgnode) {
        this.variables = jQuery(wdgnode).attr('cubicweb:variables').split(',');
        this.options = {
            name: wdgnode.getAttribute('cubicweb:inputid'),
            rows: wdgnode.getAttribute('cubicweb:rows') || 40,
            cols: wdgnode.getAttribute('cubicweb:cols') || 80
        };
        // this.variableRegexp = /%\((\w+)\)s/;
        this.errorField = DIV({
            'class': "errorMessage"
        });
        this.textField = TEXTAREA(this.options);
        jQuery(this.textField).bind('keyup', {
            'self': this
        },
        this.highlightInvalidVariables);
        jQuery('#substitutions').prepend(this.errorField);
        jQuery('#substitutions .errorMessage').hide();
        wdgnode.appendChild(this.textField);
    },

    /* signal callbacks */

    highlightInvalidVariables: function(event) {
        var self = event.data.self;
        var text = self.textField.value;
        var unknownVariables = [];
        var it = 0;
        var group = null;
        var variableRegexp = /%\((\w+)\)s/g;
        // emulates rgx.findAll()
        while ( (group = variableRegexp.exec(text)) ) {
            if ($.inArray(group[1], self.variables) == -1) {
                unknownVariables.push(group[1]);
            }
            it++;
            if (it > 5) {
                break;
            }
        }
        var errText = '';
        if (unknownVariables.length) {
            errText = "Detected invalid variables : " + unknownVariables.join(', ');
            jQuery('#substitutions .errorMessage').show();
        } else {
            jQuery('#substitutions .errorMessage').hide();
        }
        self.errorField.innerHTML = errText;
    }

});

cw.widgets = {
    /**
     * .. function:: insertText(text, areaId)
     *
     * inspects textarea with id `areaId` and replaces the current selected text
     * with `text`. Cursor is then set at the end of the inserted text.
     */
    insertText: function (text, areaId) {
        var textarea = jQuery('#' + areaId);
        if (document.selection) { // IE
            var selLength;
            textarea.focus();
            var sel = document.selection.createRange();
            selLength = sel.text.length;
            sel.text = text;
            sel.moveStart('character', selLength - text.length);
            sel.select();
        } else if (textarea.selectionStart || textarea.selectionStart == '0') { // mozilla
            var startPos = textarea.selectionStart;
            var endPos = textarea.selectionEnd;
            // insert text so that it replaces the [startPos, endPos] part
            textarea.value = textarea.value.substring(0, startPos) + text + textarea.value.substring(endPos, textarea.value.length);
            // set cursor pos at the end of the inserted text
            textarea.selectionStart = textarea.selectionEnd = startPos + text.length;
            textarea.focus();
        } else { // safety belt for other browsers
            textarea.value += text;
        }
    }
};


// InOutWidget  This contains specific InOutnWidget javascript
// IE things can not handle hide/show options on select, this cloned list solition (should propably have 2 widgets)

(function ($) {

    var methods = {
        __init__: function(fromSelect, toSelect) {
            // closed over state
            var state = {'$fromNode' : $(cw.escape('#' + fromSelect)),
                         '$toNode'   : $(cw.escape('#' + toSelect)),
                         'name'      : this.attr('id')};

            function sortoptions($optionlist) {
                var $sorted = $optionlist.find('option').sort(function(opt1, opt2) {
                    return $(opt1).text() > $(opt2).text() ? 1 : -1;
                });
                // this somehow translates to an inplace sort
                $optionlist.append($sorted);
            };
            sortoptions(state.$fromNode);
            sortoptions(state.$toNode);

            // will move selected options from one list to the other
            // and call an option handler on each option
            function moveoptions ($fromlist, $tolist, opthandler) {
                $fromlist.find('option:selected').each(function(index, option) {
                    var $option = $(option);
                    // add a new option to the target list
                    $tolist.append(OPTION({'value' : $option.val()},
	 			          $option.text()));
                    // process callback on the option
                    opthandler.call(null, $option);
                    // remove option from the source list
                    $option.remove();
                });
                // re-sort both lists
                sortoptions($fromlist);
                sortoptions($tolist);
            };

            function addvalues () {
                moveoptions(state.$fromNode, state.$toNode, function ($option) {
                    // add an hidden input for the edit controller
                    var hiddenInput = INPUT({
                        type: 'hidden', name: state.name,
                        value : $option.val()
                    });
                    state.$toNode.parent().append(hiddenInput);
                });
            };

            function removevalues () {
                moveoptions(state.$toNode, state.$fromNode, function($option) {
                    // remove hidden inputs for the edit controller
                    var selector = 'input[name=' + cw.escape(state.name) + ']'
                    state.$toNode.parent().find(selector).each(function(index, input) {
                        if ($(input).val() == $option.val()) {
                            $(input).remove();
                        }
                    });
                });
            };

            var $this = $(this);
            $this.find('.cwinoutadd').bind( // 'add >>>' symbol
                'click', {'state' : state}, addvalues);
            $this.find('.cwinoutremove').bind( // 'remove <<<' symbol
                'click', {'state' : state}, removevalues);

            state.$fromNode.bind('dblclick', {'state': state}, addvalues);
            state.$toNode.bind('dblclick', {'state': state}, removevalues);

        }
    };
    $.fn.cwinoutwidget = function(fromSelect, toSelect) {
        return methods.__init__.apply(this, [fromSelect, toSelect]);
    };
})(jQuery);
