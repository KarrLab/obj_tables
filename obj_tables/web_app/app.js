$(document).foundation();

function changeMethod(evt){
    var method = $('#method').val();
    switch(method) {
        case 'convert':
            $('#label_model').hide()
            $('#label_workbook').show()
            $('#label_workbook-2').hide()
            $('#label_format').show()
            $('#label_viz_format').hide()
            break;

        case 'diff':
            $('#label_model').show()
            $('#label_workbook').show()
            $('#label_workbook-2').show()
            $('#label_format').hide()
            $('#label_viz_format').hide()
            break;

        case 'gen-template':
            $('#label_model').hide()
            $('#label_workbook').hide()
            $('#label_workbook-2').hide()
            $('#label_format').show()
            $('#label_viz_format').hide()
            break;

        case 'init-schema':
            $('#label_model').hide()
            $('#label_workbook').hide()
            $('#label_workbook-2').hide()
            $('#label_format').hide()
            $('#label_viz_format').hide()
            break;

        case 'normalize':
            $('#label_model').show()
            $('#label_workbook').show()
            $('#label_workbook-2').hide()
            $('#label_format').show()
            $('#label_viz_format').hide()
            break;

        case 'validate':
            $('#label_model').hide()
            $('#label_workbook').show()
            $('#label_workbook-2').hide()
            $('#label_format').hide()
            $('#label_viz_format').hide()
            break;

        case 'viz-schema':
            $('#label_model').hide()
            $('#label_workbook').hide()
            $('#label_workbook-2').hide()
            $('#label_format').hide()
            $('#label_viz_format').show()
            break;
    }
}
$('#method').change(changeMethod)

$(document).ready(changeMethod(null))


$('#submit').click(function (evt) {
    setResults('');

    var schema_files = $('#schema')[0].files;
    var model = $('#model').val();
    var method = $('#method').val();
    var workbook_files = $('#workbook')[0].files;
    var workbook_2_files = $('#workbook-2')[0].files;
    var format = $('#format').val();
    var viz_format = $('#viz_format').val();

    var data = new FormData();
    if (schema_files == 0) {
        setError('Select a schema');
        return;
    }
    var schema = schema_files[0];
    data.append('schema', schema);

    var successFunc = null;
    var errorMsgStart = null;
    var downloadResult = null;
    switch(method) {
        case 'convert':
            if (workbook_files.length == 0) {
                setError('Select a dataset');
                return;
            }
            data.append('workbook', workbook_files[0]);
            data.append('format', format);
            successFunc = function(request) {
                setResults('The dataset was converted to ' + format + ' format.');
            }
            errorMsgStart = 'The dataset could not be converted.';
            downloadResult = true;
            break;

        case 'diff':
            if (model == '') {
                setError('Enter a model to difference');
                return;
            }
            if (workbook_files.length == 0) {
                setError('Select a dataset');
                return;
            }
            if (workbook_2_files.length == 0) {
                setError('Select a second dataset');
                return;
            }
            data.append('model', model);
            data.append('workbook', workbook_files[0]);
            data.append('workbook-2', workbook_2_files[0]);
            downloadResult = false;
            successFunc = function(request) {
                var reader = new FileReader();
                reader.addEventListener('loadend', (e) => {
                    const json = JSON.parse(e.srcElement.result);
                    if (json.length == 0) {
                        setResults('The datasets are equivalent.');
                    } else {
                        setResults('The datasets are different:\n\n' + json.join('\n\n'));
                    }
                });
                reader.readAsText(request.response);
            };
            errorMsgStart = 'The datasets could not be compared.';
            break;

        case 'gen-template':
            data.append('format', format);
            downloadResult = true;
            successFunc = function(request) {
                setResults('A ' + format + ' template was generated.');
            };
            errorMsgStart = 'A template could not be generated.';
            break;

        case 'init-schema':
            downloadResult = true;
            successFunc = function(request) {
                setResults('A Python implementation of the schema was generated.');
            };
            errorMsgStart = 'Unable to generate a Python implementation of the schema.'
            break;

        case 'normalize':
            if (model == '') {
                setError('Enter a model to normalize');
                return;
            }
            if (workbook_files.length == 0) {
                setError('Select a dataset');
                return;
            }
            data.append('model', model);
            data.append('workbook', workbook_files[0]);
            data.append('format', format);
            successFunc = function(request) {
                setResults('The dataset was normalized and exported to ' + format + ' format.');
            };
            errorMsgStart = 'The dataset could not be normalized.';
            downloadResult = true;
            break;

        case 'validate':
            if (workbook_files.length == 0) {
                setError('Select a dataset');
                return;
            }
            data.append('workbook', workbook_files[0]);
            successFunc = function(request) {
                var reader = new FileReader();
                reader.addEventListener('loadend', (e) => {
                    const json = JSON.parse(e.srcElement.result);
                    if (json == '') {
                        setResults('The dataset is valid.');
                    } else {
                        setResults(json);
                    }
                });
                reader.readAsText(request.response);
            };
            errorMsgStart = 'The dataset could not be validated.';
            downloadResult = false;
            break;

        case 'viz-schema':
            data.append('format', viz_format);
            downloadResult = true;
            successFunc = function(request) {
                setResults('A UML diagram was generated.');
            };
            errorMsgStart = 'Unable to generate a UML diagram for the schema.'
            break;
    }

    var url = '/api/' + method + '/';

    var request = new XMLHttpRequest();
    request.open('POST', url, async=true);
    request.responseType = 'blob';

    request.onload = function(evt) {
        var request = evt.target;
        switch(request.status) {
            case 200:
                if (downloadResult) {
                    downloadFile(request);
                }
                successFunc(request);
                break

            case 400:
                var reader = new FileReader();
                reader.addEventListener('loadend', (e) => {
                    const json = JSON.parse(e.srcElement.result);
                    var msg = json['message'];
                    setError(errorMsgStart + ' ' + msg);
                });
                reader.readAsText(request.response);
                break;

            default:
                setError(errorMsgStart + ' Other error.');
                break;
        }
    }

    request.onerror = function(evt) {return;}

    request.send(data);
})

function downloadFile(request) {
    downloadUrl = window.URL.createObjectURL(request.response);
    filename = request.getResponseHeader('content-disposition').split('=')[1];

    var element = document.createElement('a');
    element.setAttribute('href', downloadUrl);
    element.setAttribute('download', filename);

    element.style.display = 'none';
    document.body.appendChild(element);

    element.click();

    document.body.removeChild(element);
}

function setResults(msg) {
    $("#errors").css('color', 'rgb(10, 10, 10)');
    $("#errors").html(msg);
}

function setError(msg) {
    $("#errors").css('color', '#da3b60');
    $("#errors").html(msg);
}
