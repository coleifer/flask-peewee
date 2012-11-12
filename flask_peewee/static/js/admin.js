var Admin = window.Admin || {};

(function(A, $) {

  /* paginated list of models displayed in a modal window */
  function ModelAdminAjaxList() {
    this.autocomplete_selector = '.fk-lookup-input';
  }

  ModelAdminAjaxList.prototype.init = function(click_cb_factory) {
    var self = this;

    /* bind keyboard handler for input */
    $(this.autocomplete_selector).keyup(function(e) {
      var elem = $(this)
        , target = elem.siblings('ul.result-list')
        , modal = elem.parents('.modal');

      self.show(elem.data('ajax-url'), elem.val(), target, click_cb_factory(modal));
    });

    /* bind next/prev buttons */
    $('.modal a.next, .modal a.previous').click(function(e) {
      var elem = $(this)
        , modal = elem.parents('.modal')
        , input_elem = modal.find(self.autocomplete_selector)
        , target = input_elem.siblings('ul.result-list')
        , page = elem.data('page');

      if (!elem.hasClass('disabled')) {
        self.show(input_elem.data('ajax-url')+'&page='+page, input_elem.val(), target, click_cb_factory(modal));
      }
    });
  }

  ModelAdminAjaxList.prototype.show = function(url, query, target, click_cb) {
    var modal = target.parents('.modal')
      , next_btn = modal.find('a.next')
      , prev_btn = modal.find('a.previous')
      , self = this;

    $.get(url+'&query='+query, function(data) {
      target.empty();
      for (var i=0, l=data.object_list.length; i < l; i++) {
        var o = data.object_list[i];
        target.append('<li><a data-object-id="'+o.id+'" href="#">'+o.repr+'</a></li>');
      }

      if (data.prev_page) {
        prev_btn.removeClass('disabled');
        prev_btn.data('page', data.prev_page);
      } else {
        prev_btn.addClass('disabled');
      }
      if (data.next_page) {
        next_btn.removeClass('disabled');
        next_btn.data('page', data.next_page);
      } else {
        next_btn.addClass('disabled');
      }

      target.find('a').click(function(e) {
        var data = $(this).data('object-id')
          , repr = $(this).text()
          , html = $(this).html()
          , sender = modal.data('sender');

        click_cb(sender, repr, data, html);
        target.parents('.modal').modal('hide');
      });
    });
  }

  var ModelAdminRawIDField = function(field_name) {
    this.field_name = field_name;
    this.selector = 'input#'+this.field_name;
  }

  ModelAdminRawIDField.prototype.init = function(repr) {
    var self = this
      , repr = repr || 'Select...'
      , hidden_elem = $(this.selector)
      , new_elem = $('<a class="btn btn-primary" href="#">'+repr+'</a>');

    /* bind the ajax list */
    this.ajax_list = new ModelAdminAjaxList();
    this.ajax_list.init(function(modal) {return self.on_click});

    new_elem.click(function(e) {
      e.preventDefault();
      var modal = $('#modal-' + self.field_name)
        , modal_input = modal.find('.fk-lookup-input')
        , target = modal.find('ul.result-list');

      self.ajax_list.show(modal_input.data('ajax-url'), '', target, self.on_click);
      modal.data('sender', $(this));
      modal.modal('show');
    });
    hidden_elem.after(new_elem);
  }

  ModelAdminRawIDField.prototype.on_click = function(sender, repr, data, html) {
    if (repr) {
      sender.text(repr);
    } else {
      sender.html(html);
    }
    sender.parent().find('input[type="hidden"]').val(data);
  }

  /* filter class */
  var ModelAdminFilter = function() {
    this.wrapper = '#filter-wrapper'; /* wrapper around the form that submits filters */
    this.add_selector = 'a.field-filter'; /* links to add filters (in the navbar) */
    this.lookups_wrapper = '#filter-fields'; /* wrapper around the filter fields */
  }

  ModelAdminFilter.prototype.init = function() {
    var self = this;

    this.filter_list = $(this.wrapper + ' form div.filter-list');
    this.lookups_elem = $(this.lookups_wrapper);

    /* bind the "add filter" click behavior */
    $(this.add_selector).click(function(e) {
      e.preventDefault();
      self.add_filter($(this));
    });
  }

  ModelAdminFilter.prototype.chosen_handler = function(data) {
    var results = {}
      , object_list = data.object_list;
    for (var i = 0, l = object_list.length; i < l; i++) {
      var item = object_list[i];
      results[item['id']] = item['repr']
    }
    return results;
  }

  ModelAdminFilter.prototype.add_row = function(qf_v, qf_s, ival, sval) {
    var select_elem = this.lookups_elem.find('#'+qf_s),
        input_elem = this.lookups_elem.find('#'+qf_v),
        field_label = $('#filter-'+qf_s).text();

    var self = this,
        select_clone = select_elem.clone(),
        input_clone = input_elem.clone(),
        row = [
          , '<div class="clearfix control-group">'
          , '<a class="btn btn-close btn-danger" href="#" title="click to remove">'
          , field_label
          , '</a> </div>'
        ].join('\n'),
        row_elem = $(row).append(select_clone).append(input_clone);

    if (ival && sval) {
        select_clone.val(sval);
        input_clone.val(ival);
    }

    row_elem.find('a.btn-close').click(function(e) {
      row_elem.remove();
    });

    this.filter_list.prepend(row_elem);

    /* reload our jquery plugin stuff */
    if (input_clone.hasClass('datetime-widget')) {
      $(input_clone[0]).datepicker({format: 'yyyy-mm-dd'});
    } else if (input_clone.hasClass('date-widget')) {
      input_clone.datepicker({format: 'yyyy-mm-dd'});
    } else if (input_clone.data('role') === 'chosen') {
      input_clone.chosen();
    } else if (input_clone.data('role') === 'ajax-chosen') {
      input_clone.ajaxChosen({
          type: 'GET',
          url: input_clone.data('source'),
          jsonTermKey: 'query',
          dataType: 'json',
          data: {'field': input_clone.data('param')},
          minTermLength: 2
      }, this.chosen_handler);
    }

    $(this.wrapper).show();

    /* twitter bootfap doesn't wanna close the dropdown */
    $('.dropdown.open .dropdown-toggle').dropdown('toggle');

    return row_elem;
  }

  /* add a filter of a given type */
  ModelAdminFilter.prototype.add_filter = function(elem) {
    return this.add_row(elem.data('field'), elem.data('select'));
  }

  /* pull request data and simulate adding a filter */
  ModelAdminFilter.prototype.add_filter_request = function(qf_s, filter_idx, qf_v, filter_val) {
    return this.add_row(qf_v, qf_s, filter_val, filter_idx);
  }

  /* export */
  A.ModelAdminRawIDField = ModelAdminRawIDField;
  A.ModelAdminFilter = ModelAdminFilter;

  /* bind a simple listener */
  A.index_submit = function(action) {
    $('form#model-list input[name=action]').val(action);
    $('form#model-list').submit();
  }
})(Admin, jQuery);

jQuery(function() {
  jQuery(".alert").alert()
});
