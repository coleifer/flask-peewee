from setuptools import setup


setup(
    name='flask-peewee',
    version='0.1.0',
    url='http://github.com/coleifer/flask-peewee/',
    license='BSD',
    author='Charles Leifer',
    author_email='coleifer@gmail.com',
    description='Peewee integration for flask',
    packages=['flaskext'],
    namespace_packages=['flaskext'],
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
    ]
)
