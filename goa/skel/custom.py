def postinit(vreg):
    """this callback is called at the end of initialization process
    and can be used to load explicit modules (views or entities).

    For instance :
    import someviews
    vreg.load_module(someviws)
    """
    # from migration import migrate
    # migrate(vreg)
