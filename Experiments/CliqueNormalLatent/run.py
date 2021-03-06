

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

from scipy.linalg.misc import norm

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
# Where to save results
parser.add_argument('-p', '--path', type=str,metavar='', help='Give path (including filename) to where the data should be saved')

# Number of Iterations specifics
parser.add_argument('-B', '--NrBootstraps',metavar='', type=int, help='Give number of bootstraps')
parser.add_argument('-N', '--NrSampleIterations',metavar='', type=int, help='Give number of sample iterations')

# Graph generation specifics
parser.add_argument('-n1', '--NrSamples1', type=int,metavar='', help='Number of graphs in sample 1')
parser.add_argument('-n2', '--NrSamples2', type=int,metavar='', help='Number of graphs in sample 2')
parser.add_argument('-nnode1', '--NrNodes1', type=int,metavar='', help='Number of nodes in each graph in sample 1')
parser.add_argument('-nnode2', '--NrNodes2', type=int,metavar='', help='Number of nodes in each graph in sample 2')
parser.add_argument('-latent1', '--latent1', type=float,metavar='', help='The mean of the latent normal governing the mean of nodes in a graph in sample 1')
parser.add_argument('-latent2', '--latent2', type=float,metavar='', help='The mean of the latent normal governing the mean of nodes in a graph in sample 2')

# parallelization specifics
parser.add_argument('-d', '--division', type=int,metavar='', help='How many processes')

# Kernel specifics
parser.add_argument('-kernel', '--kernel', type=str,metavar='', help='Kernel')
parser.add_argument('-norm', '--normalize', type=int,metavar='', help='Should kernel be normalized')

# Shared parameters
parser.add_argument('-nitr', '--NumberIterations', type=int,metavar='', help='WL nr iterations, wl, wloa, wwl, dk, hashkernel ')
parser.add_argument('-wlab', '--wlab', type=int,metavar='', help='With labels?, sp, rw, pyramid')
parser.add_argument('-type', '--type', type=str,metavar='', help='Type of... rw (geometric or exponential) , deepkernel (sp or wl), haskenrel(sp or wl)')
parser.add_argument('-l', '--discount', type=float,metavar='', help='RW, wwl lambda/discount')
parser.add_argument('-tmax', '--tmax', type=int,metavar='', help='Maximum number of walks, used in propagation and RW.')

# Hash graph
parser.add_argument('-iterations', '--iterations', type=int,metavar='', help='hash kernel iteration')
parser.add_argument('-basekernel', '--basekernel', type=str,metavar='', help='Base kernel wl or sp')
parser.add_argument('-scale', '--scale', type=int,metavar='', help='Scale attrubutes?')


# Propagation only
parser.add_argument('-w', '--binwidth', type=float,metavar='', help='Bin width.')
parser.add_argument('-M', '--Distance', type=str,metavar='', help='The preserved distance metric (on local sensitive hashing):')

# Gik
parser.add_argument('-distances', '--distances', type=int,metavar='', help='node neigbourhood depth')

group = parser.add_mutually_exclusive_group()
group.add_argument('-v', '--verbose', action='store_false', help = 'print verbose')


args = parser.parse_args()



if __name__ == "__main__":
    # Erdos Renyi graphs
    # np.seterr(divide='ignore', invalid='ignore')


    # NOTE IF args.variable has not been given then args.variable returns None.  

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
    nnode1 = args.NrNodes1
    nnode2 = args.NrNodes2
    loc_latent_1 = args.latent1
    loc_latent_2 = args.latent2

    # number of cores
    d = args.division

    kernel_name = args.kernel
    # add parameters parsed, may be none
    kernel_specific_params = dict()

    # WL iterations
    kernel_specific_params['nitr'] = args.NumberIterations   
    
    # with labels?
    if args.wlab is None:
        kernel_specific_params['with_labels'] = bool(1)
    else:
        kernel_specific_params['with_labels'] = bool(args.wlab)


    
    kernel_specific_params['w'] = args.binwidth

    # gik
    kernel_specific_params['distances'] = args.distances

    # Hash
    kernel_specific_params['iterations'] = args.iterations
    kernel_specific_params['scale'] = args.scale
    kernel_specific_params['basekernel'] = args.basekernel

    # Propagation
    kernel_specific_params['tmax'] = args.tmax
    kernel_specific_params['M'] = args.Distance

    kernel_specific_params['type'] = args.type  
    kernel_specific_params['discount'] = args.discount   


    
    # functions used for kernel testing
    MMD_functions = [mg.MMD_b, mg.MMD_u]
    
    # initialize bootstrap class, we only want this to be initalized once so that numba njit
    # only gets compiled once (at first call)
    kernel_hypothesis = mg.BoostrapMethods(MMD_functions)

    # Initialize Graph generator class
    bg1 = mg.CliqueGraph(n1, nnode1,  l = 'samelabels_float', a = 'normal_conditional_on_latent_mean_rv', loc_latent = loc_latent_1)
    bg2 = mg.CliqueGraph(n2, nnode2,  l = 'samelabels_float', a = 'normal_conditional_on_latent_mean_rv', loc_latent = loc_latent_2)

    # Probability of type 1 error
    alphas = np.linspace(0.01, 0.99, 99)


    now = datetime.now()
    time = pd.Timestamp(now)
    print(time)
    
    # Kernel specification
    # kernel = [{"name": "WL", "n_iter": 4}]

    if kernel_name == 'gh':
        kernel = [{"name": "GH", 'kernel_type':kernel_specific_params['type']}]
    elif kernel_name == 'hash':
        kernel = {'base_kernel':kernel_specific_params['basekernel'], 'iterations':kernel_specific_params['iterations'],
                                                                    'lsh_bin_width':kernel_specific_params['w'], 
                                                                    'sigma':1,
                                                                    'normalize':bool(normalize),
                                                                    'scale_attributes':bool(kernel_specific_params['scale']),
                                                                    'attr_name': 'attr',
                                                                    'label_name':'label',
                                                                    'wl_iterations':kernel_specific_params['nitr'],
                                                                    'normalize':normalize}
    elif kernel_name == 'gik':
        kernel = {'local':True, 'label_name':'label', 'attr_name':'attr', 
        'wl_itr':kernel_specific_params['nitr'], 
        'distances':kernel_specific_params['distances'],  
        'c':kernel_specific_params['discount'],
        'normalize':normalize}
    elif kernel_name == 'prop':
        kernel = [{"name": "propagation", "t_max": kernel_specific_params['tmax'], "w":kernel_specific_params['w'], "M":kernel_specific_params['M'], 'with_attributes':True}]

    else:
        raise ValueError(f'No kernel names {kernel_name}')
    
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


    if kernel_name == 'dk':
        kernel_library="deepkernel"
    elif kernel_name == 'wwl':
        kernel_library = 'wwl'
    elif kernel_name == 'hash':
        kernel_library = 'hash'
    elif kernel_name == 'gik':
        kernel_library = 'gik'
    else:
        kernel_library = "Grakel"

    with concurrent.futures.ProcessPoolExecutor() as executor:
        results = [executor.submit(mg.iteration, n , kernel, normalize, MMD_functions, bg1,bg2, B, kernel_hypothesis, kernel_library, node_labels_tag='attr') for n in [part] * d]

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
            #print(f'{key} pvaalue {p_values[key]}')
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
                        'normalize':normalize,
                        'nr_nodes_1': nnode1,
                        'nr_nodes_2': nnode2,
                        'loc_latent_1':loc_latent_1,
                        'loc_latent_1':loc_latent_1,
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

        # add specific kernel value
        for k,v in kernel_specific_params.items():
            if not v is None:
                tmp[k] = v



        # add to the main data frame
        df = df.append(tmp, ignore_index=True)

    # Save the dataframe at each iteration each such that if out-of-memory or time-out happen we at least have some of the information.
    with open(path, 'wb') as f:
            pickle.dump(df, f)

    print(datetime.now() - now )

