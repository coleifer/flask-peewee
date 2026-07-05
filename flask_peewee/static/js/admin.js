var Admin = window.Admin || {};

(function(A) {

  function getJSON(url, cb) {
    fetch(url, {credentials: 'same-origin'})
      .then(function(resp) { return resp.json(); })
      .then(cb);
  }

  function debounce(fn, wait) {
    var timer = null;
    return function() {
      var args = arguments, self = this;
      clearTimeout(timer);
      timer = setTimeout(function() { fn.apply(self, args); }, wait);
    };
  }

  /* paginated list of models displayed in a modal window */
  function AjaxModalList(modal_elem, on_select) {
    var self = this;
    this.modal_elem = modal_elem;
    this.modal = new bootstrap.Modal(modal_elem);
    this.input = modal_elem.querySelector('.fk-lookup-input');
    this.list = modal_elem.querySelector('ul.result-list');
    this.next_btn = modal_elem.querySelector('a.next');
    this.prev_btn = modal_elem.querySelector('a.previous');
    this.on_select = on_select;

    this.input.addEventListener('keyup', debounce(function() {
      self.load(self.input.dataset.ajaxUrl);
    }, 200));

    [this.prev_btn, this.next_btn].forEach(function(btn) {
      btn.addEventListener('click', function(e) {
        e.preventDefault();
        if (!btn.classList.contains('disabled') && btn.dataset.page) {
          self.load(self.input.dataset.ajaxUrl + '&page=' + btn.dataset.page);
        }
      });
    });
  }

  AjaxModalList.prototype.load = function(url) {
    var self = this;
    getJSON(url + '&query=' + encodeURIComponent(this.input.value), function(data) {
      self.list.innerHTML = '';
      data.object_list.forEach(function(o) {
        var link = document.createElement('a');
        link.href = '#';
        link.textContent = o.repr;
        link.addEventListener('click', function(e) {
          e.preventDefault();
          self.on_select(o);
          self.modal.hide();
        });
        var li = document.createElement('li');
        li.appendChild(link);
        self.list.appendChild(li);
      });

      [[self.prev_btn, data.prev_page], [self.next_btn, data.next_page]].forEach(function(pair) {
        pair[0].classList.toggle('disabled', !pair[1]);
        pair[0].dataset.page = pair[1] || '';
      });
    });
  };

  AjaxModalList.prototype.open = function() {
    this.load(this.input.dataset.ajaxUrl);
    this.modal.show();
  };

  /* raw-id foreign key: hidden input + button that opens a lookup modal */
  A.ModelAdminRawIDField = function(field_name) {
    this.field_name = field_name;
  };

  A.ModelAdminRawIDField.prototype.init = function(repr) {
    var hidden_elem = document.getElementById(this.field_name),
        modal_elem = document.getElementById('modal-' + this.field_name),
        btn = document.createElement('a');

    btn.className = 'btn btn-outline-primary';
    btn.href = '#';
    btn.textContent = repr || 'Select...';

    var list = new AjaxModalList(modal_elem, function(o) {
      btn.textContent = o.repr;
      hidden_elem.value = o.id;
    });

    btn.addEventListener('click', function(e) {
      e.preventDefault();
      list.open();
    });
    hidden_elem.insertAdjacentElement('afterend', btn);
  };

  /* upgrade an ajax-select: a search input that repopulates the select's
     options from the model admin's ajax_list endpoint */
  A.ajaxSelect = function(select) {
    var search = document.createElement('input');
    search.type = 'text';
    search.placeholder = 'Type to search...';
    search.className = 'form-control form-control-sm w-auto';

    search.addEventListener('input', debounce(function() {
      var url = select.dataset.source +
        '?field=' + encodeURIComponent(select.dataset.param) +
        '&query=' + encodeURIComponent(search.value);
      getJSON(url, function(data) {
        select.innerHTML = '';
        data.object_list.forEach(function(o) {
          var opt = document.createElement('option');
          opt.value = o.id;
          opt.textContent = o.repr;
          select.appendChild(opt);
        });
      });
    }, 200));

    select.insertAdjacentElement('beforebegin', search);
  };

  /* filter class */
  A.ModelAdminFilter = function() {
    this.wrapper = document.getElementById('filter-wrapper');
    this.lookups_elem = document.getElementById('filter-fields');
    this.filter_list = this.wrapper && this.wrapper.querySelector('.filter-list');
  };

  A.ModelAdminFilter.prototype.init = function() {
    var self = this;
    document.querySelectorAll('a.field-filter').forEach(function(link) {
      link.addEventListener('click', function(e) {
        e.preventDefault();
        self.add_row(link.dataset.field, link.dataset.select);
      });
    });

    if (!this.filter_list) return;

    this.filter_list.addEventListener('click', function(e) {
      var btn = e.target.closest('a.remove-filter');
      if (btn) {
        e.preventDefault();
        btn.closest('.filter-row').remove();
      }
    });

    /* rows for active filters are rendered server-side */
    this.filter_list.querySelectorAll('.filter-row').forEach(function(row) {
      self.bind_row(row);
    });
  };

  A.ModelAdminFilter.prototype.bind_row = function(row) {
    var select_elem = row.children[1],
        input_elem = row.children[2];

    /* certain operations want a different input type than the field's
       default, e.g. "within X days ago" takes a number, not a date */
    if (input_elem.tagName === 'INPUT') {
      var lookup = this.lookups_elem.querySelector('[name="' + input_elem.name + '"]'),
          default_type = lookup ? lookup.type : input_elem.type;
      var sync_input_type = function() {
        var opt = select_elem.selectedOptions[0];
        input_elem.type = (opt && opt.dataset.inputType) || default_type;
      };
      select_elem.addEventListener('change', sync_input_type);
      sync_input_type();
    }

    if (input_elem.dataset.role === 'ajax-select') {
      A.ajaxSelect(input_elem);
    }
  };

  A.ModelAdminFilter.prototype.add_row = function(qf_v, qf_s) {
    var select_clone = this.lookups_elem.querySelector('#' + CSS.escape(qf_s)).cloneNode(true),
        input_clone = this.lookups_elem.querySelector('#' + CSS.escape(qf_v)).cloneNode(true),
        field_label = document.getElementById('filter-' + qf_s).textContent.trim();

    select_clone.removeAttribute('id');
    input_clone.removeAttribute('id');
    input_clone.classList.add(
      input_clone.tagName === 'SELECT' ? 'form-select' : 'form-control',
      input_clone.tagName === 'SELECT' ? 'form-select-sm' : 'form-control-sm',
      'w-auto');

    var row = document.createElement('div');
    row.className = 'filter-row d-flex align-items-center gap-2 mb-2';

    var remove_btn = document.createElement('a');
    remove_btn.className = 'btn btn-danger btn-sm remove-filter';
    remove_btn.href = '#';
    remove_btn.title = 'click to remove';
    remove_btn.textContent = field_label;

    row.appendChild(remove_btn);
    row.appendChild(select_clone);
    row.appendChild(input_clone);

    this.bind_row(row);
    this.filter_list.prepend(row);
    this.wrapper.classList.remove('d-none');

    return row;
  };

  /* add a filter of a given type */
  A.ModelAdminFilter.prototype.add_filter = function(elem) {
    return this.add_row(elem.dataset.field, elem.dataset.select);
  };

  /* bulk action helper for the model list */
  A.index_submit = function(action) {
    var form = document.getElementById('model-list');
    form.querySelector('input[name=action]').value = action;
    form.submit();
  };

})(Admin);
