import sys
from setuptools import setup, find_packages

requirements = ['Flask', 'werkzeug', 'jinja2', 'peewee>=3.0.0', 'wtforms', 'wtf-peewee']
if sys.version_info[:2] < (2, 6):
    requirements.append('simplejson')

setup(
    name='flask-peewee',
    version='3.0.3',
    url='http://github.com/coleifer/flask-peewee/',
    license='MIT',
    author='Charles Leifer',
    author_email='coleifer@gmail.com',
    description='Peewee integration for flask',
    packages=find_packages(),
    package_data = {
        'flask_peewee': [
            'static/*/*.css',
            'static/*/*.js',
            'static/*/*.gif',
            'static/*/*.png',
            'templates/*.html',
            'templates/*/*.html',
            'templates/*/*/*.html',
            'tests/*.html',
            'tests/*/*.html',
        ],
    },
    zip_safe=False,
    platforms='any',
    install_requires=requirements,
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
