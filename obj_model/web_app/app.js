$(document).foundation()

function change_method(evt){
    var method = $('#method').val();
    switch(method) {
        case 'convert':
            $('#label_model').hide()
            $('#label_workbook').show()
            $('#label_workbook-2').hide()
            $('#label_format').show()
            break;
        case 'diff':
            $('#label_model').show()
            $('#label_workbook').show()
            $('#label_workbook-2').show()
            $('#label_format').hide()
            break;
        case 'gen-template':
            $('#label_model').hide()
            $('#label_workbook').hide()
            $('#label_workbook-2').hide()
            $('#label_format').show()
            break;
        case 'init-schema':
            $('#label_model').hide()
            $('#label_workbook').hide()
            $('#label_workbook-2').hide()
            $('#label_format').hide()
            break;
        case 'normalize':
            $('#label_model').show()
            $('#label_workbook').show()
            $('#label_workbook-2').hide()
            $('#label_format').show()
            break;
        case 'validate':
            $('#label_model').hide()
            $('#label_workbook').show()
            $('#label_workbook-2').hide()
            $('#label_format').hide()
            break;
    }
}
$('#method').change(change_method)

$(document).ready(change_method(null))


$('#submit').click(function (evt) {
    var method = $('#method').val();
    set_results('')

    var data = new FormData();
    if ($('#schema')[0].files.length == 0) {
        set_error('Select a schema');
        return;
    }
    data.append('schema', $('#schema')[0].files[0])
    data.append("sbtab", true);

    switch(method) {
        case 'convert':
            if ($('#workbook')[0].files.length == 0) {
                set_error('Select a workbook');
                return;
            }
            data.append('workbook', $('#workbook').files[0])
            data.append('format', $('#format').val())
            break;
        case 'diff':
            if ($('#model').val() == '') {
                set_error('Enter a model to difference');
                return;
            }
            if ($('#workbook')[0].files.length == 0) {
                set_error('Select a workbook');
                return;
            }
            if ($('#workbook-2')[0].files.length == 0) {
                set_error('Select a second workbook');
                return;
            }
            data.append('model', $('#model').val())
            data.append('workbook', $('#workbook').files[0])
            data.append('workbook-2', $('#workbook-2').files[0])
            break;
        case 'gen-template':
            data.append('format', $('#format').val())
            break;
        case 'init-schema':
            break;
        case 'normalize':
            if ($('#model').val() == '') {
                set_error('Enter a model to normalize');
                return;
            }
            if ($('#workbook')[0].files.length == 0) {
                set_error('Select a workbook');
                return;
            }
            data.append('model', $('#model').val())
            data.append('workbook', $('#workbook').files[0])
            data.append('format', $('#format').val())
            break;
        case 'validate':
            if ($('#workbook')[0].files.length == 0) {
                set_error('Select a workbook');
                return;
            }
            data.append('workbook', $('#workbook').files[0])
            break;
    }

    $.ajax({
      type: 'post',
      url: '/api/' + method + '/',
      data: data,
      enctype: 'multipart/form-data',
      processData: false,
      contentType: false,
      cache: false,
      // contentType: 'application/x-www-form-urlencoded; charset=UTF-8',
      dataType: 'json',
      success: display_results
    })
    .fail(display_error);

})

display_results = function(data, status, jqXHR) {    
    set_results('Implement output display');
}
function set_results(msg) {
    $("#errors").css('color', 'rgb(10, 10, 10)');
    $("#errors").html(msg);
}

display_error = function(jqXHR, textStatus, errorThrown) {    
    set_error('Implement error display');
}
function set_error(msg) {
    $("#errors").css('color', '#da3b60');
    $("#errors").html(msg);
}
