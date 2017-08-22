# nl2sql
# Learning a Neural Semantic Parser with User Feedback

## Setup

#### Install torch libraries
```
luarocks install hdf5
```

#### Install MySQL libraries
```
sudo apt-get install libmysqlclient-dev
sudo apt-get install python-mysqldb
```

#### Install required python packages
```
pip install python-gflags MySQL-python futures pattern commentjson numpy h5py
```

#### Download word2vec embeddings and replace word2vec_sample.txt. Its is a tab separated list of the words followed by 300 dim embeddings
```
download from https://drive.google.com/file/d/0B7XkCwpI5KDYNlNUTTlSS21pQmM/edit?usp=sharing
convert the bin file to tsv: see https://gist.github.com/dav009/10a742de43246210f3ba
Note: This script outputs a comma separated list. Change that to tabs.
```

#### Unzip ppdb file
```
cd data/ppdb
gunzip ppdb-l-combined.gz
```

#### Setup databases for computing results
#### Databases are provided as a mysql dump file
```
mysql -u root -ptmppassword geo < data/geo/geo_mysql_dump.db
mysql -u root -ptmppassword atis < data/atis/atis_mysql_dump.db
```

### Export DB environment variables
```
export DBHOST="my.database.host"
export DBUSER="me"
export DBPASSWD="secret"
```

## GeoQuery

#### Train geo
```
cd src
./train_geo.sh
```

#### Predictions for each epoch on the development set are now in run_geo/preds/
#### Results on the dev set are summarized in run_geo.summary 
#### Test geo. Pick a trained model based on the run_geo.summary file.

```
$ ./train_geo.sh test run_geo_1001/s2s-model_epoch50.00_1.42.t7
loading run_geo_1001/s2s-model_epoch50.00_1.42.t7...
280.0
Correct=231 , Total=280.0 , Percent=82.5
```

## ATIS

#### Train ATIS
```
cd src
./train_atis.sh
```

#### Predictions for each epoch on the development set are now in run_atis/preds/
#### Results on the dev set are summarized in run_atis.summary 
#### Test atis. Pick a trained model based on the run_atis.summary file.

```
$ ./train_atis.sh test run_atis/s2s-model_epoch60.00_1.13.t7
loading run_atis/s2s-model_epoch60.00_1.13.t7...
448.0
Correct=355 , Total=448.0 , Percent=79.2410714286
```

## SCHOLAR

#### Download the dataset from:
https://drive.google.com/file/d/0Bw5kFkY8RRXYRXdYYlhfdXRlTVk/view?usp=sharing

#### Load it
```
mysql -u root -ptmppassword scholar < data/scholar/s2_mysql_dump.db
```

#### Train SCHOLAR
```
cd src
./train_scholar.sh
```

#### Predictions for each epoch on the development set are now in run_scholar/preds/
#### Results on the dev set are summarized in run_scholar.summary 
#### Test scholar. Pick a trained model based on the run_scholar.summary file.

```
$ ./train_scholar.sh test run_scholar/s2s-model_epoch50.00_1.60.t7
loading run_scholar/s2s-model_epoch50.00_1.60.t7...
218.0
Correct=145 , Total=218.0 , Percent=66.5137614679
```

# Run Simulated Interactive Experiments
```
python geo_interactive_batch.py --ppscale 3 --init_grammar_file ../data/grammar_empty.sql --data_dir ../data/geo/tmp_no_tem --models_dir ../data/geo/tmp_no_tem/models --db_host my.db.host --db_user me --db_pass my.secret.password

python atis_interactive_batch.py --ppscale 3 --init_grammar_file ../data/grammar_empty_atis.sql --data_dir ../data/atis/tmp_no_tem --models_dir ../data/atis/tmp_no_tem/models --host my.db.host --user me --passwd my.secret.password
```

# Useful SQL commands
```
Make MySQL ignore spaces after function names
SET sql_mode='IGNORE_SPACE';

Check number of threads connection to the database server
SHOW STATUS WHERE `variable_name` = 'Threads_connected';
```
