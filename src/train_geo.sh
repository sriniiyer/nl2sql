#!/bin/bash
OUT_DIR=../data/geo/tmp
mkdir -p ${OUT_DIR}
GPUID=1
DATA_DIR=../data/geo/
TRAIN_NL=geo_tr.nl
TRAIN_SQL=geo_tr.sql
DEV_NL=geo_dev.nl
DEV_SQL=geo_dev.sql
TEST_NL=geo_test.nl
TEST_SQL=geo_test.sql
GRAMMAR=../data/grammar.sql
SCHEMA=../data/geo/geo.schema
DB=geo

# TEST
if [ "$1" == "test" ]; then

	th beam.lua \
		-model $2 \
		-src_file ${OUT_DIR}/${TEST_NL}.tem \
		-output_file ${OUT_DIR}/test.pred.txt \
		-gpuid ${GPUID} \
		-src_dict ${OUT_DIR}/s2.src.dict \
		-targ_dict ${OUT_DIR}/s2.targ.dict \
		-beam 5 \
		-score_gold 0 \
		-word2vec_dict ${OUT_DIR}/word2vec.dict \

	python geo_templatize.py --mapfile ${OUT_DIR}/${TEST_NL}.tem.map --sqlfile ${OUT_DIR}/test.pred.txt --inst deanonymize

	python getMetrics.py \
		--reffile ${OUT_DIR}/${TEST_SQL} \
		--methodfile ${OUT_DIR}/test.pred.txt.deanon \
		--debugfile ${OUT_DIR}/test.pred.txt.deanon.debug.sql \
		--db ${DB} \
		--host ${DBHOST} \
		--user ${DBUSER} \
		--passwd ${DBPASSWD}
	exit 1
fi

cp ${DATA_DIR}/${TRAIN_NL} ${OUT_DIR}/
cp ${DATA_DIR}/${TRAIN_SQL} ${OUT_DIR}/
cp ${DATA_DIR}/${DEV_NL} ${OUT_DIR}/
cp ${DATA_DIR}/${DEV_SQL} ${OUT_DIR}/
cp ${DATA_DIR}/${TEST_NL} ${OUT_DIR}/
cp ${DATA_DIR}/${TEST_SQL} ${OUT_DIR}/

python geo_templatize.py --nlfile ${OUT_DIR}/${TRAIN_NL} --sqlfile ${OUT_DIR}/${TRAIN_SQL}
python geo_templatize.py --nlfile ${OUT_DIR}/${DEV_NL} --sqlfile ${OUT_DIR}/${DEV_SQL}
python geo_templatize.py --nlfile ${OUT_DIR}/${TEST_NL} --sqlfile ${OUT_DIR}/${TEST_SQL}

# add paraphrases
paste ${OUT_DIR}/${TRAIN_NL}.tem ${OUT_DIR}/${TRAIN_SQL}.tem  > ${OUT_DIR}/train.tem
python generate.py --grammar ${OUT_DIR}/train.tem --schema ${SCHEMA} --db ${DB} --ppscale 3 --paraphrase_file ../data/ppdb/ppdb-l-combined --prefix ${OUT_DIR}/ --stop_file ../data/ppdb/stopwords.txt --host ${DBHOST} --user ${DBUSER} --passwd ${DBPASSWD}

python generate.py --grammar ${GRAMMAR} --schema ${SCHEMA} --db ${DB} --ppscale 0 --prefix ${OUT_DIR}/pp0_ --stop_file ../data/ppdb/stopwords.txt --host ${DBHOST} --user ${DBUSER} --passwd ${DBPASSWD}
cat ${OUT_DIR}/pp0_train.nl >> ${OUT_DIR}/train.nl
cat ${OUT_DIR}/pp0_train.sql  >> ${OUT_DIR}/train.sql


#build word2vec
py_script="
import sys
words = []

def ingest(filename):
	for line in open(filename, 'r'):
		wors = line.strip().split()
		for w in wors:
			if w not in words:
				words.append(w)

ingest('${OUT_DIR}/train.nl')
ingest('${OUT_DIR}/${DEV_NL}.tem')
ingest('${OUT_DIR}/${TEST_NL}.tem')

f = open('${OUT_DIR}/word2vec.vecs', 'w')
g = open('${OUT_DIR}/word2vec.dict', 'w')
g.write('<blank> 1\n')
g.write('<unk> 2\n')
g.write('<s> 3\n')
g.write('</s> 4\n')
num = 5
for line in open('../data/word2vec/word2vec.txt', 'r'):
  cols = line.strip().split()
  if cols[0] in words:
    f.write(line)
    g.write(cols[0] + ' ' + str(num) + '\n')
    num += 1
f.close()
g.close()
"

python -c "$py_script"

python preprocess.py \
 	--srcfile ${OUT_DIR}/train.nl \
 	--targetfile ${OUT_DIR}/train.sql \
	--srcvalfile ${OUT_DIR}/${DEV_NL}.tem \
	--targetvalfile ${OUT_DIR}/${DEV_SQL}.tem \
	--word2vecfile ${OUT_DIR}/word2vec.dict \
	--outputfile ${OUT_DIR}/s2 \
	--batchsize 100 \
	--seqlength 150  \
	--vocab_unk_threshold 1 \

EPOCHS=70
word2vec_size=`wc -l < ${OUT_DIR}/word2vec.dict`
lr=0.001
wvec=800
dim=600
bsiz=100
lay=1
dropout=0.4
enc_dropout=0.5
PREFIX=run_geo
SUMMARY_FILE=${PREFIX}.summary
TRACE_FILE=${PREFIX}.trace
rm ${SUMMARY_FILE}
for rand in `seq 1 1 1`;
do
	seed=$((1000 + $rand))

	MODELS_DIR=${PREFIX}
	rm -rf ${MODELS_DIR}
	mkdir -p ${MODELS_DIR}
	mkdir -p ${MODELS_DIR}/preds

  th train.lua \
		-src_dict ${OUT_DIR}/s2.src.dict \
		-seed ${seed} \
		-targ_dict ${OUT_DIR}/s2.targ.dict \
		-data_file ${OUT_DIR}/s2-train.hdf5 \
		-val_data_file ${OUT_DIR}/s2-val.hdf5 \
		-savefile ${MODELS_DIR}/s2s-model \
		-max_batch_l 100 \
		-num_layers ${lay} \
		-gpuid ${GPUID} \
		-dropout ${dropout} \
		-enc_dropout ${enc_dropout} \
		-print_every 50 \
		-epochs ${EPOCHS} \
		-rnn_size ${dim} \
		-word2vec_size ${word2vec_size} \
		-word2vec_dim 300 \
		-word2vecfile ${OUT_DIR}/word2vec.vecs \
		-word_vec_size ${wvec} \
		-brnn 1 \
		-lr_decay 0.8 \
		-predict 0 \
		-optim adam \
		-learning_rate ${lr} | tee ${TRACE_FILE}

	for ((i=1; i<=${EPOCHS}; i++)); do
		fname=`ls ${MODELS_DIR}/s2s-model_epoch${i}.*.t7`
		f=${fname##*/}

		echo $fname >> ${SUMMARY_FILE}

		th beam.lua \
			-model ${fname} \
			-src_file ${OUT_DIR}/${DEV_NL}.tem \
			-output_file ${MODELS_DIR}/preds/${f}.pred.txt \
			-gpuid ${GPUID} \
			-src_dict ${OUT_DIR}/s2.src.dict \
			-targ_dict ${OUT_DIR}/s2.targ.dict \
			-beam 5 \
			-score_gold 0 \
			-word2vec_dict ${OUT_DIR}/word2vec.dict \

    python geo_templatize.py --mapfile ${OUT_DIR}/${DEV_NL}.tem.map --sqlfile ${MODELS_DIR}/preds/${f}.pred.txt --inst deanonymize

		python getMetrics.py \
			--reffile ${OUT_DIR}/${DEV_SQL} \
			--methodfile ${MODELS_DIR}/preds/${f}.pred.txt.deanon \
			--debugfile ${MODELS_DIR}/preds/${f}.pred.txt.deanon.debug.sql \
			--db ${DB} \
			--host ${DBHOST} \
			--user ${DBUSER} \
			--passwd ${DBPASSWD} >> ${SUMMARY_FILE}
	done

done


