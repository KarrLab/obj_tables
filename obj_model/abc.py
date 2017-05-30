""" Support for abstract model classes

:Author: Jonathan Karr <karr@mssm.edu>
:Date: 2017-05-23
:Copyright: 2016, Karr Lab
:License: MIT
"""

from __future__ import absolute_import
import abc
import obj_model.core
import six


class ModelMetaAbc(obj_model.core.ModelMeta, abc.ABCMeta):
    """ Abstract model metaclass """
    pass


class ModelAbc(six.with_metaclass(ModelMetaAbc, obj_model.core.Model)):
    """ Abstract model base class """
    pass
