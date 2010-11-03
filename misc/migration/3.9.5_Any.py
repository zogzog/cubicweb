if not rql('CWConstraintType X WHERE X name "RQLUniqueConstraint"',
           ask_confirm=False):
    rql('INSERT CWConstraintType X: X name "RQLUniqueConstraint"',
        ask_confirm=False)
