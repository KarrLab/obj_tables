""" Attributes for embedding domain-specific langauges for describing \*-to-many relationships
into Excel cell

:Author: Jonathan Karr <karr@mssm.edu>
:Date: 2019-09-23
:Copyright: 2019, Karr Lab
:License: MIT
"""

from obj_tables import core
from obj_tables import utils
from wc_utils.util.list import det_dedupe
import abc
import lark
import stringcase

__all__ = [
    'ToManyGrammarAttribute',
    'ToManyGrammarTransformer',
]


class ToManyGrammarAttribute(core.RelatedAttribute, metaclass=abc.ABCMeta):
    """ \*-to-many attribute that can be deserialized with a grammar

    Attributes:
        grammar (:obj:`str`): grammar
        parser (:obj:`lark.Lark`): parser

    Class attributes:

    * grammar (:obj:`str`): grammar
    * grammar_path (:obj:`str`): path to grammar
    * Transformer (:obj:`type`): subclass of :obj:`Transformer` which transforms
      parse trees into a list of instances of :obj:`core.Model`
    """
    grammar = None
    grammar_path = None
    Transformer = None

    def __init__(self, related_class, grammar=None, **kwargs):
        """
        Args:
            related_class (:obj:`type`): related class
            grammar (:obj:`str`, optional): grammar
        """
        super(ToManyGrammarAttribute, self).__init__(related_class, **kwargs)

        if grammar is None:
            if self.grammar:
                grammar = self.grammar
            elif self.grammar_path:
                with open(self.grammar_path, 'r') as file:
                    grammar = file.read()
            else:
                raise ValueError('A grammar or path to a grammar must be defined')

        self.grammar = grammar
        self.parser = lark.Lark(grammar)

    @abc.abstractmethod
    def serialize(self, values, encoded=None):
        """ Serialize related object

        Args:
            values (:obj:`list` of :obj:`core.Model`): Python representation
            encoded (:obj:`dict`, optional): dictionary of objects that have already been encoded

        Returns:
            :obj:`str`: simple Python representation
        """
        pass  # pragma: no cover

    def deserialize(self, values, objects, decoded=None):
        """ Deserialize value

        Args:
            values (:obj:`object`): String representation of related objects
            objects (:obj:`dict`): dictionary of objects, grouped by model
            decoded (:obj:`dict`, optional): dictionary of objects that have already been decoded

        Returns:
            :obj:`tuple` of :obj:`object`, :obj:`core.InvalidAttribute` or :obj:`None`: tuple of cleaned value and cleaning error
        """
        if values in [None, '']:
            return ([], None)

        try:
            tree = self.parser.parse(values)
            self.Transformer = self.Transformer or self.gen_transformer(self.related_class)
            transformer = self.Transformer(objects)
            result = transformer.transform(tree)
            return (result, None)
        except lark.exceptions.LarkError as err:
            return (None, core.InvalidAttribute(self, [str(err)]))

    @classmethod
    def gen_transformer(cls, model):
        """ Generate transformer for model

        Args:
            model (:obj:`type`): model

        Returns:
            :obj:`type`: transformer
        """
        related_models = utils.get_related_models(model, include_root_model=True)
        methods = {}
        for model in related_models:
            @lark.v_args(inline=True)
            def func(self, *args, model=model):
                kwargs = {}
                for arg in args:
                    cls_name, _, attr_name = arg.type.partition('__')
                    if cls_name.lower() == stringcase.snakecase(model.__name__):
                        kwargs[attr_name.lower()] = arg.value
                return self.get_or_create_model_obj(model, **kwargs)

            methods[stringcase.snakecase(model.__name__)] = func
        return type('Transformer', (ToManyGrammarTransformer, ), methods)


class ToManyGrammarTransformer(lark.Transformer):
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
        return det_dedupe(arg for arg in args if not isinstance(arg, lark.lexer.Token))

    def get_or_create_model_obj(self, model, _serialized_val=None, _clean=True,
                                **kwargs):
        """ Get a instance of a model with serialized value :obj:`_serialized_val`, or
        create an instance if there is no such instance

        Args:
            model (:obj:`type`): type of model instance to get or create
            _serialized_val (:obj:`str`, optional): serialized value of instance of model
            _clean (:obj:`bool`, optional): if :obj:`True`, clean values
            kwargs (:obj:`dict`, optional): arguments to constructor of model for instance
        """
        if model not in self.objects:
            self.objects[model] = {}

        new_obj = None
        if _serialized_val is None:
            if model.Meta.primary_attribute:
                _serialized_val = kwargs[model.Meta.primary_attribute.name]
            else:
                if not kwargs:
                    raise ValueError('Insufficient information to make new instance')
                new_obj = self._make_obj(model, _clean=_clean, **kwargs)
                _serialized_val = new_obj.serialize()

        obj = self.objects[model].get(_serialized_val, None)
        if obj is None:
            if new_obj is None:
                if not kwargs:
                    raise ValueError('Insufficient information to make new instance')
                obj = self._make_obj(model, _clean=_clean, **kwargs)
            else:
                obj = new_obj
            self.objects[model][_serialized_val] = obj

        return obj

    @staticmethod
    def _make_obj(model, _clean=True, **kwargs):
        """ Make an instance of a model

        Args:
            model (:obj:`type`): type of model to instantiate
            _clean (:obj:`bool`): if :obj:`True`, clean the instance of :obj:`model`
            kwargs (:obj:`dict`, optional): arguments to constructor of :obj:`model`
        """
        obj = model(**kwargs)
        if _clean:
            err = obj.clean()
        if err is not None:
            raise ValueError('Unable to clean {}: {}'.format(
                model.__name__, str(err)))
        return obj
