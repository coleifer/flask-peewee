var Admin = window.Admin || {};

(function(A, $) {
  var ModelAdminFilter = function(options) {
    this.wrapper = '#filter-wrapper';
    this.add_selector = 'a.field-filter';
    this.lookups_wrapper = '#lookup-fields';
  };
  
  ModelAdminFilter.prototype.init = function() {
    var self = this;
    
    this.form = $(this.wrapper + ' form');
    this.lookups_elem = $(this.lookups_wrapper);
    
    $(this.add_selector).click(function(e) {
      self.add_filter($(this), e);
    });
  }
  
  ModelAdminFilter.prototype.add_filter = function(elem, e) {
    var filter_clone = elem.siblings('select').clone().removeClass('hidden'),
        field_name = elem.attr('id').replace(/^filter\-/, ''),
        self = this;
    
    var row = [
        , '<div class="clearfix">'
        , '<a class="btn small" href="#" onclick="$(this).parent().remove();">',
        , elem.text()
        , '</a> </div>'
      ].join('\n'),
      row_elem = $(row).append(filter_clone);
    
    this.form.prepend(row_elem);
    
    filter_clone.change(function(e) {
      var desired_elem = self.lookups_elem.find('#' + field_name + '__' + this.value);
      if (desired_elem) {
        row_elem.find('.lookup-input').remove();
        row_elem.append(desired_elem.clone());
      }
    });
  }
  
  A.ModelAdminFilter = ModelAdminFilter;

})(Admin, jQuery);

jQuery(function() {
  jQuery(".alert-message").alert()
});
