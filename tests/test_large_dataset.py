""" Large test case

:Author: Jonathan Karr <karr@mssm.edu>
:Date: 2017-03-23
:Copyright: 2017, Karr Lab
:License: MIT
"""

from obj_model import core, utils
from obj_model.io import Reader, Writer
from wc_utils.util.list import is_sorted
import os
import shutil
import sys
import tempfile
import unittest


class Model(core.Model):
    id = core.SlugAttribute()
    class Meta(core.Model.Meta):
        _donot_use_manager = True


class Gene(core.Model):
    model = core.ManyToOneAttribute(Model, related_name='genes')
    id = core.SlugAttribute()
    class Meta(core.Model.Meta):
        _donot_use_manager = True


class Rna(core.Model):
    model = core.ManyToOneAttribute(Model, related_name='rna')
    gene = core.ManyToOneAttribute(Gene, related_name='rna')
    id = core.SlugAttribute()
    class Meta(core.Model.Meta):
        _donot_use_manager = True


class Protein(core.Model):
    model = core.ManyToOneAttribute(Model, related_name='proteins')
    rna = core.ManyToOneAttribute(Rna, related_name='proteins')
    id = core.SlugAttribute()
    class Meta(core.Model.Meta):
        _donot_use_manager = True


class Metabolite(core.Model):
    model = core.ManyToOneAttribute(Model, related_name='metabolites')
    id = core.SlugAttribute()
    class Meta(core.Model.Meta):
        _donot_use_manager = True


class Reaction(core.Model):
    model = core.ManyToOneAttribute(Model, related_name='reactions')
    id = core.SlugAttribute()
    metabolites = core.ManyToManyAttribute(Metabolite, related_name='reactions')
    enzyme = core.ManyToOneAttribute(Protein, related_name='reactions')
    class Meta(core.Model.Meta):
        _donot_use_manager = True


def generate_model(n_gene, n_rna, n_prot, n_met):
    model = Model(id='model')
    for i_gene in range(1, n_gene + 1):
        gene = model.genes.create(id='Gene_{}'.format(i_gene))
        for i_rna in range(1, n_rna + 1):
            rna = model.rna.create(id='Rna_{}_{}'.format(i_gene, i_rna), gene=gene)
            for i_prot in range(1, n_prot + 1):
                prot = model.proteins.create(id='Protein_{}_{}_{}'.format(i_gene, i_rna, i_prot), rna=rna)

    for i_met in range(1, n_met + 1):
        met = model.metabolites.create(id='Metabolite_{}'.format(i_met))

    prots = Protein.sort(model.proteins)
    mets = Metabolite.sort(model.metabolites)
    for i_rxn in range(1, n_gene * n_rna * n_prot + 1):
        rxn = model.reactions.create(id='Reaction_{}'.format(i_rxn), enzyme=prots[i_rxn - 1], metabolites=[
            mets[(i_rxn - 1 + 0) % n_met],
            mets[(i_rxn - 1 + 1) % n_met],
            mets[(i_rxn - 1 + 2) % n_met],
            mets[(i_rxn - 1 + 3) % n_met],
        ])

    return model


def get_all_objects(model):
    return [model] \
        + model.genes \
        + model.rna \
        + model.proteins \
        + model.metabolites \
        + model.reactions


class TestDataset(unittest.TestCase):

    def setUp(self):
        self.regular_recursion_limit = sys.getrecursionlimit()
        sys.setrecursionlimit(200)

        self.dirname = tempfile.mkdtemp()

    def tearDown(self):
        sys.setrecursionlimit(self.regular_recursion_limit)

        shutil.rmtree(self.dirname)


class TestMediumDataset(TestDataset):
    """ Test that the methods work on reasonably sized datasets """

    n_gene = 50
    n_rna = 2
    n_prot = 2
    n_met = 50

    def test_get_related(self):
        model = generate_model(self.n_gene, self.n_rna, self.n_prot, self.n_met)
        objects = model.get_related()
        self.assertEqual(set(objects), set(get_all_objects(model)))

    def test_normalize(self):
        model = generate_model(self.n_gene, self.n_rna, self.n_prot, self.n_met)
        utils.randomize_object_graph(model)
        model.normalize()

        self.assertTrue(is_sorted([gene.id for gene in model.genes]))
        self.assertTrue(is_sorted([rna.id for rna in model.rna]))
        self.assertTrue(is_sorted([prot.id for prot in model.proteins]))
        self.assertTrue(is_sorted([met.id for met in model.metabolites]))
        self.assertTrue(is_sorted([rxn.id for rxn in model.reactions]))

        for met in model.metabolites:
            self.assertTrue(is_sorted([rxn.id for rxn in met.reactions]))

        for prot in model.proteins:
            self.assertTrue(is_sorted([rxn.id for rxn in prot.reactions]))

        for rxn in model.reactions:
            self.assertTrue(is_sorted([met.id for met in rxn.metabolites]))

    def test_is_equal(self):
        model = generate_model(self.n_gene, self.n_rna, self.n_prot, self.n_met)
        model2 = generate_model(self.n_gene, self.n_rna, self.n_prot, self.n_met)
        utils.randomize_object_graph(model2)
        self.assertTrue(model2.is_equal(model))

    def test_difference(self):
        model = generate_model(self.n_gene, self.n_rna, self.n_prot, self.n_met)
        model2 = generate_model(self.n_gene, self.n_rna, self.n_prot, self.n_met)
        utils.randomize_object_graph(model2)
        self.assertEqual(model2.difference(model), '')

    def test_validate(self):
        model = generate_model(self.n_gene, self.n_rna, self.n_prot, self.n_met)
        errors = core.Validator().run(model)
        self.assertEqual(errors, None)

    def test_read_write(self):
        model = generate_model(self.n_gene, self.n_rna, self.n_prot, self.n_met)

        filename = os.path.join(self.dirname, 'test.xlsx')
        Writer().run(filename, [model], [Model, Gene, Rna, Protein, Metabolite, Reaction, ])
        objects2 = Reader().run(filename, [Model, Gene, Rna, Protein, Metabolite, Reaction, ])

        model2 = objects2[Model].pop()
        self.assertTrue(model2.is_equal(model))


@unittest.skip("Skipped because test is long")
class TestLargeDataset(TestDataset):
    n_gene = 1000
    n_rna = 3
    n_prot = 3
    n_met = 800

    def test_validate(self):
        model = generate_model(self.n_gene, self.n_rna, self.n_prot, self.n_met)
        all_objects = get_all_objects(model)

        errors = core.Validator().run(all_objects)
        self.assertEqual(errors, None)

    def test_read_write(self):
        model = generate_model(self.n_gene, self.n_rna, self.n_prot, self.n_met)
        all_objects = get_all_objects(model)

        filename = os.path.join(self.dirname, 'test.xlsx')
        Writer().run(filename, all_objects, [Model, Gene, Rna, Protein, Metabolite, Reaction, ], get_related=False)
        objects2 = Reader().run(filename, [Model, Gene, Rna, Protein, Metabolite, Reaction, ])


@unittest.skip("Skipped because test is long")
class TestHugeDataset(TestLargeDataset):
    n_gene = 30000
    n_rna = 3
    n_prot = 3
    n_met = 8000
