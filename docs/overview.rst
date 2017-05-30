Overview
========
`obj_model` allows developers to define standalone (i.e. separate from databases) schemas using a syntax similar to Django.
The `obj_model.io` module provides methods to serialize and deserialize schema objects to/from Excel, csv, and tsv file(s).

-------------------------------------
Defining schemas
-------------------------------------
Each schema is composed of one or models (subclasses of :obj:`Model`) each of which has one or more attributes
(instances of :obj:`Attribute` and its subclasses). The following shows an example of a schema for a lab member::

    class Member(Model):
        first_name = StringAttribute()
        last_name = StringAttribute()

Multiple attributes types are provided:

* :obj:`BooleanAttribute`
* :obj:`EnumAttribute`
* :obj:`IntegerAttribute`, :obj:`PositiveIntegerAttribute`
* :obj:`FloatAttribute`
* :obj:`StringAttribute`, :obj:`LongStringAttribute`, :obj:`RegexAttribute`, :obj:`UrlAttribute`, :obj:`SlugAttribute`
* :obj:`DateAttribute`, :obj:`TimeAttribute`, :obj:`DateTimeAttribute`

Four related attribute types (:obj:`OneToOneAttribute`, :obj:`OneToManyAttribute`, :obj:`ManyToOneAttribute`, and
:obj:`ManyToManyAttribute`) are provided to enable relationships among objects. Each constructor includes an
optional argument `related_name` which when provided automatically constructs a reverse attribute between the
instances::

    class Lab(Model):
        name = StringAttribute()
        url = UrlAttribute()

    class Member(Model):
        first_name = StringAttribute()
        last_name = StringAttribute()
        lab = ManyToOneAttribute(Lab, related_name='members')

Do not choose attribute names that would clash with with built-in attributes or methods of
classes, such as `validate`, `serialize`, and `deserialize`.


-------------------------------------
Instantiating objects
-------------------------------------
The module automatically adds optional keyword arguments to the constructor for each type. Thus objects can be
constructed as illustrated below::

    lab = Lab(name='Karr Lab')
    member = Member(first_name='Jonathan', last_name='Karr', lab=lab)

-------------------------------------
Getting and setting object attributes
-------------------------------------
Objects attributes can be get and set as shown below::

    name = lab.name
    lab.url = 'http://www.karrlab.org'

Related attributes can also be edited as shown below::

    new_member = Member(first_name='new', last_name='guy')
    lab.members = [new_member]

*-to-many and many-to-* attribute and related attribute values are instances of :obj:`RelatedManager` which is a subclass
of :obj:`set`. Thus, their values can also be edited with set methods such as `add`, `clear`, `remove`, and `update`.
:obj:`RelatedManager` provides three additional methods:

* `create`: `object.related_objects.create(**kwargs)` is syntatic sugar for `object.attribute.add(RelatedObject(**kwargs))`
* `get`: this returns a related object with attribute values equal to the supplies keyward argments
* `filter`: this returns the subset of the related objects with attribute values equal to the supplied keyword argments

-------------------------------------
Meta information
-------------------------------------
To allow developers to customize the behavior of each :obj:`Model` subclass, :obj:`Model` provides an internal `Meta` class
(:obj:`Model.Meta`). This provides several attributes:

* `attribute_order`: :obj:`tuple` of attribute names; controls order in which attributes should be printed when serialized
* `frozen_columns`: :obj:`int`: controls how many columns should be frozen when the model is serialized to Excel
* `ordering`: :obj:`tuple` of attribute names; controls the order in which objects should be printed when serialized
* `tabular_orientation`: :obj:`TabularOrientation`: controls orientation (row, column, inline) of model when serialized
* `unique_together`: :obj:`tuple` of attribute names; controls what tuples of attribute values must be unique
* `verbose_name`: verbose name of the model; used for (de)serialization
* `verbose_name_plural`: plural verbose name of the model; used for (de)serialization

-------------------------------------
Validation
-------------------------------------
To facilitate data validation, the module allows developers to specify how objects should be validated at several levels:

* Attribute: :obj:`Attribute` defines a method `validate` which can be used to validate individual attribute values. Attributes of
  (e.g. `min`, `max`, `min_length`, `max_length`, etc. ) these classes can be used to customize this validation
* Object: :obj:`Model` defines a method `validate` which can be used to validate entire object instances
* Model: :obj:`Model` defines a class method `validate_unique` which can be used to validate sets of object instances of the same type.
  This is customized by setting (a) the `unique` attribute of each model type's attrbutes or (b) the `unique_together` attribute
  of the model's `Meta` class.
* Dataset: :obj:`Validator` can be subclasses provide additional custom validation of entire datasets

Validation does not occur automatically, rather users must call validate() when it is needed.

-------------------------------------
Equality, differencing
-------------------------------------
To facilitate comparison between objects, the :obj:`Model` provides two methods

* `is_equal`: returns :obj:`True` if two :obj:`Model` instances are semantically equal (all attribute values are recursively equal)
* `difference`: returns a textual description of the difference(s) between two objects

-------------------------------------
Serialization/deserialization
-------------------------------------
The `io` module provides methods to serialize and deserialize schema objects to/from Excel, csv, and tsv files(s). :obj:`Model.Meta`
provides several attributes to enable developers to control how each model is serialized. Please see the "Meta information" section
above for more information.

-------------------------------------
Utilities
-------------------------------------
The `utils` module provides several additional utilities for manipulating :obj:`Model` instances.
