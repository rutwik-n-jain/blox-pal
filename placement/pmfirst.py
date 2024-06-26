import pandas as pd
import numpy as np
import json
import copy
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from typing import Tuple, List
import seaborn
import statistics
import scipy
from matplotlib import pyplot as plt
import csv
import itertools

class PMFirstPlacement(object):
    def __init__(self, args):
        # per class dataframes containing GPU_ID, Node_ID and sf for all GPUs
        self.dict_of_dfs = {}
        pass

    @staticmethod
    def copy_arguments(function):
        def function_wrapper(
            self, job_state, cluster_state, new_job_schedule, **kwargs
        ):
            return function(
                self,
                copy.deepcopy(job_state.active_jobs),
                copy.deepcopy(new_job_schedule),
                copy.deepcopy(cluster_state.server_map),
                copy.deepcopy(cluster_state.gpu_df),
                **copy.deepcopy(kwargs),
            )

        return function_wrapper

    @copy_arguments.__func__
    def place(
        self,
        active_jobs: dict,
        new_job_schedule: dict,
        node_info: dict,
        gpu_df: pd.DataFrame,
        **kwargs,
    ) -> dict:
        """
        parses the sorted_jobs dictionary and calls relevant placement policy

        # CAUTION: This function makes in place changes to active jobs and
        # gpu_df

        """
        if not bool(self.dict_of_dfs):
            if not gpu_df.empty:   #get alloc order based on slowdown factors and locality penalty
                self.dict_of_dfs = get_slowdown_factors(gpu_df)
        job_order = new_job_schedule["job_order"]
        scheduler = new_job_schedule.get("scheduler")
        jobs_to_terminate = list()
        job_to_launch = dict()
        launched_job_ids = list()
        # go over jobs in job order
        if scheduler == "Gavel":
            for idx, job_priority_sorted in enumerate(job_order):
                job_id, gpu_preference = list(job_priority_sorted.keys())[0]
                job = active_jobs[job_id]
                found = False
                if job["is_running"] == True:
                    if job["running_accel"] == gpu_preference:
                        # nothing to do here
                        continue
                    else:
                        # need to terminate this job trying to launch on
                        # different accelerator
                        jobs_to_terminate.append(job_id)
                        job["is_running"] = False
                        delete_job_by_id(gpu_df, job_id)

                if job_id in launched_job_ids:
                    # already launched the same ID in this round
                    continue
                if job["is_running"] == False:
                    # need to find placement only if job is not running
                    place_consolidated = (
                        job.get("placement_preference") == "consolidated"
                    )

                    free_gpus = find_free_GPUs_by_type(gpu_df, gpu_preference)
                    if place_consolidated:
                        placement, found = self._consolidated_placement(job, free_gpus)
                    else:
                        placement, found = self._scattered_placement(job, free_gpus)
                    if not found:
                        # no free GPUs
                        # find the GPU with same GPU preference in the reverse
                        # order of priority
                        for rev_idx in range(1, len(active_jobs) - idx):
                            potential_terminate_job_pair = job_order[-rev_idx]
                            if potential_terminate_job_pair[1] != gpu_preference:
                                # Job doesn't have the same preference
                                continue
                            else:
                                # the job has the same preference

                                # need to check if it is running
                                # and if it is running on the same as current
                                # preference
                                potential_terminate_job_info = active_jobs[
                                    potential_terminate_job_pair[0]
                                ]
                                if (
                                    potential_terminate_job_info["is_running"] == True
                                ) and (
                                    potential_terminate_job_info["running_accel"]
                                    == gpu_preference
                                ):
                                    # only terminate in case the training is
                                    # also happening on the same GPU as the
                                    # preference
                                    jobs_to_terminate.append(
                                        potential_terminate_job_pair[0]
                                    )
                                    potential_terminate_job_info["is_running"] = False
                                    # freeing up GPUs
                                    delete_job_by_id(
                                        gpu_df, potential_terminate_job_pair[0]
                                    )
                                    free_gpus = find_free_GPUs_by_type(
                                        gpu_df, gpu_preference
                                    )

                                    if place_consolidated:
                                        placement, found = self._consolidated_placement(
                                            job, free_gpus
                                        )
                                    else:
                                        placement, found = self._scattered_placement(
                                            job, free_gpus
                                        )

                                    if found:
                                        # we found the placement
                                        break

                                    # terminate this job
                                else:
                                    # job matching not found
                                    continue
                if found:
                    launched_job_ids.append(job_id)
                    job_to_launch[job_id] = placement
                    active_jobs[jid]["running_accel"] = gpu_preference
                    mark_gpu_in_use(gpu_df, placement, job_id)
                else:
                    break

            return (jobs_to_terminate, jobs_to_launch)

            # accel_sorted_by_pref - key: gpu_type, val: list of job ids sorted
            # by decreasing preference

        if scheduler is None:
            potential_preempt_dict = {}
            running_jobs = 0
            new_scheduled_jobs = 0
            jobs_to_schedule = 0     

            # Don't care about relocation penalties
            # Clear all allocations for all currently running jobs
            for item in job_order:
                jid, _ = item
                job = active_jobs[jid]

                if job["is_running"] == True:
                    potential_preempt_dict[jid] = get_gpus_by_job_id(gpu_df, jid)
                    delete_job_by_id(gpu_df, jid)
                    jobs_to_terminate.append(jid)

            # Cut off job queue at cluster size
            cluster_size = len(gpu_df)
            num_gpus_per_node = get_num_gpus_per_node(gpu_df)
            count_jobs = 0
            sum_gres_demand = 0
            cutoff_LoT = []

            for job_data in job_order:
                jid_temp, _ = job_data
                job_temp = active_jobs[jid_temp]
                sum_gres_demand += job_temp["num_GPUs"]
                if sum_gres_demand > cluster_size:
                    break
                job_class = job_temp["perfclass"]
                cutoff_LoT.append((jid_temp,job_class))

            # Sort them by perfclass
            custom_order = {'classA': 0, 'classB': 1, 'classC': 2, 'classD': 3}
            sorted_cutoff_LoT = sorted(cutoff_LoT, key=lambda x: custom_order.get(x[1], len(custom_order)))   
            sorted_job_ids = [job[0] for job in sorted_cutoff_LoT]

            mod_job_order = sorted_job_ids

            # Next, add elements from original_list that are not in sorted_job_ids
            for item in job_order:
                jid, _ = item
                if jid not in sorted_job_ids:
                    mod_job_order.append(jid)

            # with open(f"compare-job-queues.csv", "a") as file:
            #     file.write("\""+str(sorted_cutoff_LoT)+"\"," + str(mod_job_order) + " \n")            

            for idx, job_id in enumerate(mod_job_order):
                job = active_jobs[job_id]
                found = False

                # First get free_gpus dict
                temp_freelist = find_free_GPUs(gpu_df)
                        
                alloc, alloc_found = self._pmfirst_placement(job,temp_freelist, self.dict_of_dfs, num_gpus_per_node)

                if alloc_found == True:
                    job["is_running"] = True
                    placement, found = alloc, alloc_found

                if found:
                    new_scheduled_jobs += 1
                    job_to_launch[job_id] = placement
                    mark_gpu_in_use(gpu_df, placement, job_id)
                else:
                    # print(f"New Jobs scheduled {new_scheduled_jobs}")
                    # print(f"Jobs previously running {running_jobs}")
                    # print(f"Jobs terminated {len(jobs_to_terminate)}")
                    # print(f"Jobs in queue {len(job_order)-idx}")
                    break

            # if job id is a key in both potential_preempt_dict and job_to_launch
            # AND the value list is exactly the same in both dictionaries, 
            # remove jid from jobs_to_terminate
            for job_id in potential_preempt_dict.keys() & job_to_launch.keys():
                if sorted(potential_preempt_dict[job_id]) == sorted(job_to_launch[job_id]):
                    jobs_to_terminate.remove(job_id)

            return (jobs_to_terminate, job_to_launch)

    def _pmfirst_placement(
        self, job_param: dict, free_gpus: dict, dodfs: dict, num_gpus_per_node: int
    ) -> Tuple[list, bool]:
        """
        PAL placement policy
        Args:
        job_param: Job Param configuration
        free_gpus: Dict of free GPUs {node_id: [list of GPU IDs']}
        dodfs: dataframe of per-class dataframes
        num_gpus_per_node: 4 for Frontera, 3 for LoneStar6
        Returns:
        list of GPU IDs on which to place the job
        boolean indicating if we found placement
        """
        # move this to an init variable
        perfclasses = ["classA","classB","classC","classD"]
        free_gpu_list = []
        for node_id, gpu_ids in free_gpus.items():
            free_gpu_list.extend(gpu_ids)

        # Incoming job parameters
        numGPUs_needed = job_param["num_GPUs"]
        job_class      = job_param["perfclass"]

        # Filter the dataframe to keep relevant info
        df_data = dodfs[job_class]
        # Filter sf to keep GPUs that are in free list
        df_data = df_data[df_data['GPU_ID'].isin(free_gpu_list)]

        best_gpus = []
        # PMFirst
        if df_data.shape[0] >= numGPUs_needed:  #enough free GPUs are available for allocation
            best_gpus = _return_pmfirst_gpus(df_data, numGPUs_needed)
        #else no allocation found
  
        if len(best_gpus) == numGPUs_needed: #just checking if the allocation is satisfied
            with open(f"pal-allocations.csv", "a") as file:
                file.write("\""+str(best_gpus)+"\"," + str(numGPUs_needed) + "\n")
            return(best_gpus, True)
        # didn't find the requested number of GPUs
        return ([], False)


def get_num_gpus_per_node(gpu_df: pd.DataFrame) -> int:
    """
    Returns number of GPUs on a node using gpu_df
    assumes all nodes have same NUM_GPUS_PER_NODE
    no error checking
    """
    return gpu_df["Node_ID"].value_counts().iloc[0]

# PMFirst algorithm
def _return_pmfirst_gpus(df_filt: pd.DataFrame, numGPUs_needed: int) -> list:
    """
    Return best GPUs sorted by PM First and break ties using best-match locality
    Args:
    df_filt : filtered DataFrame consisting of information about free GPUs 
    (needs to have columns 'sf', 'Node_ID' and 'GPU_ID' for available GPUs)
    numGPUs_needed: number of GPUs that needs to be returned
    Returns:
    list: [list of best GPUs to be allocated to jon ]
    """  
    df_filt['locality_score'] = df_filt.groupby(['sf','Node_ID'])['Node_ID'].transform('count')
    # Best-match locality score
    df_filt['locality_score'] = abs(df_filt['locality_score'] - numGPUs_needed)
    df_filt = df_filt.sort_values(by=['sf','locality_score'], ascending=[True, True])
    # pick first Nj GPUs
    best_gpus = df_filt['GPU_ID'].head(numGPUs_needed).tolist()
    return best_gpus
# Pandas Utilities
def find_gpus_matching_JobID(job_id: int, gpu_df: pd.DataFrame) -> list:
    """
    Finds the GPU IDs which are running the given job id
    """
    return gpu_df.loc[gpu_df["JOB_IDS"] == job_id]["GPU_ID"].tolist()

def get_gpus_by_job_id(gpu_df: pd.DataFrame, job_id: int):
    # Filter the DataFrame based on JOB_ID and IN_USE
    filtered_df = gpu_df[(gpu_df['JOB_IDS'] == job_id) & (gpu_df['IN_USE'] == True)]
    gpu_ids = filtered_df['GPU_ID'].tolist()
    return gpu_ids


# Find free GPUs
def find_free_GPUs(gpu_df: pd.DataFrame) -> dict:
    """
    Find the nodeID's which have free GPUs
    Args:
    gpu_df : DataFrame consisting of information about GPUs
    Returns:
    dict: {Node_ID: [list of free GPUs]}
    """
    return (
        gpu_df.loc[gpu_df["IN_USE"] == False]
        .groupby("Node_ID")["GPU_ID"]
        .apply(list)
        .to_dict()
    )

# Find GPU allocation by job
def find_alloc_by_job(gpu_df: pd.DataFrame, job_id: int) -> dict:
    """
    Find the nodeID's which have GPUs being used by job
    Args:
    gpu_df : DataFrame consisting of information about GPUs
    Returns:
    dict: {Node_ID: [list of free GPUs]}
    """
    return (
        gpu_df.loc[gpu_df["JOB_IDS"] == job_id]
        .groupby("Node_ID")["GPU_ID"]
        .apply(list)
        .to_dict()
    )


def find_free_GPUs_by_type(gpu_df: pd.DataFrame, gpu_type: str) -> dict:
    """
    Find free nodeID's which have free GPUs of specific type

    Args:
    gpu_df : DataFrame consiting the information about GPUs
    Returns:
    dict : {Node_ID : [list of free GPUs]}
    """
    return (
        gpu_df.loc[(gpu_df["IN_USE"] == False) & (gpu_df["GPU_type"] == gpu_type)]
        .groupby("Node_ID")["GPU_ID"]
        .apply(list)
        .to_dict()
    )


# Mark a GPU in use


def mark_gpu_in_use(gpu_df: pd.DataFrame, gpu_id: List[int], job_id: int) -> None:
    """
    Find the GPU ID and mark it in use. After deciding to schedule something on
    it.
    Args:
    gpu_df : DataFrame consisting of information about GPUs
    gpu_id : GPU to mark busy
    job_id: Job being scheduled on GPU with id=gpu_id

    Returns:
    None
    In place modifies the gpu_df
    """
    gpu_df.loc[gpu_df["GPU_ID"].isin(gpu_id), ["JOB_IDS", "IN_USE"]] = job_id, True
    return None


# Delete Job from data frame


def delete_job_by_id(gpu_df: pd.DataFrame, job_id: int) -> None:
    """
    Finds the job ID provided. Marks those jobs free and marks the GPU free to
    Args:
    gpu_df : DataFrame consisting of information about GPUs
    job_id : Job to delete

    Returns:
    None
    In place modifies the gpu_df
    """
    gpu_df.loc[gpu_df["JOB_IDS"] == job_id, ["JOB_IDS", "IN_USE"]] = None, False
    return None

def identify_outliers(data: pd.DataFrame, threshold=3):
    # Identify outliers based on mean + threshold * standard deviation
    mean_val = data.mean()
    std_val = data.std()
    outliers = (data > mean_val + threshold * std_val)
    return outliers

def _remove_outliers(gpu_df: pd.DataFrame, threshold=3):
    # Calculate mean and standard deviation of the "sf" column
    mean_sf = gpu_df['sf'].mean()
    std_sf = gpu_df['sf'].std()
    
    # Filter the DataFrame to exclude outliers
    filtered_df = gpu_df[gpu_df['sf'] <= mean_sf + threshold * std_sf]
    
    return filtered_df


def get_optimal_k(data: pd.DataFrame, outliers: pd.Series) -> int:
    data_no_outliers = data[~outliers]
    silhouette_scores = []
    for k in range(2, 11):
        kmeans = KMeans(n_clusters=k, init='k-means++', algorithm='full', random_state=1)
        labels = kmeans.fit_predict(data_no_outliers)
        silhouette_avg = silhouette_score(data_no_outliers, labels)
        silhouette_scores.append(silhouette_avg)
        
        # Choose the K with the highest silhouette score
        optimal_k = silhouette_scores.index(max(silhouette_scores)) + 2  # Add 2 because range starts from 2
        #num_outliers = outliers.sum()  #Sum up boolean True values to get num_outliers
        #optimal_k += num_outliers
        return optimal_k

def get_slowdown_factors(gpu_df: pd.DataFrame) ->  dict:
    slowdown_factors = {}
    dict_of_dfs = {}
    df_copy = gpu_df.copy() # making a modifiable copy

    # Create a dictionary to store GPU indices grouped by Node_ID
    node_id_dict = {}
    for idx, row in gpu_df.iterrows():
        node_id = row['Node_ID']
        if node_id not in node_id_dict:
            node_id_dict[node_id] = []
        node_id_dict[node_id].append(idx)

    # Read profiles.json to get perfclass keys
    with open('profiles.json') as json_file:
        perfclasses = json.load(json_file)

    # For each class
    for key in perfclasses:
        temparr = df_copy[[f"PerfVar_{key}"]].values
        outliers = identify_outliers(gpu_df[f"PerfVar_{key}"])

        ##############################################################################################
        # K means clustering to get sfs
        #get number of clusters without outliers
        K1 = get_optimal_k(temparr, outliers)

        K2 = outliers.sum() # Number of outliers 
        num_clusters = K1 + K2

        # if outliers.any():
        #     #identify ideal number of clusters for outlier data alone
        #     gpudf_subset = gpu_df[outliers]
        #     filtarr = gpudf_subset[[f"PerfVar_{key}"]].values
        #     K2 = get_optimal_k(filtarr, pd.Series())

        #     num_clusters = K1 + K2
        # else:
        #     num_clusters = K1

        # with open("optimal-k-vals.csv", "a") as file:
        #     file.write(f"{key},{K1}+{K2}={num_clusters}\n")        

        kmeans = KMeans(init='k-means++',algorithm='full',random_state=1,n_clusters=num_clusters)
        df_copy.loc[:,'label'] = kmeans.fit_predict(temparr)

        centers = list(kmeans.cluster_centers_)

        df_copy['sf'] = kmeans.transform(df_copy[[f"PerfVar_{key}"]]).argmin(axis=1)
        df_copy['sf'] = df_copy['sf'].map(lambda x: centers[x])
        df_copy['sf'] = df_copy['sf'].apply(lambda x: x[0])
        median_centroid = np.median(centers,axis=0)
        df_copy['sf'] = df_copy['sf'] / median_centroid

        slowdown_factors[key] = df_copy.set_index('GPU_ID')['sf'].to_dict()

        cluster_nums = df_copy.set_index('GPU_ID')['label'].to_dict()

        # Add df_key to dict_of_dfs
        # Some debug prints too
        df_key = df_copy[['GPU_ID', 'Node_ID', 'sf']]
        dict_of_dfs[key] = df_key
        df_key.to_csv(f"gpudf_{key}.csv")

    return dict_of_dfs



