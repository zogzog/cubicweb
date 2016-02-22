# for el5, force use of python2.6
%if 0%{?el5}
%define python python26
%define __python /usr/bin/python2.6
%else
%define python python
%define __python /usr/bin/python
%endif

Name:           cubicweb-pyramid
Version:        0.4.0
Release:        1%{?dist}
Summary:        Add the 'pyramid' command to cubicweb-ctl

Group:          Development/Languages
License:        LGPL
URL:            https://www.cubicweb.org/project/cubicweb-pyramid
Source0:        http://pypi.python.org/packages/source/c/cubicweb-pyramid/cubicweb-pyramid-%{version}.tar.gz
BuildArch:      noarch
BuildRoot:      %{_tmppath}/%{name}-%{version}-%{release}-buildroot

Requires:       cubicweb >= 3.20.0
Requires:       python-waitress >= 0.8.9
Requires:       pyramid-cubicweb
Requires:       python-wsgicors
BuildRequires:  python-setuptools

%description
Add the 'pyramid' command to cubicweb-ctl
CubicWeb is a semantic web application framework.

Add the 'pyramid' command to cubicweb-ctl

This package will install all the components you need to run the 
cubicweb-pyramid application (cube :)..

%prep
%setup -q -n cubicweb-pyramid-%{version}
%if 0%{?el5}
# change the python version in shebangs
find . -name '*.py' -type f -print0 |  xargs -0 sed -i '1,3s;^#!.*python.*$;#! /usr/bin/python2.6;'
%endif

%install
NO_SETUPTOOLS=1 %{__python} setup.py --quiet install --no-compile --prefix=%{_prefix} --root="$RPM_BUILD_ROOT"
# remove generated .egg-info file
rm -rf $RPM_BUILD_ROOT/usr/lib/python*


%clean
rm -rf $RPM_BUILD_ROOT

%files
%defattr(-, root, root)
%{_prefix}/share/cubicweb*
