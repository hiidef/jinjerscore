from distutils.core import setup

version = '0.1.0'

setup(
    name='jinjerscore',
    version=version,
    description="An alternate Jinja compiler that produces"
                "Underscore templates.",
    long_description=open('README.rst').read(),
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python',
        'Programming Language :: JavaScript',
        'Operating System :: OS Independent',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'Topic :: Software Development :: Libraries',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: Software Development :: Code Generators',
        'Topic :: Software Development :: Compilers',
    ],
    keywords='jinja jinja2 underscore compiler template',
    author='Brent Hagany',
    author_email='brent@hiidef.com',
    url='http://github.com/hiidef/jinjerscore',
    license='LICENSE.txt',
    packages=['jinjerscore'],
    scripts=[],
    install_requires=[
        'Jinja2 >= 2.6',
    ],
)


