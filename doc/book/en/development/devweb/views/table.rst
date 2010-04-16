Table view
----------

(:mod:`cubicweb.web.views.tableview`)

*table*
    Creates a HTML table (`<table>`) and call the view `cell` for each cell of
    the result set. Applicable on any result set.

*cell*
    By default redirects to the `final` view if this is a final entity or
    `outofcontext` view otherwise


API
```

.. autoclass:: cubicweb.web.views.tableview.TableView
   :members:
