.. _utils:

Utilities
=========

flask-peewee ships with several useful utilities.  If you're coming from the
django world, some of these functions may look familiar to you.


Getting objects
---------------

:py:func:`get_object_or_404`

    .. code-block:: python
    
        @app.route('/blog/<title>/')
        def blog_detail(title):
            blog = get_object_or_404(Blog.select().where(active=True), title=title)
            return render_template('blog/detail.html', blog=blog)

:py:func:`object_list`

    .. code-block:: python
    
        @app.route('/blog/')
        def blog_list():
            active = Blog.select().where(active=True)
            return object_list('blog/index.html', active)
    
    .. code-block:: html
    
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

    .. code-block:: python
    
        query = Blog.select().where(active=True)
        pq = PaginatedQuery(query)
        
        # assume url was /?page=3
        obj_list = pq.get_list()  # returns 3rd page of results
        
        pq.get_page() # returns "3"
        
        pq.get_pages() # returns total objects / objects-per-page


Misc
----


:py:func:`slugify`

    .. code-block:: python
    
        from flask_peewee.utils import slugify
        
        
        class Blog(db.Model):
            title = CharField()
            slug = CharField()
            
            def save(self):
                self.slug = slugify(self.title)
                super(Blog, self).save()
