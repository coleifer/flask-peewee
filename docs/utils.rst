.. _utils:

Utilities
=========

flask-peewee ships with several useful utilities.  If you're coming from the
django world, some of these functions may look familiar to you.


Getting objects
---------------

:py:func:`get_object_or_404`

    Provides a handy way of getting an object or 404ing if not found, useful
    for urls that match based on ID.

    .. code-block:: python
    
        @app.route('/blog/<title>/')
        def blog_detail(title):
            blog = get_object_or_404(Blog.select().where(Blog.active==True), Blog.title==title)
            return render_template('blog/detail.html', blog=blog)

:py:func:`object_list`

    Wraps the given query and handles pagination automatically. Pagination defaults to ``20``
    but can be changed by passing in ``paginate_by=XX``.

    .. code-block:: python
    
        @app.route('/blog/')
        def blog_list():
            active = Blog.select().where(Blog.active==True)
            return object_list('blog/index.html', active)
    
    .. code-block:: html+jinja

        <!-- template -->
        {% for blog in object_list %}
          {# render the blog here #}
        {% endfor %}
        
        {% if page > 1 %}
          <a href="./?page={{ page - 1 }}">Prev</a>
        {% endif %}
        {% if page < pagination.get_pages() %}
          <a href="./?page={{ page + 1 }}">Next</a>
        {% endif %}

:py:class:`PaginatedQuery`

    A wrapper around a query (or model class) that handles pagination.

    Example:

    .. code-block:: python
    
        query = Blog.select().where(Blog.active==True)
        pq = PaginatedQuery(query, 20)  # 20 items per page

        # assume url was /?page=3
        obj_list = pq.get_list()  # returns 3rd page of results
        
        pq.get_page() # returns "3"
        
        pq.get_pages() # returns total objects / objects-per-page

        pq.get_count() # total number of matching rows

        # a windowed list of page numbers for building pagination controls;
        # None marks a gap to render as an ellipsis. on page 10 of 20:
        pq.get_page_range()  # [1, None, 7, 8, 9, 10, 11, 12, 13, None, 20]

    ``get_page_range(window=N)`` controls how many pages are shown on either side
    of the current page (the default is 3).


Misc
----


.. py:function:: slugify(string)
    :no-index:

    Convert a string into something suitable for use as part of a URL,
    e.g. "This is a url" becomes "this-is-a-url"

    .. code-block:: python
    
        from flask_peewee.utils import slugify
        
        
        class Blog(db.Model):
            title = CharField()
            slug = CharField()
            
            def save(self, *args, **kwargs):
                self.slug = slugify(self.title)
                super(Blog, self).save(*args, **kwargs)

.. py:function:: make_password(raw_password)

    Create a salted hash for the given plain-text password

.. py:function:: check_password(raw_password, enc_password)

    Compare a plain-text password against a salted/hashed password

.. py:data:: PASSWORD_HASH_METHOD

    The hashing method :py:func:`make_password` hands to werkzeug's
    ``generate_password_hash`` -- ``'scrypt'`` by default.  Override it before
    hashing to change the algorithm or work factor, for instance to pick a
    cheaper method that speeds up your test suite:

    .. code-block:: python

        import flask_peewee.utils

        flask_peewee.utils.PASSWORD_HASH_METHOD = 'pbkdf2:sha256:1'

    See ``werkzeug.security.generate_password_hash`` for the accepted values.
