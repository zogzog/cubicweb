from setuptools import setup, find_packages


setup(
    name='pyramid_cubicweb',
    version='0.1',
    description='Integrate CubicWeb with a Pyramid application.',
    author='Christophe de Vienne',
    author_email='username: christophe, domain: unlish.com',
    url='http://bitbucket.com/cdevienne/pyramid_cubicweb',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: Public Domain',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Framework :: Pylons',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Internet :: WWW/HTTP :: WSGI',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    install_requires=[]
)
