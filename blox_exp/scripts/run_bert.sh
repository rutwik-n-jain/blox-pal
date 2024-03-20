#!/bin/bash

export CUDA_VISIBLE_DEVICES=$1

GPUS_PER_NODE=$2
# Change for multinode config
MASTER_ADDR=localhost
MASTER_PORT=$3
NNODES=1
NODE_RANK=0
WORLD_SIZE=$(($GPUS_PER_NODE*$NNODES))

CHECKPOINT_PATH=checkpoints/bert_pretrain
VOCAB_FILE=/scratch1/08503/rnjain/data-files/bert/bert-large-uncased-vocab.txt
DATA_PATH=/global/cfs/cdirs/m4207/song/my-bert_text_sentence

DISTRIBUTED_ARGS="
    --nproc_per_node $GPUS_PER_NODE \
    --nnodes $NNODES \
    --node_rank $NODE_RANK \
    --master_addr $MASTER_ADDR \
    --master_port $MASTER_PORT
"

BERT_ARGS="
    --tensor-model-parallel-size 1 \
    --pipeline-model-parallel-size $4 \
    --num-layers 24 \
    --hidden-size 1024 \
    --num-attention-heads 16 \
    --seq-length 512 \
    --max-position-embeddings 512 \
    --micro-batch-size 16 \
    --global-batch-size 256 \
    --lr 0.0001 \
    --train-iters 1000000 \
    --lr-decay-iters 990000 \
    --lr-decay-style linear \
    --min-lr 1.0e-5 \
    --weight-decay 1e-2 \
    --lr-warmup-fraction .01 \
    --clip-grad 1.0 \
    --fp16 \
    --no-async-tensor-model-parallel-allreduce \
    --is-manual-pipeline True \
    --manual-pipeline-list $5 \
    --job-id $6
"

DATA_ARGS="
    --data-path $DATA_PATH \
    --vocab-file $VOCAB_FILE \
    --data-impl mmap \
    --split 949,50,1
"

OUTPUT_ARGS="
    --log-interval 100 \
    --save-interval 10000 \
    --eval-interval 1000 \
    --eval-iters 10
"

torchrun $DISTRIBUTED_ARGS /scratch1/08503/rnjain/Megatron-Resource/pretrain_bert.py \
    $BERT_ARGS \
    $DATA_ARGS \
    $OUTPUT_ARGS \
    --distributed-backend nccl \
    --save $CHECKPOINT_PATH \
    --load $CHECKPOINT_PATH