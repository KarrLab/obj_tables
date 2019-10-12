""" Example of how to decode JSON-encoded instances of :obj:`obj_tables.Model`

:Author: Jonathan Karr <karr@mssm.edu>
:Date: 2019-10-12
:Copyright: 2019, Karr Lab
:License: MIT
"""

import json


def from_json(filename):
    with open(filename, 'r') as file:
        json_data = json.load(file)

    decoded = {}
    to_decode = []

    return_val = add_to_decoding_queue(json_data, decoded, to_decode)

    while to_decode:
        obj_json, obj = to_decode.pop()
        if isinstance(obj, dict) and '__type' in obj:
            for attr_name, attr_json in obj_json.items():
                if attr_name in ['__type', '__id']:
                    continue
                obj[attr_name] = add_to_decoding_queue(attr_json, decoded, to_decode)

        elif isinstance(obj, list):
            for sub_json in obj_json:
                obj.append(add_to_decoding_queue(sub_json, decoded, to_decode))

        elif isinstance(obj, dict):
            for key, val in obj_json.items():
                obj[key] = add_to_decoding_queue(val, decoded, to_decode)

    # return data
    return return_val


def add_to_decoding_queue(json, decoded, to_decode):
    if isinstance(json, dict) and '__type' in json:
        obj_type = json.get('__type')
        obj = decoded.get(json['__id'], None)
        if obj is None:
            obj = {'__type': obj_type}
            decoded[json['__id']] = obj
        to_decode.append((json, obj))
    elif isinstance(json, list):
        obj = []
        to_decode.append((json, obj))
    elif isinstance(json, dict):
        obj = {}
        to_decode.append((json, obj))
    else:
        obj = json

    return obj
