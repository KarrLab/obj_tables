""" Example of how to decode JSON-encoded instances of :obj:`obj_tables.Model`

:Author: Jonathan Karr <karr@mssm.edu>
:Date: 2019-10-12
:Copyright: 2019, Karr Lab
:License: MIT
"""


def decode_data(encoded_data):
    """ Decode a data structure (arbitrary combination of list and dictionaries) that contains
    dictionaries that represent encoded objects and their relationships, preserving the high-level
    structure of the data structure. Objects and their relationships should be encoded into the
    data structure as follows:

    * Each object in the dataset should be represented by a dictionary whose keys/values represent
      the attributes of the object.

    * The dictionaries which represent the objects should contain an additional string-valued key
      `__type` that is equal to the name of the class of each object.

    * The dictionaries which represent the objects should contain an additional integer-value key
      `__id` that is a unique value for each object.

    * *-to-one relationships between objects should represented by the unique integer ids of the
      related objects.

    * *-to-many relationships between objects should represented by lists of the unique integer ids
      of the  related objects.

    * The dictionaries that represent the objects in datasets can be composed into arbitrary
      combinations of lists and dictionaries. This method preserves this nesting of dataset objects
      into lists and dictionaries.

    Args:
        encoded_data (:obj:`dict` or :obj:`list`): data structure with encoded objects and relationships

    Returns:
        :obj:`dict` or :obj:`list`: decoded data structure
    """
    decoded_objects = {}
    data_to_decode = []

    decoded_data = _decode_instance(encoded_data, decoded_objects, data_to_decode)

    while data_to_decode:
        obj_json, obj = data_to_decode.pop()
        if isinstance(obj, dict) and '__type' in obj:
            for attr_name, attr_json in obj_json.items():
                if attr_name in ['__type', '__id']:
                    continue
                obj[attr_name] = _decode_instance(attr_json, decoded_objects, data_to_decode)

        elif isinstance(obj, list):
            for sub_json in obj_json:
                obj.append(_decode_instance(sub_json, decoded_objects, data_to_decode))

        elif isinstance(obj, dict):
            for key, val in obj_json.items():
                obj[key] = _decode_instance(val, decoded_objects, data_to_decode)

    # return decoded data
    return decoded_data


def _decode_instance(encoded_data, decoded_objects, data_to_decode):
    """ Decode a data structure

    Args:
        encoded_data (:obj:`dict`, :obj:`list`, or scalar): data structure with
            encoded objects
        decoded_objects (:obj:`dict`): dictionary that maps the unique ids of
            encoded objects to dictionaries that represent the decoded objects
        data_to_decode (:obj:`list`): list of tuples of data structures that still
            need to decoded. The first element represents the data structure that
            needs to be decoded. The second element represents the object that will
            represent the decoded data structure.

    Returns:
        :obj:`dict`, :obj:`list`, or scalar: decoded data structure
    """
    if isinstance(encoded_data, dict) and '__type' in encoded_data:
        obj_type = encoded_data.get('__type')
        obj = decoded_objects.get(encoded_data['__id'], None)
        if obj is None:
            obj = {'__type': obj_type}
            decoded_objects[encoded_data['__id']] = obj
        data_to_decode.append((encoded_data, obj))
    elif isinstance(encoded_data, list):
        obj = []
        data_to_decode.append((encoded_data, obj))
    elif isinstance(encoded_data, dict):
        obj = {}
        data_to_decode.append((encoded_data, obj))
    else:
        obj = encoded_data

    return obj
