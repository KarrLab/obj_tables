# *ObjTables* examples and tutorials

## Example datasets and schemas in CSV, JSON, TSV, XLSX, and YAML formats
* Basic examples of simple datasets
  * [`address_book`](examples/address_book): Address book of several major technology companies, their CEOs, and their addresses.
  * [`biochemical_network`](examples/biochemical_network): Small network of metabolites and chemical reactions.
  * [`children_favorite_video_games`](examples/children_favorite_video_games): Table of children and their favorite video games.
  * [`financial_transactions`](examples/financial_transactions): Table of financial transactions including the category and amount of each transaction.
  * [`genomics`](examples/genomics): Dataset of several human genes and their splice variants obtaned from [Ensembl](https://useast.ensembl.org/).
* Larger examples involving published datasets. These examples are discussed in the supplementary materials to the [*ObjTables* manuscript](https://arxiv.org/abs/2005.05227).
  * [`kinetic_metabolic_model`](examples/kinetic_metabolic_model): Kinetically-constrained model of *Escherichia coli* metabolism developed by Khodayari & Maranas.
    DOI: [10.1038/ncomms13806](https://doi.org/10.1038/ncomms13806).
  * [`thermodynamic_metabolic_model`](examples/thermodynamic_metabolic_model): Thermodynamically-constrained model of *Escherichia coli* metabolism developed by Gerosa et al.
    DOI: [10.1016/j.cels.2015.09.008](https://doi.org/10.1016/j.cels.2015.09.008).
  * [`merged_metabolite_model`](examples/merged_metabolite_model): Merged model which combines the data from the Khodayari & Maranas and Gerosa et al. models.
* Larger examples involving the [SBtab schema](examples/sbtab/SBtab.csv) for systems biology data and models. See [https://sbtab.net](https://sbtab.net) for more information.
  * [`sbtab/hynne.*`](examples/sbtab): Hynne model of yeast glycolysis. DOI: [10.1016/s0301-4622(01)00229-0](https://doi.org/10.1016/s0301-4622%2801%2900229-0).
  * [`sbtab/jiang_model.*`](examples/sbtab): Jiang et al. model of pancreatic beta-cell insulin secretion.  DOI: [10.1007/s00335-007-9011-y](https://doi.org/10.1007/s00335-007-9011-y).
  * [`sbtab/jiang_data.*`](examples/sbtab): Data related to the Jiang et al. model.
  * [`sbtab/ecoli_noor_2016_model.*`](examples/sbtab): Noor et al. model of *Escherichia coli* metabolism.  DOI: [10.1371/journal.pcbi.1005167](https://dx.doi.org/10.1371%2Fjournal.pcbi.1005167).
  * [`sbtab/ecoli_noor_2016_data.*`](examples/sbtab): Data related to the Noor et al. model.
  * [`sbtab/sigurdsson_model.*`](examples/sbtab): Sigurdsson et al. model of mouse metabolism. DOI: [10.1186/1752-0509-4-140](https://doi.org/10.1186/1752-0509-4-140).
  * [`sbtab/teusink_model.*`](examples/sbtab): Teusink model of yeast glycolysis. DOI: [10.1046/j.1432-1327.2000.01527.x](https://doi.org/10.1046/j.1432-1327.2000.01527.x).
  * [`sbtab/teusink_data.*`](examples/sbtab): Data related to the Teusink model
  * [`sbtab/ecoli_wortel_2018_model.*`](examples/sbtab): Wortel et al. model of *Escherichia coli* metabolism. DOI: [10.1371/journal.pcbi.1006010](https://doi.org/10.1371/journal.pcbi.1006010).
  * [`sbtab/ecoli_wortel_2018_data.*`](examples/sbtab): Data related to the Wortel et al. model.
  * [`sbtab/kegg_reactions_cc_ph70_quantity.*`](examples/sbtab): Standard free energies of reactions calculated by [eQuilibrator](http://equilibrator.weizmann.ac.il/).
  * [`sbtab/yeast_transcription_network_chang_2008_relationship.*`](examples/sbtab): Yeast transcriptional regulatory network inferred by Chang et al. DOI: [10.1093/bioinformatics/btn131](https://doi.org/10.1093/bioinformatics/btn131).
* Examples of larger, more complex schemas for new formats for domain-specific data
  * [WC-KB](https://github.com/Karrlab/wc_kb): WC-KB is a framework for organizing the data needed for whole-cell modeling projects of prokaryotes and eukaryotes. 
    * [UML diagram for eukaryote schema](https://raw.githubusercontent.com/KarrLab/obj_tables/master/examples/wc_kb.eukaryote.svg)
    * [UML diagram for prokaryote schema](https://raw.githubusercontent.com/KarrLab/obj_tables/master/examples/wc_kb.prokaryote.svg)
  * [WC-Lang](https://github.com/KarrLab/wc_lang): Format for systematically describing composite, multi-algorithmic whole-cell models.    
    * [UML diagram for core classes](https://raw.githubusercontent.com/KarrLab/obj_tables/master/examples/wc_lang.core.svg)
    * [UML diagram for complete schema](https://raw.githubusercontent.com/KarrLab/obj_tables/master/examples/wc_lang.svg)

## Jupyter notebooks with tutorials of the *ObjTables* Python package
1. [Building and visualizing schemas](http://sandbox.karrlab.org/notebooks/obj_tables/1.%20Building%20and%20visualizing%20schemas.ipynb)
2. [Building, querying, editing, comparing, normalizing, and validating datasets](http://sandbox.karrlab.org/notebooks/obj_tables/2.%20Building%2C%20querying%2C%20editing%2C%20comparing%2C%20normalizing%2C%20and%20validating%20datasets.ipynb)
3. [Importing, exporting, converting, and pretty printing datasets](http://sandbox.karrlab.org/notebooks/obj_tables/3.%20Importing%2C%20exporting%2C%20converting%2C%20and%20pretty%20printing%20datasets.ipynb)
4. [Merging and cutting datasets](http://sandbox.karrlab.org/notebooks/obj_tables/4.%20Merging%20and%20cutting%20datasets.ipynb)
5. [Revisioning and migrating datasets](http://sandbox.karrlab.org/notebooks/obj_tables/5.%20Revisioning%20and%20migrating%20datasets.ipynb)

## Example code for decoding a JSON-formatted *ObjTables* dataset to a collection of linked computational objects, or object graph
See [`decode_json_data.py`](examples/decode_json_data.py).

## Example instructions for deploying the REST API
See [`deploy_rest_api.sh`](examples/deploy_rest_api.sh).
