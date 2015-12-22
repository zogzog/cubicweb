%if 0%{?el5}
%define python python26
%define __python /usr/bin/python2.6
%else
%define python python
%define __python /usr/bin/python
%endif

Name:           cubicweb
Version:        3.21.5
Release:        logilab.1%{?dist}
Summary:        CubicWeb is a semantic web application framework
Source0:        http://download.logilab.org/pub/cubicweb/cubicweb-%{version}.tar.gz
License:        LGPLv2+
Group:          Development/Languages/Python
Vendor:         Logilab <contact@logilab.fr>
Url:            http://www.cubicweb.org/project/cubicweb

BuildRoot:      %{_tmppath}/%{name}-%{version}-%{release}-buildroot
BuildArch:      noarch

Requires:       %{python}
Requires:       %{python}-six >= 1.4.0
Requires:       %{python}-logilab-common >= 0.63.1
Requires:       %{python}-logilab-mtconverter >= 0.8.0
Requires:       %{python}-rql >= 0.31.2
Requires:       %{python}-yams >= 0.41.1
Requires:       %{python}-logilab-database >= 1.14.0
Requires:       %{python}-passlib
Requires:       %{python}-lxml
Requires:       %{python}-twisted-web
Requires:       %{python}-markdown
Requires:       %{python}-tz
# the schema view uses `dot'; at least on el5, png output requires graphviz-gd
Requires:       graphviz-gd
Requires:       gettext

BuildRequires:  %{python}

%description
a repository of entities / relations for knowledge management

%prep
%setup -q
%if 0%{?el5}
# change the python version in shebangs
find . -name '*.py' -type f -print0 |  xargs -0 sed -i '1,3s;^#!.*python.*$;#! /usr/bin/python2.6;'
%endif

%install
NO_SETUPTOOLS=1 %{__python} setup.py --quiet install --no-compile --prefix=%{_prefix} --root="$RPM_BUILD_ROOT"
mkdir -p $RPM_BUILD_ROOT/var/log/cubicweb

%clean
rm -rf $RPM_BUILD_ROOT

%files 
%defattr(-, root, root)
%dir /var/log/cubicweb
/*

