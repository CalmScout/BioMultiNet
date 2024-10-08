# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/04_cmmd.ipynb.

# %% auto 0
__all__ = ['time_it', 'communities_detection', 'continual_multiplex_analysis', 'cmmd']

# %% ../nbs/04_cmmd.ipynb 4
import os
import sys
import subprocess
import numpy as np
from concurrent.futures import ThreadPoolExecutor
from scipy.spatial.distance import pdist, squareform
import seaborn as sns
import pickle
from pathlib import Path
import pathlib
import time
import shutil

# %% ../nbs/04_cmmd.ipynb 6
def time_it(func):
    def wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        end_time = time.perf_counter()
        execution_time = end_time - start_time
        minutes = int(execution_time // 60)
        seconds = execution_time % 60
        print(f"Function '{func.__name__}' executed in {minutes} minutes, {seconds:.2f} seconds")
        return result
    return wrapper

# %% ../nbs/04_cmmd.ipynb 8
# @time_it
def communities_detection(input_layers:list[str]=None,
                          gamma_min:float=None,
                          gamma_max:float=None,
                          gamma_step:float=None,
                          path_to_communities:str=None,
                          method:str="molti"):
    # Prepare inputs to generate the console order for MolTi's run.
    layers = " ".join(input_layers)
    
    resolution_gamma_step = np.arange(gamma_min, gamma_max + gamma_step, gamma_step)
    desfile_vector = [f"{path_to_communities}{res}.csv" for res in resolution_gamma_step]
    
    # community analysis
    if method == "molti":
        for i, current_resolution in enumerate(resolution_gamma_step):
            current_destfile = desfile_vector[i]
            system_order = f"molti-console -o {current_destfile} -p {current_resolution} {layers} > /dev/null"
            subprocess.run(system_order, shell=True)

# %% ../nbs/04_cmmd.ipynb 9
# @time_it
def continual_multiplex_analysis(nodelist:list[str]=None,
                                 path_to_communities:str=None,
                                 distmethod:str="hamming",
                                 n_jobs:int=1):
        # reading MolTi output files
        output_files = [f for f in os.listdir(path_to_communities) if "_" not in f]
        
        alllists = []
        
        for output_file in output_files:
            with open(os.path.join(path_to_communities, output_file), 'r') as file:
                red = file.readlines()
            
            cluster_ids = [i for i, line in enumerate(red) if "Cluster" in line]
            lista = []
            
            for j, st in enumerate(cluster_ids):
                if j == len(cluster_ids) - 1:
                    en = len(red)
                else:
                    en = cluster_ids[j + 1]
                current_cluster = red[st:en]
                current_cluster2 = current_cluster[:-2] if j != len(cluster_ids) - 1 else current_cluster[:-1]
                lista.append(current_cluster2[1:])
            
            alllists.append(lista)
        
        allgenes = list(set([gene for sublist in alllists for cluster in sublist for gene in cluster]))

        if nodelist:
            allgenes = list(set(allgenes).intersection(nodelist))
        
        # Calculating Gene/Community matrix
        res_matrix = np.empty((len(allgenes), len(alllists) + 1), dtype=object)
        res_matrix[:, :-1] = 0  # Initialize the integer part of the matrix with zeros
        gene_indices = {gene: idx for idx, gene in enumerate(allgenes)}
        
        for j, output_file_list in enumerate(alllists):
            for k, cluster in enumerate(output_file_list):
                for gene in cluster:
                    res_matrix[gene_indices[gene], j] = k + 1
        
        patterns = ["_".join(map(str, res_matrix[i, :-1])) for i in range(len(allgenes))]
        res_matrix[:, -1] = np.array(patterns, dtype=str)
        
        # Calculating Hamming distances for all gene pairs
        gene_community_matrix = res_matrix[:, :-1].astype(np.int64)
        genes_same_communities = {pattern: [] for pattern in np.unique(gene_community_matrix[:,-1])}
        
        for i, pattern in enumerate(gene_community_matrix[:,-1]):
            genes_same_communities[pattern].append(allgenes[i])
        
        with ThreadPoolExecutor(max_workers=n_jobs) as executor:
            distance_matrix = squareform(pdist(gene_community_matrix, metric=distmethod))
        
        final_output = {
            "gene_community_matrix": gene_community_matrix,
            "l_constant": genes_same_communities,
            "distance_matrix": distance_matrix
        }
        
        return final_output

# %% ../nbs/04_cmmd.ipynb 10
def cmmd(nodelist:list[str]|None=None,
         input_layers:list[str]=None,
         gamma_min:float=None,
         gamma_max:float=None,
         gamma_step:float=None, 
         distmethod:str="hamming",
         method:str="molti",
         n_jobs:int=1,
         path_to_communities:str=None):
    
    """
    Compute CmmD multilayer community trajectory analysis for a set of given networks.

    Parameters
    ----------
    nodelist : list, optional
        A list with the unique nodes that we want to appear in the final output. If not given,
        all nodes of the multiplex will be in the final output (nodelist= NULL)
    input_layers : list
        A vector of strings containing the paths where the different network layers are located
        in the system. Networks should be a two column file representing the edges of the graph.
    gamma_min : float
        The first gamma resolution parameter to use in the different MolTi's analysis
    gamma_max : float
        The last gamma resolution parameter to use in the different MolTi's analysis.
    gamma_step : float
        The gamma_step of the resolution parameter to use. 
    distmethod : str, optional
        A distance method metric to use to compute the trajectories. Defaults to "hamming" for hamming
        distance, but accepts any other metric supplied by scipy.spatial.distance.pdist.
    n_jobs : int, optional
        The number of n_jobs to use for the computation of the distance matrix. Defaults to 1.
    path_to_communities : str, optional
        The path to save Molti's output files. Defaults to "Output/".

    Returns
    -------
    A dictionary containing the following keys:
        gene_community_matrix: A matrix where the rows correspond to the different genes, and the columns to the different community structures. The values of the matrix are the cluster to which the gene belongs in the corresponding community structure.
        l_constant: A dictionary where the keys are the different community structures, and the values are the list of genes that belong to that community structure.
        distance_matrix: A matrix with the hamming distances between all pairs of genes.
    """
    # 0. check input correctness
    if input_layers is None or len(input_layers) < 1:
        raise ValueError("ERROR: Input_layers argument must be a list of at least 1 network file")
    
    if not isinstance(gamma_max, (int, float)):
        raise ValueError("ERROR: Resolution parameter must be a number")
    
    if not isinstance(gamma_min, (int, float)):
        raise ValueError("ERROR: Resolution parameter must be a number")
    
    if not isinstance(gamma_step, (int, float)):
        raise ValueError("ERROR: gamma_step value must be a number")
    
    if not isinstance(path_to_communities, str):
        raise ValueError("ERROR: path_to_communities expects a character string")
    
    assert distmethod in ['braycurtis', 'canberra', 'chebyshev', 'cityblock',
                          'correlation', 'cosine', 'dice', 'euclidean', 'hamming',
                          'jaccard', 'jensenshannon', 'kulczynski1', 'mahalanobis',
                          'matching', 'minkowski', 'rogerstanimoto', 'russellrao',
                          'seuclidean', 'sokalmichener', 'sokalsneath', 'sqeuclidean',
                          'yule']
    
    if not isinstance(n_jobs, int):
        raise ValueError("ERROR: n_jobs must be a number corresponding to the number of cores available to use")

    # 1st part: community detection
    Path(path_to_communities).mkdir(parents=True, exist_ok=True)
    # if folder is empty, generate communities to populate it
    if len(os.listdir(path_to_communities)) == 0:
        communities_detection(input_layers=input_layers, gamma_min=gamma_min, gamma_max=gamma_max,
                            gamma_step=gamma_step, method=method, path_to_communities=path_to_communities)
    
    # 2nd part: cmmd
    final_output = continual_multiplex_analysis(nodelist=nodelist,
                                                path_to_communities=path_to_communities,
                                                distmethod=distmethod,
                                                n_jobs=n_jobs)
    
    return final_output
