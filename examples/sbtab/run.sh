SCHEMA=schema.csv

# Initalize Python module which implements schema
obj-tables init-schema ${SCHEMA} schema.py

# Generate a template for the schema
obj-tables gen-template ${SCHEMA} template.xlsx

# Validate that documents adhere to the schema
obj-tables validate ${SCHEMA} template.xlsx
obj-tables validate ${SCHEMA} 'hynne/*.tsv'
obj-tables validate ${SCHEMA} hynne.tsv
obj-tables validate ${SCHEMA} 'lac_operon/*.tsv'
obj-tables validate ${SCHEMA} feed_forward_loop_relationship.tsv
obj-tables validate ${SCHEMA} kegg_reactions_cc_ph70_quantity.tsv
obj-tables validate ${SCHEMA} yeast_transcription_network_chang_2008_relationship.tsv
obj-tables validate ${SCHEMA} simple_examples/1.tsv
obj-tables validate ${SCHEMA} simple_examples/2.csv
obj-tables validate ${SCHEMA} simple_examples/3.csv
obj-tables validate ${SCHEMA} simple_examples/4.csv
obj-tables validate ${SCHEMA} simple_examples/5.csv
obj-tables validate ${SCHEMA} simple_examples/6.csv
obj-tables validate ${SCHEMA} simple_examples/7.csv
obj-tables validate ${SCHEMA} simple_examples/8.csv
obj-tables validate ${SCHEMA} simple_examples/9.csv
obj-tables validate ${SCHEMA} simple_examples/10.csv
obj-tables validate ${SCHEMA} teusink_data.tsv
obj-tables validate ${SCHEMA} teusink_model.tsv
obj-tables validate ${SCHEMA} jiang_data.tsv
obj-tables validate ${SCHEMA} jiang_model.tsv
obj-tables validate ${SCHEMA} ecoli_noor_2016_data.tsv
obj-tables validate ${SCHEMA} ecoli_noor_2016_model.tsv
obj-tables validate ${SCHEMA} ecoli_wortel_2018_data.tsv
obj-tables validate ${SCHEMA} ecoli_wortel_2018_model.tsv
obj-tables validate ${SCHEMA} sigurdsson_model.tsv
obj-tables validate ${SCHEMA} layout_model.tsv
