from setuptools import setup, find_packages


setup(
    name='pyramid-cubicweb',
    version='0.3.1',
    description='Integrate CubicWeb with a Pyramid application.',
    author='Christophe de Vienne',
    author_email='username: christophe, domain: unlish.com',
    url='https://www.cubicweb.org/project/pyramid-cubicweb',
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
    install_requires=[
        'pyramid >= 1.5.0',
        'waitress >= 0.8.9',
        'cubicweb >= 3.19.3',
        'wsgicors >= 0.3',
        'pyramid_multiauth',
    ]
)
