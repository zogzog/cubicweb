/*
 *  :organization: Logilab
 *  :copyright: 2003-2008 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
 *  :contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
 */

CubicWeb.require('htmlhelpers.js');
CubicWeb.require('ajax.js');

//============= filter form functions ========================================//

function copyParam(origparams, newparams, param) {
    var index = findValue(origparams[0], param);
    if (index > -1) {
	newparams[param] = origparams[1][index];
    }
}

function facetFormContent(form) {
    var names = [];
    var values = [];
    jQuery(form).find('.facet').each(function () {
        var facetName = jQuery(this).find('.facetTitle').attr('cubicweb:facetName');
        var facetValues = jQuery(this).find('.facetValueSelected').each(function(x) {
  	    names.push(facetName);
  	    values.push(this.getAttribute('cubicweb:value'));
        });
    });
    jQuery(form).find('input').each(function () {
        names.push(this.name);
        values.push(this.value);
    });
    jQuery(form).find('select option[@selected]').each(function () {
	names.push(this.parentNode.name);
	values.push(this.value);
    });
    return [names, values];
}

function buildRQL(divid, vid, paginate, vidargs) {
    jQuery(CubicWeb).trigger('facets-content-loading', [divid, vid, paginate, vidargs]);
    var form = getNode(divid+'Form');
    var zipped = facetFormContent(form);
    zipped[0].push('facetargs');
    zipped[1].push(vidargs);
    var d = async_remote_exec('filter_build_rql', zipped[0], zipped[1]);
    d.addCallback(function(result) {
	var rql = result[0];
	var $bkLink = jQuery('#facetBkLink');
	if ($bkLink.length) {
	    var bkUrl = $bkLink.attr('cubicweb:target') + '&path=view?rql=' + rql;
	    if (vid) {
		bkUrl += '&vid=' + vid;
	    }
	    $bkLink.attr('href', bkUrl);
	}
	var toupdate = result[1];
	var extraparams = vidargs;
	var displayactions = jQuery('#' + divid).attr('cubicweb:displayactions');
	if (displayactions) { extraparams['displayactions'] = displayactions; }
	if (paginate) { extraparams['paginate'] = '1'; }
	// copy some parameters
	// XXX cleanup vid/divid mess
	// if vid argument is specified , the one specified in form params will
	// be overriden by replacePageChunk
	copyParam(zipped, extraparams, 'vid');
	extraparams['divid'] = divid;
	copyParam(zipped, extraparams, 'divid');
	copyParam(zipped, extraparams, 'subvid');
	// paginate used to know if the filter box is acting, in which case we
	// want to reload action box to match current selection
	replacePageChunk(divid, rql, vid, extraparams, true, function() {
	  jQuery(CubicWeb).trigger('facets-content-loaded', [divid, rql, vid, extraparams]);
	});
	if (paginate) {
	    // FIXME the edit box might not be displayed in which case we don't
	    // know where to put the potential new one, just skip this case
	    // for now
	    if (jQuery('#edit_box').length) {
		reloadComponent('edit_box', rql, 'boxes', 'edit_box');
	    }
	}
	var d = async_remote_exec('filter_select_content', toupdate, rql);
	d.addCallback(function(updateMap) {
	    for (facetId in updateMap) {
		var values = updateMap[facetId];
		jqNode(facetId).find('.facetCheckBox').each(function () {
		    var value = this.getAttribute('cubicweb:value');
		    if (!values.contains(value)) {
			if (!jQuery(this).hasClass('facetValueDisabled')) {
			    jQuery(this).addClass('facetValueDisabled');
			}
		    } else {
			if (jQuery(this).hasClass('facetValueDisabled')) {
			    jQuery(this).removeClass('facetValueDisabled');
			}
		    }
		});
	    }
	});
    });
}


var SELECTED_IMG = baseuri()+"data/black-check.png";
var UNSELECTED_IMG = baseuri()+"data/no-check-no-border.png";

function initFacetBoxEvents(root){
    root = root || document;
    jQuery(root).find('form').each(function () {
	var form = jQuery(this);
	var facetargs = evalJSON(form.attr('cubicweb:facetargs'));
	if (facetargs !== undefined && facetargs.length) {
	    form.submit(function() {
	        buildRQL.apply(null, facetargs); //(divid, vid, paginate, extraargs);
	        return false;
	    });
	    form.find('div.facet').each(function() {
		var facet = jQuery(this);
		facet.find('div.facetCheckBox').each(function (i) {
		    this.setAttribute('cubicweb:idx', i);
		});
		facet.find('div.facetCheckBox').click(function () {
		    var $this = jQuery(this);
		    if ($this.hasClass('facetValueSelected')) {
			$this.removeClass('facetValueSelected');
			$this.find('img').attr('src', UNSELECTED_IMG);
			var index = parseInt($this.attr('cubicweb:idx'));
			var shift = jQuery.grep(facet.find('.facetValueSelected'), function (n) {
			    var nindex = parseInt(n.getAttribute('cubicweb:idx'));
			    return nindex > index;
			}).length;
			index += shift;
			var parent = this.parentNode;
			jQuery(parent).find('.facetCheckBox:nth('+index+')').after(this);
		    } else {
			var lastSelected = facet.find('.facetValueSelected:last');
			if (lastSelected.length) {
			    lastSelected.after(this);
			} else {
			    var parent = this.parentNode;
			    jQuery(parent).prepend(this);
			}
			jQuery(this).addClass('facetValueSelected');
			jQuery(this).find('img').attr('src', SELECTED_IMG);
		    }
		    buildRQL.apply(null, facetargs); // (divid, vid, paginate, extraargs);
		    facet.find('.facetBody').animate({scrollTop: 0}, '');
		});
		facet.find('select.facetOperator').change(function() {
		    var nbselected = facet.find('div.facetValueSelected').length;
		    if (nbselected >= 2) {
			buildRQL.apply(null, facetargs); // (divid, vid, paginate, extraargs);
		    }
		});
		facet.find('div.facetTitle').click(function() {
		  facet.find('div.facetBody').toggleClass('hidden').toggleClass('opened');
		  jQuery(this).toggleClass('opened');
		   });

	    });
	}
    });
}

// trigger this function on document ready event if you provide some kind of
// persistent search (eg crih)
function reorderFacetsItems(root){
    root = root || document;
    jQuery(root).find('form').each(function () {
	var form = jQuery(this);
	var facetargs = form.attr('cubicweb:facetargs');
	if (facetargs) {
	    form.find('div.facet').each(function() {
		var facet = jQuery(this);
		var lastSelected = null;
		facet.find('div.facetCheckBox').each(function (i) {
		    var $this = jQuery(this);
		    if ($this.hasClass('facetValueSelected')) {
			if (lastSelected) {
			    lastSelected.after(this);
			} else {
			    var parent = this.parentNode;
			    jQuery(parent).prepend(this);
			}
			lastSelected = $this;
		    }
		});
	    });
	}
    });
}

// we need to differenciate cases where initFacetBoxEvents is called
// with one argument or without any argument. If we use `initFacetBoxEvents`
// as the direct callback on the jQuery.ready event, jQuery will pass some argument
// of his, so we use this small anonymous function instead.
jQuery(document).ready(function() {initFacetBoxEvents();});

CubicWeb.provide('formfilter.js');
