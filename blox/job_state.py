import sys
import time
import copy
import grpc
import json
import logging
import argparse
import pandas as pd
import time
from concurrent import futures

from typing import Tuple, List

from blox_manager import BloxManager


class JobState(object):
    """
    Tracks state of jobs and all the metadata associated with them
    """

    def __init__(self, args: argparse.ArgumentParser):
        """
        Keep Track of job state
        """
        # self.blr = blox_resource_manager
        # dict of active jobs
        self.active_jobs = dict()
        # count number of accepted jobs
        self.job_counter = 0
        self.job_completion_stats = dict()
        self.job_responsiveness_stats = dict()
        self.cluster_stats = dict()
        self.custom_metrics = dict()
        self.job_runtime_stats = dict()
        self.finished_job = dict()  # keys are ids of the jobs which have finished
        self.job_ids_to_track = list(range(args.start_id_track, args.stop_id_track + 1))
        self.time = 0

    # def get_new_jobs(self):
    # """
    # Fetch any new jobs which have arrived at the scheduler
    # """
    # new_jobs = self.blr.rmserver.get_new_jobs()
    # return new_jobs

    # def get_new_jobs_sim(self):
    # """
    # Get new jobs for simulation
    # """
    # new_jobs = self.blr.rmserver.get_jobs_sim(self.simulator_time)
    # return new_jobs

    # def add(self, new_jobs: List[dict]):
    # """
    # Add new jobs
    # """
    # if len(new_jobs) > 0:
    # self._add_new_jobs(new_jobs)

    def update_metrics(self, metric_data: dict) -> None:
        """
        Update the metrics fetched at end of each round duration
        """
        for jid in self.active_jobs:
            if self.active_jobs[jid]["is_running"] == True:
                if len(metric_data.get(jid)) > 0:
                    # replace only when we have got metrics
                    self.active_jobs[jid]["tracked_metrics"] = metric_data.get(jid)

        return None
    
    def _get_perfclass(self, job, class_id):
        if "perfclass" in job and (job.get("perfclass")) is not None:
            return job["perfclass"]
        else:
            if class_id == 0: #alexnet
                return "classA"
            elif class_id == 1: #res18
                return "classC"
            elif class_id == 2: #res50
                return "classA"
            elif class_id == 3: #mobilenet
                return "classD"
            elif class_id == 4: #shufflenet
                return "classD"
            elif class_id == 5: #gnmt
                return "classB"
            elif class_id == 6: #transformer
                return "classB"
            elif class_id == 7: #lstm
                return "classD"
            elif class_id == 8: #deepspeech
                return "classB"
            else:
                return "classB"

    def add_new_jobs(self, new_jobs: List[dict]) -> None:
        """
        Pop jobs from the new queue and assign to the dictionary

        new_jobs : list of new jobs submitted to resource manager
        """
        if len(new_jobs) > 0:
            while True:
                try:
                    jobs = new_jobs.pop(0)
                    # TODO: Make this more permanent
                    params_to_track = ["per_iter_time", "attained_service"]
                    default_values_param = [0, 0]
                    tracking_dict = dict()
                    for p, v in zip(params_to_track, default_values_param):
                        tracking_dict[p] = v
                    jobs["tracked_metrics"] = tracking_dict
                    jobs["time_since_scheduled"] = 0
                    jobs["job_priority"] = 999
                    jobs["previously_launched"] = False
                    self.active_jobs[self.job_counter] = jobs
                    self.active_jobs[self.job_counter]["is_running"] = False
                    self.job_counter += 1
                except IndexError:
                    # remove the job counter
                    break
