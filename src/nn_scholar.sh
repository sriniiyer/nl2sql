#!/bin/bash
OUT_DIR=../data/scholar/tmp
mkdir -p ${OUT_DIR}
DATA_DIR=../data/scholar/
TRAIN_NL=scholar_train.nl
TRAIN_SQL=scholar_train.sql
DEV_NL=scholar_dev.nl
DEV_SQL=scholar_dev.sql
TEST_NL=scholar_test.nl
TEST_SQL=scholar_test.sql
SCHEMA=../data/scholar/scholar.schema
DB=scholar

cp ${DATA_DIR}/${TRAIN_NL} ${OUT_DIR}/
cp ${DATA_DIR}/${TRAIN_SQL} ${OUT_DIR}/
cp ${DATA_DIR}/${DEV_NL} ${OUT_DIR}/
cp ${DATA_DIR}/${DEV_SQL} ${OUT_DIR}/
cp ${DATA_DIR}/${TEST_NL} ${OUT_DIR}/
cp ${DATA_DIR}/${TEST_SQL} ${OUT_DIR}/

python scholar_templatize.py --nlfile ${OUT_DIR}/${TRAIN_NL} --sqlfile ${OUT_DIR}/${TRAIN_SQL}
python scholar_templatize.py --nlfile ${OUT_DIR}/${DEV_NL} --sqlfile ${OUT_DIR}/${DEV_SQL}
python scholar_templatize.py --nlfile ${OUT_DIR}/${TEST_NL} --sqlfile ${OUT_DIR}/${TEST_SQL}

cat ${OUT_DIR}/${TRAIN_NL}.tem ${OUT_DIR}/${DEV_NL}.tem > ${OUT_DIR}/train_dev.nl.tem
cat ${OUT_DIR}/${TRAIN_SQL}.tem ${OUT_DIR}/${DEV_SQL}.tem > ${OUT_DIR}/train_dev.sql.tem

python tfidf.py --nl ${OUT_DIR}/train_dev.nl.tem  --sql ${OUT_DIR}/train_dev.sql.tem --testnl ${OUT_DIR}/${TEST_NL}.tem > ${OUT_DIR}/nn.pred.txt

python anonymize.py --schema ${SCHEMA} --sqlfile ${OUT_DIR}/nn.pred.txt --mapfile ${OUT_DIR}/${TEST_NL}.tem.map --reverse --stop_file ../data/ppdb/stopwords.txt

python getMetrics.py \
	--reffile ${OUT_DIR}/${TEST_SQL} \
	--methodfile ${OUT_DIR}/nn.pred.txt.deanon \
	--debugfile ${OUT_DIR}/nn.pred.txt.deanon.debug.sql \
	--db ${DB}
