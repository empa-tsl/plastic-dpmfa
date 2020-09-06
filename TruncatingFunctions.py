# -*- coding: utf-8 -*-
"""
Created on Mon Apr 29 09:54:22 2019

@author: dew
"""

from scipy.stats import trapz
import numpy.random as nr
import numpy as np

#============= FUNCTION FOR TRUNCATING TRAPEZOIDAL DISTRIBUTIONS ==============

def TrapezTrunc(TC1, TC2, spread1, spread2, N, linf=float('-inf'), lsup=float('inf')): 
    if TC1+TC2 == 0:
        return np.asarray([0]*N)
    
    # define variables for trapezoidal distribution
    if TC1 < TC2:
        A = TC1*(1-spread1)
        B = TC2*(1+spread2)
        c = (TC1-A)/(B-A)
        d = (TC2-A)/(B-A)
    else:
        A = TC2*(1-spread2)
        B = TC1*(1+spread1)
        c = (TC2-A)/(B-A)
        d = (TC1-A)/(B-A)
    
    loc = A
    scale = B-A
    
    dist = trapz.rvs(c, d, loc, scale, N)
    
    truncdist = [i for i in dist if i >= linf]
    truncdist = [i for i in truncdist if i <= lsup]
    
    
    while len(truncdist) < N:
         adddist = trapz.rvs(c, d, loc, scale, N-len(truncdist))
         truncadddist = [i for i in adddist if i >= linf]
         truncadddist = [i for i in truncadddist if i <= lsup]
         
         truncdist = truncdist + truncadddist
    
    return np.asarray(truncdist)

#============= FUNCTION FOR TRUNCATING TRIANGULAR DISTRIBUTIONS ===============
    
def TriangTrunc(TC1, spread1, N, linf=float('-inf'), lsup=float('inf')):
    if TC1 == 0:
        return np.asarray([0]*N)
    
    if TC1 == 1 and lsup == 1:
        return np.asarray([1]*N)
    
    # define variables for trapezoidal distribution
    A = TC1*(1-spread1)
    B = TC1*(1+spread1)
    
    dist = nr.triangular(A, TC1, B, N)
    
     # remove all that's not in the proper range - we end with a distribution with a length < N
    truncdist = [i for i in dist if i >= linf]
    truncdist = [i for i in truncdist if i <= lsup]
    
    # Create the "same" triangular distribution with the missing number of samples, and remove all that's not in the range.
    # "while" -> do that until you have N samples. 
    while len(truncdist) < N:
         adddist = nr.triangular(A, TC1, B, N-len(truncdist))
         truncadddist = [i for i in adddist if i >= linf]
         truncadddist = [i for i in truncadddist if i <= lsup]
         
          # concatenate both triangular distributions
         truncdist = truncdist + truncadddist
    
    return np.asarray(truncdist)