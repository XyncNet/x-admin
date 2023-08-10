$('#gid').select2({
  ajax: {
    delay: 250,
    dataType: 'json',
    url: p => '/addr-opts/'+p.term,
    data: '',
    processResults: data => data,
    cache: true
  },
  minimumInputLength: 5,
}).on('select2:select', e => {
    $('#formatted').val(e.params.data.text)
    $.getJSON('/addr/'+e.params.data.id, data => {
      $.each(data.address_components, function(i, obj) {
        $('#'+obj.types[0]).val(obj.short_name)
      });
      $('#plus_code').val(data.plus_code & data.plus_code.global_code)
      const [y, x] = document.getElementsByName('loc[]')
      y.value = data.geometry.location.lat
      x.value = data.geometry.location.lng
    });
})