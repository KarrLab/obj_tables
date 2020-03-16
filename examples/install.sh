# Installation instructions for web server on DreamHost

cd /home/objtables/objtables.org

# Install Python 3.6.9 using miniconda 4.6.14
wget https://repo.anaconda.com/miniconda/Miniconda3-4.6.14-Linux-x86_64.sh
chmod u+x Miniconda3-4.6.14-Linux-x86_64.sh
./Miniconda3-4.6.14-Linux-x86_64.sh
rm Miniconda3-4.6.14-Linux-x86_64.sh
echo "export PATH=~/miniconda3/bin:\$PATH" >> ~/.bashrc
echo "export PATH=~/miniconda3/bin:\$PATH" >> ~/.bash_profile
source ~/.bashrc
conda create -n py369 python=3.6.9
conda activate py369
conda install graphviz
conda install -c openbabel openbabel
echo "export PATH=~/miniconda3/envs/py369/bin:\$PATH" >> ~/.bashrc
echo "export PATH=~/miniconda3/envs/py369/bin:\$PATH" >> ~/.bash_profile

# Install our code
git clone https://github.com/KarrLab/wc_utils.git
pip install -e wc_utils/

git clone https://github.com/KarrLab/obj_tables.git
pip install -e obj_tables/[all]

# Save passenger config to /home/objtables/objtables.org/passenger_wsgi.py

# Setup static directory
ln -s ../obj_tables/obj_tables/web/app.css public/app.css
ln -s ../obj_tables/obj_tables/web/app.js public/app.js
ln -s ../obj_tables/obj_tables/web/index.html public/index.html

# make temporary directory for triggering the webserver to restart
mkdir tmp
touch tmp/restart.txt

# make directory for logs
mkdir logs
