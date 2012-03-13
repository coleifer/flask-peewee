var Admin = window.Admin || {};

(function(A, $) {
  var ModelAdminFilter = function() {
    this.wrapper = '#filter-wrapper';
    this.add_selector = 'a.field-filter';
    this.lookups_wrapper = '#lookup-fields';
    this.autocomplete_selector = '.fk-lookup-input';
  };
  
  ModelAdminFilter.prototype.init = function() {
    var self = this;
    
    this.filter_list = $(this.wrapper + ' form div.filter-list');
    this.lookups_elem = $(this.lookups_wrapper);
    
    $(this.add_selector).click(function(e) {
      e.preventDefault();
      self.add_filter($(this));
    });
    
    $(this.autocomplete_selector).keyup(function(e) {
      var elem = $(this)
        , target = elem.siblings('ul.result-list');
      self.ajax_list(elem.data('ajax-url') + elem.val(), target);
    });
  }
  
  ModelAdminFilter.prototype.ajax_list = function(url, target) {
    $.get(url, function(data) {
      target.empty();
      for (var i=0, l=data.object_list.length; i < l; i++) {
        var o = data.object_list[i];
        target.append('<li><a data-object-id="'+o.id+'" href="#">'+o.repr+'</a></li>');
      }
      target.find('a').click(function(e) {
        var data = $(this).data('object-id');
        target.parents('.modal').modal('hide');
      });
    });
  }
  
  ModelAdminFilter.prototype.add_row = function(field_label, field_name, filter_select) {
    var self = this,
        row = [
          , '<div class="clearfix control-group">'
          , '<a class="btn btn-close span2" href="#">'
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
        
        self.ajax_list(modal_input.data('ajax-url'), target);
        modal.modal('show');
      });
      
      return clone;
    }
  }
  
  ModelAdminFilter.prototype.add_filter = function(elem) {
    var field_label = elem.text(),
        field_name = elem.attr('id').replace(/^filter\-/, ''),
        filter_select = elem.siblings('select').clone().removeClass('hidden');
    
    return this.add_row(field_label, field_name, filter_select);
  }
  
  ModelAdminFilter.prototype.add_filter_request = function(filter, value) {
    var pieces = filter.split('__'),
        lookup = pieces.pop(),
        field = pieces.join('__'),
        elem = $('a#filter-' + field);
    
    if (elem) {
      var row = this.add_filter(elem);
      row.find('select').val(lookup);
      
      var input_row = this.display_lookup(row, field, lookup)
        , input_elem = input_row.find('.lookup-input');
      input_elem.val(value);
    }
  }
  
  A.ModelAdminFilter = ModelAdminFilter;
  
  A.index_submit = function(action) {
    $('form#model-list input[name=action]').val(action);
    $('form#model-list').submit();
  };
})(Admin, jQuery);

jQuery(function() {
  jQuery(".alert").alert()
});
