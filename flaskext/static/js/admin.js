var Admin = window.Admin || {};

(function(A, $) {
  var ModelAdminFilter = function(options) {
    this.wrapper = '#filter-wrapper';
    this.form = 'form.modeladmin-filters';
    this.add_button = 'a#add-filter';
    this.remove_button = this.form + ' .remove-filter';
    this.filters = this.form + ' ul';
    this.template_row = this.form + ' #template-row';
    this.field_select = this.form + ' select.field';
  };
  
  ModelAdminFilter.prototype.bind_listeners = function() {
    var self = this;
    
    $(this.add_button).click(function(e) {
      self.add_row(e);
    });
    
    $(this.remove_button).live('click', function(e) {
      self.remove_row(e, $(this));
    });
    
    $(this.field_select).live('change', function(e) {
      self.choose_field(this.value, $(this));
    });
  };
  
  ModelAdminFilter.prototype.choose_field = function(value, elem) {
    var filter_clone = $('#filter-fields').find('#'+value).clone(true),
        filter_elem = $(filter_clone);
    
    elem.siblings('.field-value').remove();
    elem.after(filter_elem);
  };
  
  ModelAdminFilter.prototype.add_row = function(e) {
    var filter_elem = $(this.filters),
        template_row = $(this.template_row),
        row_clone = template_row.clone(true),
        row_elem = $(row_clone);
    
    $(this.wrapper).show();
    
    row_elem.attr('id', '');
    row_elem.removeClass('hidden');
    filter_elem.append(row_elem);
  };
  
  ModelAdminFilter.prototype.remove_row = function(e, elem) {
    elem.parents('li').remove();
    
    if ($(this.filters).children('li').length == 1)
      $(this.wrapper).hide();
  };
  
  A.ModelAdminFilter = ModelAdminFilter;
})(Admin, jQuery);

jQuery(function() {
  jQuery(".alert-message").alert()
});
