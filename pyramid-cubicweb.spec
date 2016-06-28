# for el5, force use of python2.6
%if 0%{?el5}
%define python python26
%define __python /usr/bin/python2.6
%else
%define python python
%define __python /usr/bin/python
%endif
%{!?_python_sitelib: %define _python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print get_python_lib()")}

Name:           pyramid-cubicweb
Version:        0.7.0
Release:        1%{?dist}
Summary:        Integrate CubicWeb with a Pyramid application

Group:          Development/Languages
License:        LGPL
URL:            https://www.cubicweb.org/project/pyramid-cubicweb
Source0:        http://pypi.python.org/packages/source/p/pyramid-cubicweb/pyramid-cubicweb-%{version}.tar.gz
BuildArch:      noarch
BuildRoot:      %{_tmppath}/%{name}-%{version}-%{release}-buildroot

Requires:       cubicweb >= 3.20.0
Requires:       python-pyramid >= 1.5.0
Requires:       python-wsgicors >= 0.3.0
Requires:       python-pyramid-multiauth >= 0.5.0
BuildRequires:  python-setuptools

%description
Integrate CubicWeb with a Pyramid application
Provides pyramid extensions to load a CubicWeb instance and serve it through
the pyramid stack.

%prep
%setup -q -n pyramid-cubicweb-%{version}
%if 0%{?el5}
# change the python version in shebangs
find . -name '*.py' -type f -print0 |  xargs -0 sed -i '1,3s;^#!.*python.*$;#! /usr/bin/python2.6;'
%endif

%install
NO_SETUPTOOLS=1 %{__python} setup.py --quiet install --no-compile --prefix=%{_prefix} --root="$RPM_BUILD_ROOT"


%clean
rm -rf $RPM_BUILD_ROOT

%files
%defattr(-, root, root)
%{_python_sitelib}/*
