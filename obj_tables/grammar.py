""" Attributes for embedding domain-specific langauges for describing \*-to-many relationships
into Excel cell

:Author: Jonathan Karr <karr@mssm.edu>
:Date: 2019-09-23
:Copyright: 2019, Karr Lab
:License: MIT
"""

from obj_tables import core
from lark import v_args
import abc
import lark


class ManyToManyGrammarAttribute(core.ManyToManyAttribute, metaclass=abc.ABCMeta):
    """ Many-to-many attribute that can be deserialized wtih a grammar

    Attributes:
        GRAMMAR (:obj:`str`): grammar
        parser (:obj:`lark.Lark`): parser
        Transformer (:obj:`type`): subclass of :obj:`Transformer` which transforms
            parse trees into a list of instances of :obj:`core.Model`
    """

    def __init__(self, related_class, **kwargs):
        """
        Args:
            related_class (:obj:`type`): related class
        """
        super(ManyToManyGrammarAttribute, self).__init__(related_class, **kwargs)
        self.parser = lark.Lark(self.GRAMMAR)

    @abc.abstractmethod
    def serialize(self, values, encoded=None):
        """ Serialize related object

        Args:
            values (:obj:`list` of :obj:`Model`): Python representation
            encoded (:obj:`dict`, optional): dictionary of objects that have already been encoded

        Returns:
            :obj:`str`: simple Python representation
        """
        pass

    def deserialize(self, values, objects, decoded=None):
        """ Deserialize value

        Args:
            values (:obj:`object`): String representation of related objects
            objects (:obj:`dict`): dictionary of objects, grouped by model
            decoded (:obj:`dict`, optional): dictionary of objects that have already been decoded

        Returns:
            :obj:`tuple` of `object`, `core.InvalidAttribute` or `None`: tuple of cleaned value and cleaning error
        """
        tree = self.parser.parse(values)
        transformer = self.Transformer(objects)
        try:
            result = transformer.transform(tree)
            return (result, None)
        except lark.exceptions.LarkError as err:
            return (None, core.InvalidAttribute(self, [str(err)]))


class Transformer(lark.Transformer):
    """ Transforms parse trees into a list of instances of :obj:`core.Model`

    Attributes:
        objects (:obj:`dict`): dictionary that maps types of models to dictionaries which map serialized values
            of instances of models to instances
    """

    def __init__(self, objects):
        """
        Args:
            objects (:obj:`dict`): dictionary that maps types of models to dictionaries which map serialized values
                of instances of models to instances
        """
        self.objects = objects

    @lark.v_args(inline=True)
    def start(self, *args):
        """ Collapse return into a list of related model instances

        Args:
            *args (:obj:`list` of :obj:`core.Model`): related model instances

        Returns:
            :obj:`list` of :obj:`core.Model`: related model instances
        """
        return args

    def get_or_create(self, cls, serialized_val, **kwargs):
        """ Get a instance of a model with serialized value :obj:`serialized_val`, or
        create an instance if there is no such instance

        Args:
            cls (:obj:`type`): type of model instance to get or create
            serialized_val (:obj:`str`): serialized value of instance of model
            kwargs (:obj:`dict`): arguments to constructor of model for instance
        """
        if cls not in self.objects:
            self.objects[cls] = {}
        obj = self.objects[cls].get(serialized_val, None)
        if obj is None:
            obj = self.objects[cls][serialized_val] = cls(**kwargs)
        return obj
