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
echo "export PATH=~/miniconda3/envs/py369/bin:\$PATH" >> ~/.bashrc
echo "export PATH=~/miniconda3/envs/py369/bin:\$PATH" >> ~/.bash_profile

# Install OpenBabel
conda install -c openbabel openbabel

# Install Java
wget https://download.java.net/java/GA/jdk11/9/GPL/openjdk-11.0.2_linux-x64_bin.tar.gz
tar xvvf openjdk-11.0.2_linux-x64_bin.tar.gz
mkdir ~/opt
mv jdk-11.0.2 ~/opt
rm openjdk-11.0.2_linux-x64_bin.tar.gz
echo "export JAVA_HOME=~/opt/jdk-11.0.2" >> ~/.bashrc
echo "export JAVA_HOME=~/opt/jdk-11.0.2" >> ~/.bash_profile
echo "export PATH=\$JAVA_HOME/bin:\$PATH" >> ~/.bashrc
echo "export PATH=\$JAVA_HOME/bin:\$PATH" >> ~/.bash_profile
source ~/.bashrc

# Install ChemAxon marvin
# download platform independent installer (zip) from https://chemaxon.com/products/marvin/download
# copy via FTP to /home/objtables/objtables.org/marvin_windows_19.20.zip
unzip marvin_windows_19.20.zip
mv marvin ~/opt
rm marvin_windows_19.20.zip
mkdir ~/.chemaxon
# copy https://github.com/KarrLab/karr_lab_build_config/blob/master/third_party/chemaxon.license.cxl to ~/.chemaxon/license.cxl
echo "export PATH=~/opt/marvin/bin:\$PATH" >> ~/.bashrc
echo "export PATH=~/opt/marvin/bin:\$PATH" >> ~/.bash_profile
echo "export CLASSPATH=\$CLASSPATH:~/opt/marvin/lib/MarvinBeans.jar" >> ~/.bashrc
echo "export CLASSPATH=\$CLASSPATH:~/opt/marvin/lib/MarvinBeans.jar" >> ~/.bash_profile
source ~/.bashrc

# Install Jnius
pip install pyjnius

# Install our code
git clone https://github.com/KarrLab/wc_utils.git
pip install -e wc_utils/

git clone https://github.com/KarrLab/bpforms.git
# comment out openbabel in bpforms/requirements.txt because installed with conda
pip install -e bpforms/

git clone https://github.com/KarrLab/bcforms.git
# comment out openbabel in bcforms/requirements.txt because installed with conda
# comment out wc_utils options in bcforms/requirements.txt because openbabel installed with conda, jinus already installed
pip install -e bcforms/

git clone https://github.com/KarrLab/obj_tables.git
pip install -e obj_tables/[all]

# Save passenger config to /home/objtables/objtables.org/passenger_wsgi.py

# Setup static directory
ln -s ../obj_tables/obj_tables/web_app/app.css public/app.css
ln -s ../obj_tables/obj_tables/web_app/app.js public/app.js
ln -s ../obj_tables/obj_tables/web_app/index.html public/index.html

# make temporary directory for triggering the webserver to restart
mkdir tmp
touch tmp/restart.txt

# make directory for logs
mkdir logs
