from setuptools import setup, find_packages


setup(
    name='flask-peewee',
    version='0.1.1',
    url='http://github.com/coleifer/flask-peewee/',
    license='BSD',
    author='Charles Leifer',
    author_email='coleifer@gmail.com',
    description='Peewee integration for flask',
    packages=find_packages(),
    package_data = {
        'flaskext': [
            'static/*/*.css',
            'static/*/*.js',
            'static/*/*.gif',
            'templates/*.html',
            'templates/*/*.html',
            'templates/*/*/*.html',
            'tests/*.html',
            'tests/*/*.html',
        ],
    },
    zip_safe=False,
    platforms='any',
    install_requires=[
        'Flask', 'werkzeug', 'jinja2', 'peewee', 'wtforms', 'wtf-peewee',
    ],
    classifiers=[
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'Topic :: Software Development :: Libraries :: Python Modules'
    ],
    test_suite='runtests.runtests',
)
