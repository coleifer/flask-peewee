.. _utils:

Utilities
=========

flask-peewee ships with several useful utilities.  If you're coming from the
django world, some of these functions may look familiar to you.

.. py:function:: get_object_or_404(query_or_model, **query)

    Given any number of keyword arguments, retrieve a single instance of the
    ``query_or_model`` parameter or return a 404
    
    :param query_or_model: either a ``Model`` class or a ``SelectQuery``
    :param **query: any number of keyword arguments, e.g. ``id=1``
    :rtype: either a single model instance or raises a ``NotFound`` (404 response)

.. py:function:: object_list(template_name, qr[, var_name='object_list'[, **kwargs]])

    Returns a rendered template, passing in a paginated version of the query.
    
    :param template_name: a string representation of a path to a template
    :param qr: a ``SelectQuery``
    :param var_name: context variable name to use when rendering the template
    :param **kwargs: any arbitrary keyword arguments to pass to the template during rendering
    :rtype: rendered ``Response``

.. py:function:: get_next()

    :rtype: a URL suitable for redirecting to

.. py:function:: slugify(s)

    Use a regular expression to make arbitrary string ``s`` URL-friendly

    :param s: any string to be slugified
    :rtype: url-friendly version of string ``s``

.. py:class:: PaginatedQuery

    Wraps a ``SelectQuery`` with helpers for paginating.
    
    .. py:attribute:: page_var = 'page'
    
        GET argument to use for determining request page
    
    .. py:method:: __init__(query_or_model, paginate_by)
    
        :param query_or_model: either a ``Model`` class or a ``SelectQuery``
        :param paginate_by: number of results to return per-page
    
    .. py:method:: get_list()
    
        :rtype: a list of objects for the request page
    
    .. py:method:: get_page()
    
        :rtype: an integer representing the currently requested page
    
    .. py:method:: get_pages()
    
        :rtype: the number of pages in the entire result set
