from xml.etree.ElementTree import QName
from pysixt.standard.xhtml_xslfo.transformer import XHTML2FOTransformer
from pysixt.utils.xslfo.standard import cm
from pysixt.utils.xslfo import SimplePageMaster
from pysixt.standard.xhtml_xslfo.default_styling import default_styles
from pysixt.standard.xhtml_xslfo import XHTML_NS


class ReportTransformer(XHTML2FOTransformer):
    """
    Class transforming an XHTML input tree into a FO document
    displaying reports (one report for each <div class="contentmain">
    element in the input tree.
    """

    def __init__(self, section,
                 page_width=21.0, page_height=29.7,
                 margin_top=1.0, margin_bottom=1.0,
                 margin_left=1.0, margin_right=1.0,
                 header_footer_height=0.75,
                 standard_font_size=11.0, default_lang=u"fr" ):
        """
        Initializes a transformer turning an XHTML input tree
        containing <div class="contentmain"> elements representing
        main content sections into a FO output tree displaying the
        reports.

        page_width: float - width of the page (in cm)
        page_height: float - height of the page (in cm)
        margin_top: float - top margin of the page (in cm)
        margin_bottom: float - bottom margin of the page (in cm)
        margin_left: float - left margin of the page (in cm)
        margin_right: float - right margin of the page (in cm)
        header_footer_height: float - height of the header or the footer of the
                              page that the page number (if any) will be
                              inserted in.
        standard_font_size: float - standard size of the font (in pt)
        default_lang: u"" - default language (used for hyphenation)
        """
        self.section = section
        self.page_width = page_width
        self.page_height = page_height

        self.page_tmargin = margin_top
        self.page_bmargin = margin_bottom
        self.page_lmargin = margin_left
        self.page_rmargin = margin_right

        self.hf_height = header_footer_height

        self.font_size = standard_font_size
        self.lang = default_lang

        XHTML2FOTransformer.__init__(self)


    def define_pagemasters(self):
        """
        Defines the page masters for the FO output document.
        """
        pm = SimplePageMaster(u"page-report")
        pm.set_page_dims( self.page_width*cm, self.page_height*cm )
        pm.set_page_margins({u'top'   : self.page_tmargin*cm,
                             u'bottom': self.page_bmargin*cm,
                             u'left'  : self.page_lmargin*cm,
                             u'right' : self.page_rmargin*cm })
        pm.add_peripheral_region(u"end",self.hf_height)
        dims = {}
        dims[u"bottom"] = self.hf_height + 0.25
        pm.set_main_region_margins(dims)
        return [pm]

    def _visit_report(self, in_elt, _out_elt, params):
        """
        Specific visit function for the input <div> elements whose class is
        "report". The _root_visit method of this class selects these input
        elements and asks the process of these elements with this specific
        visit function.
        """

        ps = self.create_pagesequence(u"page-report")
        props = { u"force-page-count": u"no-force",
                  u"initial-page-number": u"1",
                  u"format": u"1", }
        self._output_properties(ps,props)

        sc = self.create_staticcontent(ps, u"end")
        sc_bl = self.create_block(sc)
        attrs = { u"hyphenate": u"false", }
        attrs[u"font-size"] = u"%.1fpt" %(self.font_size*0.7)
        attrs[u"language"] = self.lang
        attrs[u"text-align"] = u"center"
        self._output_properties(sc_bl,attrs)
        sc_bl.text = u"Page" + u" " # ### Should be localised!
        pn = self.create_pagenumber(sc_bl)
        pn.tail = u"/"
        lpn = self.create_pagenumbercitation( sc_bl,
                                              u"last-block-of-report-%d" % params[u"context_pos"]
                                              )


        fl = self.create_flow(ps,u"body")
        bl = self.create_block(fl)

        # Sets on the highest block element the properties of the XHTML body
        # element. These properties (at the least the inheritable ones) will
        # be inherited by all the future FO elements.
        bodies = list(self.in_tree.getiterator(QName(XHTML_NS,u"body")))
        if len(bodies) > 0:
            attrs = self._extract_properties([bodies[0]])
        else:
            attrs = default_styles[u"body"].copy()
        attrs[u"font-size"] = u"%.1fpt" %self.font_size
        attrs[u"language"] = self.lang
        self._output_properties(bl,attrs)

        # Processes the report content
        self._copy_text(in_elt,bl)
        self._process_nodes(in_elt.getchildren(),bl)

        # Inserts an empty block at the end of the report in order to be able
        # to compute the last page number of this report.
        last_bl = self.create_block(bl)
        props = { u"keep-with-previous": u"always", }
        props[u"id"] = u"last-block-of-report-%d" % params[u"context_pos"]
        self._output_properties(last_bl,props)


    def _root_visit(self):
        """
        Visit function called when starting the process of the input tree.
        """
        content = [ d for d in self.in_tree.getiterator(QName(XHTML_NS,u"div"))
                    if d.get(u"id") == self.section ]
        # Asks the process of the report elements with a specific visit
        # function
        self._process_nodes(content, self.fo_root,
                            with_function=self._visit_report)

