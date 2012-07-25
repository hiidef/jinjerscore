Jinjerscore provides an alternate parser and compiler derived from Jinja2_,
which rather than generating a final (usually HTML) output, produces an
Underscore_ template that aims to be equivalent to the input. So far, support
for basic control structures and variable output is rather good, and support
is planned for more advanced features like macros and filters.

Jinjerscore also provides a Django_ management command for easy template
generation and a git_ commit hook to help you keep your server-side and client-
side templates in sync.

You can install jinjerscore with pip::

    pip install jinjerscore


You can fork jinjerscore `from its git repository
<http://github.com/hiidef/jinjerscore>`_::

    git clone http://github.com/hiidef/jinjerscore


.. _Jinja2: http://jinja.pocoo.org/
.. _Underscore: http://underscorejs.org/
.. _Django: http://djangoproject.com
.. _git: http://gitscm.org
