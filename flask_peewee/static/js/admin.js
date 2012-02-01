var Admin = window.Admin || {};

(function(A, $) {
  var ModelAdminFilter = function() {
    this.wrapper = '#filter-wrapper';
    this.add_selector = 'a.field-filter';
    this.lookups_wrapper = '#lookup-fields';
  };
  
  ModelAdminFilter.prototype.init = function() {
    var self = this;
    
    this.filter_list = $(this.wrapper + ' form div.filter-list');
    this.lookups_elem = $(this.lookups_wrapper);
    
    $(this.add_selector).click(function(e) {
      e.preventDefault();
      self.add_filter($(this));
    });
  }
  
  ModelAdminFilter.prototype.add_row = function(field_label, field_name, filter_select) {
    var self = this,
        row = [
          , '<div class="clearfix control-group">'
          , '<a class="btn span2" href="#">'
          , field_label
          , '</a> </div>'
        ].join('\n'),
        row_elem = $(row).append(filter_select);
    
    row_elem.find('a.btn').click(function(e) {
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
    var desired_elem = this.lookups_elem.find('#' + field_name + '__' + lookup);
    if (desired_elem) {
      var clone = desired_elem.clone();
      row.find('.lookup-input').remove();
      row.append(clone);
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
      
      var input_elem = this.display_lookup(row, field, lookup);
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
