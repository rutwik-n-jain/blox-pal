#!/bin/bash

#SBATCH --job-name=debug_cluster    # create a short name for your job
#SBATCH --output=test_terminate.txt
#SBATCH -A m4431_g               # account
#SBATCH --qos=debug              # debug_preempt
#SBATCH --constraint=gpu
#SBATCH --nodes=2
#SBATCH --ntasks-per-node=4
#SBATCH --gres=gpu:4
#SBATCH --time=00:25:00          # total run time limit (HH:MM:SS)
#SBATCH -x nid[008192-008193,008196-008197,008200-008201,008204-008205,008208-008209,008212-008213,008216-008217,008220-008221,008224-008225,008228-008229,008232-008233,008236-008237,008240-008241,008244-008245,008248-008249,008252-008253,008256-008257,008260-008261,008264-008265,008268-008269,008272-008273,008276-008277,008280-008281,008284-008285,008288-008289,008292-008293,008296-008297,008300-008301,008304-008305,008308-008309,008312-008313,008316-008317,008320-008321,008324-008325,008328-008329,008332-008333,008336-008337,008340-008341,008344-008345,008348-008349,008352-008353,008356-008357,008360-008361,008364-008365,008368-008369,008372-008373,008376-008377,008380-008381,008384-008385,008388-008389,008392-008393,008396-008397,008400-008401,008404-008405,008408-008409,008412-008413,008416-008417,008420-008421,008424-008425,008428-008429,008432-008433,008436-008437,008440-008441,008444-008445,008448-008449,008452-008453,008456-008457,008460-008461,008464-008465,008468-008469,008472-008473,008476-008477,008480-008481,008484-008485,008488-008489,008492-008493,008496-008497,008500-008501,008504-008505,008508-008509,008512-008513,008516-008517,008520-008521,008524-008525,008528-008529,008532-008533,008536-008537,008540-008541,008544-008545,008548-008549,008552-008553,008556-008557,008560-008561,008564-008565,008568-008569,008572-008573,008576-008577,008580-008581,008584-008585,008588-008589,008592-008593,008596-008597,008600-008601,008604-008605,008608-008609,008612-008613,008616-008617,008620-008621,008624-008625,008628-008629,008632-008633,008636-008637,008640-008641,008644-008645,008648-008649,008652-008653,008656-008657,008660-008661,008664-008665,008668-008669,008672-008673,008676-008677,008680-008681,008684-008685,008688-008689,008692-008693,008696-008697,008700-008701]


echo "NODELIST="${SLURM_NODELIST}
master_addr_f=$(scontrol show hostnames "$SLURM_JOB_NODELIST" | head -n 1)
# master_addr_s=$(scontrol show hostnames "$SLURM_JOB_NODELIST" | head -n 2 | tail -n 1)
master_addr_s=$(scontrol show hostnames "$SLURM_JOB_NODELIST" | tail -n 1)
echo "MASTER_ADDR_F="$master_addr_f
echo "MASTER_ADDR_S="$master_addr_s
export MASTER_ADDR=$master_addr_f
export JOB_ID=${SLURM_JOB_ID}
export NUM_NODES=$SLURM_JOB_NUM_NODES

srun python -u debug_submit.py
# srun --nodes=1 -w $master_addr_f python -u nersc_submit.py &
# srun --nodes=1 -w $master_addr_s python -u nersc_submit.py &

wait


