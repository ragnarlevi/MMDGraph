

# This script experiments with MMD for two binomial graphs



from logging import warn, warning
import networkx as nx
import numpy as np
import grakel as gk # graph kernels module
import pickle # save data frame (results) in a .pkl file
import pandas as pd
# from tqdm import * # Estimation of loop time
#from tqdm import tqdm as tqdm
from datetime import datetime
import os, sys
import argparse
import warnings
import concurrent.futures

# add perant dir 
currentdir = os.path.dirname(os.path.realpath(__file__))
parentdir = os.path.dirname(currentdir)
parentdir = os.path.dirname(parentdir)
sys.path.append(parentdir)
# sys.path.append(os.path.abspath(".."))
print(os.getcwd())

# Load module which
import MMDforGraphs as mg


parser = argparse.ArgumentParser()
parser.add_argument('-B', '--NrBootstraps',metavar='', type=int, help='Give number of bootstraps')
parser.add_argument('-N', '--NrSampleIterations',metavar='', type=int, help='Give number of sample iterations')
parser.add_argument('-p', '--path', type=str,metavar='', help='Give path (including filename) to where the data should be saved')
parser.add_argument('-norm', '--normalize', type=int,metavar='', help='Should kernel be normalized')
parser.add_argument('-nitr', '--NumberIterations', type=int,metavar='', help='WL nr iterations')
parser.add_argument('-n1', '--NrSamples1', type=int,metavar='', help='Number of graphs in sample 1')
parser.add_argument('-n2', '--NrSamples2', type=int,metavar='', help='Number of graphs in sample 2')
parser.add_argument('-d', '--division', type=int,metavar='', help='How many processes')


group = parser.add_mutually_exclusive_group()
group.add_argument('-v', '--verbose', action='store_false', help = 'print verbose')


args = parser.parse_args()



if __name__ == "__main__":
    # Erdos Renyi graphs
    # np.seterr(divide='ignore', invalid='ignore')



    # Number of Bootstraps
    B = args.NrBootstraps
    # Sample and bootstrap N times so that we can estimate the power.
    N = args.NrSampleIterations
    # Where should the dataframe be saved
    path = args.path
    # Should the kernels be normalized?
    normalize = args.normalize

    n1 = args.NrSamples1
    n2 = args.NrSamples2
    d = args.division
    n_itr = args.NumberIterations   



    # functions used for kernel testing
    MMD_functions = [mg.MMD_b, mg.MMD_u]
    
    # initialize bootstrap class, we only want this to be initalized once so that numba njit
    # only gets compiled once (at first call)
    kernel_hypothesis = mg.BoostrapMethods(MMD_functions)

    # Initialize Graph generator class
    probs_1 = np.array([[0.15, 0.05, 0.02], [0.05, 0.25, 0.07], [0.02, 0.07, 0.2]])
    label_pmf_1 = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]])
    sizes_1 = [30, 20, 25]
    bg1 = mg.SBMGraphs(n = n1, sizes = sizes_1, P = probs_1, l = 'BlockLabelling', params= {'label_pmf':label_pmf_1}, fullyConnected=True)

    probs_2 = np.array([[0.15, 0.05, 0.02], [0.05, 0.25, 0.07], [0.02, 0.07, 0.2]])
    label_pmf_2 = np.array([[0.8, 0.1, 0.1], [0.1, 0.8, 0.1], [0.1, 0.1, 0.8]])
    sizes_2 = [30, 20, 25]
    bg2 = mg.SBMGraphs(n = n2, sizes = sizes_2, P = probs_2, l = 'BlockLabelling', params= {'label_pmf':label_pmf_2}, fullyConnected=True)

    # Probability of type 1 error
    alphas = np.linspace(0.01, 0.99, 99)


    
    now = datetime.now()
    time = pd.Timestamp(now)
    print(time)
    
    # Kernel specification
    # kernel = [{"name": "WL", "n_iter": 4}]
    kernel = [{"name": "weisfeiler_lehman", "n_iter": n_itr}, {"name": "vertex_histogram"}]
    # kernel = [{"name": "weisfeiler_lehman", "n_iter": 4}, {"name": "SP"}]
    # kernel = [{"name": "SP", "with_labels": True}]
    # kernel = [{"name": "svm_theta"}]
    # kernel = [{"name": "pyramid_match", "with_labels":False}]
    # kernel = [{"name": "ML", "n_samples":20}]
    
    # Store outcome in a data
    df = pd.DataFrame()


    # caclulate process partition
    part = int(np.floor(N/d))
    if N % d != 0:
        N = part*d
        warnings.warn(f'Number of samples not an integer multiply of number of processes. N set as the floor {N}')

    print(part)
    print(N)
    print(d)
    
    p_values = dict()
    mmd_samples = dict()
    for i in range(len(MMD_functions)):
        key = MMD_functions[i].__name__
        p_values[key] = np.array([-1.0] * N)
        mmd_samples[key] = np.array([-1.0] * N)



    # Store K max for acceptance region
    Kmax = np.array([0] * N)


    with concurrent.futures.ProcessPoolExecutor() as executor:
        results = [executor.submit(mg.iteration, n , kernel, normalize, MMD_functions, bg1, bg2, B, kernel_hypothesis) for n in [part] * d]

        # For loop that takes the output of each process and concatenates them together
        cnt = 0
        for f in concurrent.futures.as_completed(results):
            
            for k,v in f.result().items():
                if k == "Kmax":
                    Kmax[cnt:(cnt+part)] = v
                elif k == 'p_values':
                    for i in range(len(MMD_functions)):
                        key = MMD_functions[i].__name__
                        p_values[key][cnt:(cnt+part)] = v[key]
                elif k == 'mmd_samples':
                    for i in range(len(MMD_functions)):
                        key = MMD_functions[i].__name__
                        mmd_samples[key][cnt:(cnt+part)] = v[key]

            cnt += part


    for i in range(len(MMD_functions)):
                        key = MMD_functions[i].__name__
                        if np.any(p_values[key] < 0):
                            warnings.warn(f"Some p value is negative for {key}") 

    


    # Calculate ROC curve

    for alpha in alphas:
        
        # type II error is the case when be p_val > alpha so power is 1 - #(p_val>alpha)/N <-> (N - #(p_val>alpha))/N <-> #(p_val<alpha)/N

        # power of MMD tests (including distribution free test)
        power_mmd = dict()

        for i in range(len(MMD_functions)):
            key = MMD_functions[i].__name__
            power_mmd[key] = (np.array(p_values[key]) < alpha).sum()/float(N)
            if key == 'MMD_u':
                tmp = mmd_samples[key] < (4*Kmax/np.sqrt(float(n1)))*np.sqrt(np.log(1.0/alpha))
                power_mmd[key + "_distfree"] = 1.0 - float(np.sum(tmp))/float(N)
            if key == 'MMD_b':
                tmp = np.sqrt(mmd_samples[key]) < np.sqrt(2.0*Kmax/float(n1))*(1.0 + np.sqrt(2.0*np.log(1/alpha)))
                power_mmd[key + "_distfree"] = 1.0 - float(np.sum(tmp))/float(N)



        # Store the run information in a dataframe,
        tmp = pd.DataFrame({'kernel': str(kernel), 
                        'alpha':alpha,
                        'probs_1':str(probs_1),
                        'sizes_1':str(sizes_1),
                        'label_pmf_1':str(label_pmf_1),
                        'probs_2':str(probs_2),
                        'sizes_2':str(sizes_2),
                        'label_pmf_2':str(label_pmf_2),
                        'n':n1,
                        'm':n2,
                        'timestap':time,
                        'B':B,
                        'N':N,
                        'run_time':str((datetime.now() - now))}, index = [0])
        # Add power
        if len(power_mmd) != 0:
            for k,v in power_mmd.items():
                tmp[k] = v

        # add to the main data frame
        df = df.append(tmp, ignore_index=True)

    # Save the dataframe at each iteration each such that if out-of-memory or time-out happen we at least have some of the information.
    with open(path, 'wb') as f:
            pickle.dump(df, f)

    print(datetime.now() - now )

