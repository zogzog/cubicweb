/** filter form, aka facets, javascript functions
 *
 *  :organization: Logilab
 *  :copyright: 2003-2010 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
 *  :contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
 */

var SELECTED_IMG = baseuri() + "data/black-check.png";
var UNSELECTED_IMG = baseuri() + "data/no-check-no-border.png";
var UNSELECTED_BORDER_IMG = baseuri() + "data/black-uncheck.png";


function copyParam(origparams, newparams, param) {
    var index = jQuery.inArray(param, origparams[0]);
    if (index > - 1) {
        newparams[param] = origparams[1][index];
    }
}


function facetFormContent($form) {
    var names = [];
    var values = [];
    $form.find('.facet').each(function() {
        var facetName = jQuery(this).find('.facetTitle').attr('cubicweb:facetName');
        var facetValues = jQuery(this).find('.facetValueSelected').each(function(x) {
            names.push(facetName);
            values.push(this.getAttribute('cubicweb:value'));
        });
    });
    $form.find('input').each(function() {
        names.push(this.name);
        values.push(this.value);
    });
    $form.find('select option[selected]').each(function() {
        names.push(this.parentNode.name);
        values.push(this.value);
    });
    return [names, values];
}


function buildRQL(divid, vid, paginate, vidargs) {
    jQuery(CubicWeb).trigger('facets-content-loading', [divid, vid, paginate, vidargs]);
    var $form = $('#' + divid + 'Form');
    var zipped = facetFormContent($form);
    zipped[0].push('facetargs');
    zipped[1].push(vidargs);
    var d = loadRemote('json', ajaxFuncArgs('filter_build_rql', null, zipped[0], zipped[1]));
    d.addCallback(function(result) {
        var rql = result[0];
        var $bkLink = jQuery('#facetBkLink');
        if ($bkLink.length) {
            var bkPath = 'view?rql=' + escape(rql);
            if (vid) {
                bkPath += '&vid=' + escape(vid);
            }
            var bkUrl = $bkLink.attr('cubicweb:target') + '&path=' + escape(bkPath);
            $bkLink.attr('href', bkUrl);
        }
        var toupdate = result[1];
        var extraparams = vidargs;
        if (paginate) { extraparams['paginate'] = '1'; } // XXX in vidargs
        // copy some parameters
        // XXX cleanup vid/divid mess
        // if vid argument is specified , the one specified in form params will
        // be overriden by replacePageChunk
        copyParam(zipped, extraparams, 'vid');
        extraparams['divid'] = divid;
        copyParam(zipped, extraparams, 'divid');
        copyParam(zipped, extraparams, 'subvid');
        copyParam(zipped, extraparams, 'fromformfilter');
        // paginate used to know if the filter box is acting, in which case we
        // want to reload action box to match current selection (we don't want
        // this from a table filter)
        extraparams['rql'] = rql;
        if (vid) { // XXX see copyParam above. Need cleanup
            extraparams['vid'] = vid;
        }
        d = $('#' + divid).loadxhtml('json', ajaxFuncArgs('view', extraparams),
                                     null, 'swap');
        d.addCallback(function() {
            // XXX rql/vid in extraparams
            jQuery(CubicWeb).trigger('facets-content-loaded', [divid, rql, vid, extraparams]);
        });
        if (paginate) {
            // FIXME the edit box might not be displayed in which case we don't
            // know where to put the potential new one, just skip this case for
            // now
            var $node = jQuery('#edit_box');
            if ($node.length) {
                $node.loadxhtml('json', ajaxFuncArgs('render', {
                    'rql': rql
                },
                'boxes', 'edit_box'));
            }
            $node = jQuery('#breadcrumbs')
            if ($node.length) {
                $node.loadxhtml('json', ajaxFuncArgs('render', {
                    'rql': rql
                },
                'components', 'breadcrumbs'));
            }
        }
        var d = loadRemote('json', ajaxFuncArgs('filter_select_content', null, toupdate, rql));
        d.addCallback(function(updateMap) {
            for (facetId in updateMap) {
                var values = updateMap[facetId];
                cw.jqNode(facetId).find('.facetCheckBox').each(function() {
                    var value = this.getAttribute('cubicweb:value');
                    if (jQuery.inArray(value, values) == -1) {
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


function initFacetBoxEvents(root) {
    // facetargs : (divid, vid, paginate, extraargs)
    root = root || document;
    jQuery(root).find('form').each(function() {
        var form = jQuery(this);
        // NOTE: don't evaluate facetargs here but in callbacks since its value
        //       may changes and we must send its value when the callback is
        //       called, not when the page is initialized
        var facetargs = form.attr('cubicweb:facetargs');
        if (facetargs !== undefined) {
            form.submit(function() {
                buildRQL.apply(null, cw.evalJSON(form.attr('cubicweb:facetargs')));
                return false;
            });
            form.find('div.facet').each(function() {
                var facet = jQuery(this);
                facet.find('div.facetCheckBox').each(function(i) {
                    this.setAttribute('cubicweb:idx', i);
                });
                facet.find('div.facetCheckBox').click(function() {
                    var $this = jQuery(this);
                    // NOTE : add test on the facet operator (i.e. OR, AND)
                    // if ($this.hasClass('facetValueDisabled')){
                    //          return
                    // }
                    if ($this.hasClass('facetValueSelected')) {
                        $this.removeClass('facetValueSelected');
                        $this.find('img').each(function(i) {
                            if (this.getAttribute('cubicweb:unselimg')) {
                                this.setAttribute('src', UNSELECTED_BORDER_IMG);
                                this.setAttribute('alt', (_('not selected')));
                            }
                            else {
                                this.setAttribute('src', UNSELECTED_IMG);
                                this.setAttribute('alt', (_('not selected')));
                            }
                        });
                        var index = parseInt($this.attr('cubicweb:idx'));
                        // we dont need to move the element when cubicweb:idx == 0
                        if (index > 0) {
                            var shift = jQuery.grep(facet.find('.facetValueSelected'), function(n) {
                                var nindex = parseInt(n.getAttribute('cubicweb:idx'));
                                return nindex > index;
                            }).length;
                            index += shift;
                            var parent = this.parentNode;
                            var $insertAfter = jQuery(parent).find('.facetCheckBox:nth(' + index + ')');
                            if (! ($insertAfter.length == 1 && shift == 0)) {
                                // only rearrange element if necessary
                                $insertAfter.after(this);
                            }
                        }
                    } else {
                        var lastSelected = facet.find('.facetValueSelected:last');
                        if (lastSelected.length) {
                            lastSelected.after(this);
                        } else {
                            var parent = this.parentNode;
                            jQuery(parent).prepend(this);
                        }
                        jQuery(this).addClass('facetValueSelected');
                        var $img = jQuery(this).find('img');
                        $img.attr('src', SELECTED_IMG).attr('alt', (_('selected')));
                    }
                    buildRQL.apply(null, cw.evalJSON(form.attr('cubicweb:facetargs')));
                    facet.find('.facetBody').animate({
                        scrollTop: 0
                    },
                    '');
                });
                facet.find('select.facetOperator').change(function() {
                    var nbselected = facet.find('div.facetValueSelected').length;
                    if (nbselected >= 2) {
                        buildRQL.apply(null, cw.evalJSON(form.attr('cubicweb:facetargs')));
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
function reorderFacetsItems(root) {
    root = root || document;
    jQuery(root).find('form').each(function() {
        var form = jQuery(this);
        if (form.attr('cubicweb:facetargs')) {
            form.find('div.facet').each(function() {
                var facet = jQuery(this);
                var lastSelected = null;
                facet.find('div.facetCheckBox').each(function(i) {
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


// we need to differenciate cases where initFacetBoxEvents is called with one
// argument or without any argument. If we use `initFacetBoxEvents` as the
// direct callback on the jQuery.ready event, jQuery will pass some argument of
// his, so we use this small anonymous function instead.
jQuery(document).ready(function() {
    initFacetBoxEvents();
});
