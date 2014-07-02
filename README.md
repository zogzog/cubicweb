[pyramid_cubicweb][] is one specific way of integrating [CubicWeb][] with a
[Pyramid][] web application.

### Features

* provides a default route that let a cubicweb instance handle the request.

### Usage

To use, install pyramid_cubicweb in your python environment, 
and then [include][] the package:

    config.include('pyramid_cubicweb')

### Configuration

Requires the following [INI setting / environment variable][]:

* `cubicweb.instance` / `CUBICWEB_INSTANCE`


[pyramid_cubicweb]: https://www.cubicweb.org/project/pyramid-cubicweb
[CubicWeb]: http://www.cubicweb.com/
[Pyramid]: http://pypi.python.org/pypi/pyramid
[include]: http://docs.pylonsproject.org/projects/pyramid/en/latest/api/config.html#pyramid.config.Configurator.include
[INI setting / environment variable]: http://docs.pylonsproject.org/projects/pyramid/en/latest/narr/environment.html#adding-a-custom-setting
