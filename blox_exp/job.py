import pandas as pd

class Job:
    def __init__(
        self,
        job_id,
        job_arrival_time,
        job_iteration_time,
        job_total_iteration,
        job_gpu_demand,
        job_model,
        batch_size
    ):
        # job details
        self.job_id = job_id
        self.job_arrival_time = job_arrival_time
        self.job_iteration_time = job_iteration_time
        self.job_total_iteration = job_total_iteration
        self.job_duration = job_iteration_time * job_total_iteration
        self.job_gpu_demand = job_gpu_demand
        self.job_model = job_model
        self.batch_size = batch_size

        self.job_gpu_demand_orig = job_gpu_demand
        self.job_iteration_time_orig = job_iteration_time

        # job state
        self.gpus = list()
        self.num_allocated_gpus = 0
        self.gpus_last_round = list()
        self.job_executed_iteration = 0
        self.job_last_execution_time = -1
        self.attained_service_time = 0
        
        # command to run jobs on nersc cluster
        self.launch_command = ""
        self.launch_params = []
        self.launch_params_multi = []
        self.init_launch()

    def __eq__(self, other):
        return self.job_id == other.job_id

    def __str__(self):
        return "job:%s:%s:%s (%s s,%s)" % (
            self.job_id, self.job_model, self.job_gpu_demand, self.job_arrival_time, self.job_total_iteration
        )
    
    def init_launch(self):
        default_placement = ''
        split_strategy = ''
        for i in range(self.job_gpu_demand):
            default_placement += str(i) + ","
            split_strategy += str(6) + ","
        default_placement = default_placement[:-1]
        split_strategy = split_strategy[:-1]
        if self.job_model == 'Bert-Base':
            self.launch_command = \
                "bash /scratch1/08503/rnjain/blox-pal/blox_exp/scripts/run_bert_base.sh"
            self.launch_params = [
                str(7000 + self.job_id),
                str(1),
                str(2),
                str(16),
                "True",
                split_strategy,
            ]
        elif self.job_model == 'Bert-Large':
            self.launch_command = \
                "bash /scratch1/08503/rnjain/blox-pal/blox_exp/scripts/run_bert_large.sh"
            self.launch_params = [
                str(7000 + self.job_id),
                str(1),
                str(4),
                str(16),
                "True",
                split_strategy,
            ]
        elif self.job_model == 'GPT2':
            self.launch_command = \
                "bash /scratch1/08503/rnjain/blox-pal/blox_exp/scripts/run_gpt.sh"
            self.launch_params = [
                str(7000 + self.job_id),
                str(1),
                str(2),
                str(8),
                "True",
                split_strategy,
            ]
        elif self.job_model == 'GPT2-Medium':
            self.launch_command = \
                "bash /scratch1/08503/rnjain/blox-pal/blox_exp/scripts/run_gpt_medium.sh"
            self.launch_params = [
                str(7000 + self.job_id),
                str(1),
                str(4),
                str(8),
                "True",
                split_strategy,
            ]
        elif self.job_model == 'GPT2-XL':
            self.launch_command = \
                "bash /scratch1/08503/rnjain/blox-pal/blox_exp/scripts/run_gpt_xl.sh"
            self.launch_params = [
                str(7000 + self.job_id),
                str(1),
                str(8),
                str(8),
                "True",
                split_strategy,
            ]
        elif self.job_model == "resnet50" or self.job_model == "vgg19":
            self.launch_command = \
                "bash /scratch1/08503/rnjain/blox-pal/blox_exp/scripts/run_imagenet.sh"
            self.launch_params = [
                str(7000 + self.job_id),
                self.job_model
            ]
        elif self.job_model == "DCGAN":
            self.launch_command = \
                "bash /scratch1/08503/rnjain/blox-pal/blox_exp/scripts/run_dcgan.sh"
            self.launch_params = [
                str(7000 + self.job_id),
            ]
        elif self.job_model == "PointNet":
            self.launch_command = \
                "bash /scratch1/08503/rnjain/blox-pal/blox_exp/scripts/run_pointnet.sh"
            self.launch_params = [
                str(7000 + self.job_id),
            ]
        else:
            raise ValueError("the model is not considered now!!!")

