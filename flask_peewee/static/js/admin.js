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
          , sender = modal.data('sender');
        
        click_cb(sender, repr, data);
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
  
  ModelAdminRawIDField.prototype.on_click = function(sender, repr, data) {
    sender.text(repr);
    sender.parent().find('input[type="hidden"]').val(data);
  }

  /* filter class */
  var ModelAdminFilter = function() {
    this.wrapper = '#filter-wrapper';
    this.add_selector = 'a.field-filter';
    this.lookups_wrapper = '#lookup-fields';
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
    
    /* bind the ajax list */
    this.ajax_list = new ModelAdminAjaxList();
    this.ajax_list.init(function(modal) {return self.get_cb(modal)});
  }
  
  ModelAdminFilter.prototype.single_click = function(sender, repr, data) {
    sender.find('a.fk-lookup').text(repr);
    sender.find('input[type=hidden]').val(data);
  }
  
  ModelAdminFilter.prototype.multi_click = function(sender, repr, data) {
    var add_btn = sender.find('a.fk-lookup')
      , new_btn = $('<a class="btn fk-multi" title="click to remove">'+repr+'</a>')
      , hidden_elem = sender.find('input.dummy').clone();
    
    /* assign the name */
    hidden_elem.attr('name', hidden_elem.attr('id')).removeClass('dummy');
    hidden_elem.val(data);
    
    new_btn.click(function(e) {
      var elem = $(this);
      elem.next('input').remove();
      elem.remove();
    });
    
    /* add to dom */
    add_btn.before(new_btn);
    add_btn.before(hidden_elem);
  }
  
  ModelAdminFilter.prototype.get_cb = function(modal_elem) {
    if (modal_elem.hasClass('modal-multi')) {
      return this.multi_click;
    } else {
      return this.single_click;
    }
  }
  
  ModelAdminFilter.prototype.add_row = function(field_label, field_name, filter_select) {
    var self = this,
        row = [
          , '<div class="clearfix control-group">'
          , '<a class="btn btn-close btn-danger" href="#" title="click to remove">'
          , field_label
          , '</a> </div>'
        ].join('\n'),
        row_elem = $(row).append(filter_select);
    
    row_elem.find('a.btn-close').click(function(e) {
      row_elem.remove();
    });
    
    this.filter_list.prepend(row_elem);
    
    filter_select.change(function(e) {
      self.display_lookup(row_elem, field_name, this.value);
    });
    
    $(this.wrapper).show();
    
    return row_elem;
  }
  
  ModelAdminFilter.prototype.display_lookup = function(row, field_name, lookup) {
    var desired_elem = this.lookups_elem.find('#' + field_name + '__' + lookup)
      , self = this;
    if (desired_elem) {
      var clone = desired_elem.parents('span.wrapper').clone()
        , self = this;
    
      row.find('span.wrapper').remove();
      row.append(clone);
      clone.find('.fk-lookup').click(function(e) {
        var modal = $('#modal-' + field_name + '-' + lookup)
          , modal_input = modal.find('.fk-lookup-input')
          , target = modal.find('ul.result-list');
        
        self.ajax_list.show(modal_input.data('ajax-url'), '', target, self.get_cb(modal));
        modal.data('sender', clone);
        modal.modal('show');
      });
      
      return clone;
    }
  }
  
  /* add a filter of a given type */
  ModelAdminFilter.prototype.add_filter = function(elem) {
    var field_label = elem.text(),
        field_name = elem.attr('id').replace(/^filter\-/, ''),
        filter_select = elem.siblings('select').clone().removeClass('hidden');
    
    return this.add_row(field_label, field_name, filter_select);
  }
  
  /* pull request data and simulate adding a filter */
  ModelAdminFilter.prototype.add_filter_request = function(filter, value, lookup_type, extra) {
    var pieces = filter.split('__'),
        lookup = pieces.pop(),
        field = pieces.join('__'),
        elem = $('a#filter-' + field);

    if (elem) {
      var row = this.add_filter(elem);
      row.find('select').val(lookup);
      
      var input_row = this.display_lookup(row, field, lookup)
        , input_elem = input_row.find('.lookup-input');
    
      if (lookup_type == 'foreign_key' || lookup_type == 'foreign_key_multiple') {
        cb = lookup_type == 'foreign_key' ? this.single_click : this.multi_click;
        $.each(extra, function(pk, repr) {
          cb(input_row, repr, pk);
        });
      } else {
        input_elem.val(value);
      }
    }
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
