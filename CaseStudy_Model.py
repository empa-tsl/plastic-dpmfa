# -*- coding: utf-8 -*-
"""

Created on 09.04.2020
@author: dew
Test model for importing SQL databases

"""

### PACKAGE IMPORT AND VARIABLE DEFINITION ########################################################################

# import necessary packages
import os
import sqlite3
import pandas as pd
import numpy as np
from dpmfa import components as cp
from dpmfa import model as mod
import math
import TruncatingFunctions as tr


### OPEN DATABASE #################################################################################################

# open database
connection = sqlite3.connect(os.path.join("casestudy_data","DPMFA_Plastic_EU.db"))
cursor = connection.cursor()


### SETUP MODEL ###################################################################################################

# create model
model = mod.Model('Simple Experiment for Testing')

RUNS = 10

mat = "PP"

# extract years from input
cursor.execute("SELECT DISTINCT year FROM input")
years_input = cursor.fetchall()
years_input = [item for sublist in years_input for item in sublist]

# extract years from tc
cursor.execute("SELECT DISTINCT year FROM transfercoefficients")
years_tc = cursor.fetchall()
years_tc = [item for sublist in years_tc for item in sublist]

startYear = max(min(years_tc), min(x for x in years_input if x is not None))
endYear = min(max(years_tc), max(x for x in years_input if x is not None))

# define period range (extracted from number of years in inflow)
periodRange = np.arange(0,endYear-startYear+1)



### COMPARTMENT DEFINITION ######################################################################################

# extract possible compartment names from database
cursor.execute("SELECT DISTINCT fulllabel,name FROM compartments")
complist = cursor.fetchall()

# extract list of compartments being in the lifetimes table
stocklist = list(pd.read_csv(os.path.join("casestudy_data","Lifetimes_Summary.csv"),sep=";",decimal=",").columns)
stocklist.remove('Year')

# extract list of compartments with outflows
cursor.execute("SELECT DISTINCT comp1 FROM transfercoefficients")
outflowlist = cursor.fetchall()
# flatten the list
outflowlist = [item for sublist in outflowlist for item in sublist]

# get a name of each flow existing (unique values!)
flowlist = list(set([item[0]+' to '+item[1] for item in outflowlist]))

# create the list of compartments that will be inserted into the model
CompartmentList = []

# loop over compartments
for i in np.arange(len(complist)):
    
    # get names for checking
    compfull = complist[i][0]
    compname = complist[i][1]
    
    # test if compname has lifetimes associated. If yes, insert as Stock
    if compfull in stocklist:
        CompartmentList.append(cp.Stock(compfull, logInflows=True, logOutflows=True, logImmediateFlows=True))
        print('Inserting "',compname, '" as a Stock compartment')
        
    # test if comp has outflows. If yes, insert as FlowCompartment
    elif compfull in outflowlist: 
        CompartmentList.append(cp.FlowCompartment(compfull, logInflows=True, logOutflows=True))
        print('Inserting "',compname, '" as a Flow compartment')
        
    # otherwise, insert as Sink
    else:
        CompartmentList.append(cp.Sink(compfull, logInflows=True))
        print('Inserting "',compname, '" as a Sink')


# insert compartments into model                 
model.setCompartments(CompartmentList)



### INPUT DEFINITION ############################################################################################

# extract list of compartments with input
cursor.execute("SELECT DISTINCT comp FROM input")
stocklist = cursor.fetchall()
stocklist = [item for sublist in stocklist for item in sublist]

# loop over compartments
for j in np.arange(len(complist)):
    
    # get names for checking
    compfull = complist[j][0]
    compname = complist[j][1]
    
    # if there is no input for that compartment, continue
    if not compfull in stocklist:
        continue
    
    # for storing distributions (one entry per year)
    inflow_dist = []
    
    for i in periodRange:
        
        # import data from database for compartment compname and year i+startYear and material mat
        cursor.execute("SELECT * FROM input WHERE comp='"+compfull+"' AND year="+str(i+startYear)+" AND mat='"+mat+"'")        
        data = cursor.fetchall()
        
        # check if any double data for compartment and year
        if len(data) == 1:
            
            # load inflow
            inflow = data[0][4]
            
            # if the raw data is 0, include only zeroes
            if inflow == 0:
                inflow_dist.append(np.asarray([0]*RUNS))
            
            # otherwise create a triangular distribution
            else:    
                
                # load DQIS
                dqis = data[0][5:10]
                
                # calculate CV
                CV = 1.5*math.sqrt( math.exp(2.21*(dqis[0]-1)) +
                                    math.exp(2.21*(dqis[1]-1)) +
                                    math.exp(2.21*(dqis[2]-1)) +
                                    math.exp(2.21*(dqis[3]-1)) +
                                    math.exp(2.21* dqis[4]   ) )/100*2.45
                               
                # create a triangular distribution
                inflow_dist.append(tr.TriangTrunc(inflow,
                                                  CV,
                                                  1, 0, float('inf')))
            
        elif len(data) == 2:
            
            # load inflow
            inflow = [data[0][4],data[1][4]]
            
            # if the raw data is 0, include only zeroes
            if inflow[0] == 0 and inflow[1] == 0:
                inflow_dist.append(np.asarray([0]*RUNS))
            
            # otherwise create a trapezoidal distribution
            else:    
                   
                # calculate CV
                CV = []
                
                dqis = data[0][5:10]
                CV.append(1.5*math.sqrt( math.exp(2.21*(dqis[0]-1)) +
                          math.exp(2.21*(dqis[1]-1)) +
                          math.exp(2.21*(dqis[2]-1)) +
                          math.exp(2.21*(dqis[3]-1)) +
                          math.exp(2.21* dqis[4]   ) )/100*2.45)
                  
                dqis = data[1][5:10]
                CV.append(1.5*math.sqrt( math.exp(2.21*(dqis[0]-1)) +
                          math.exp(2.21*(dqis[1]-1)) +
                          math.exp(2.21*(dqis[2]-1)) +
                          math.exp(2.21*(dqis[3]-1)) +
                          math.exp(2.21* dqis[4]   ) )/100*2.45)
                
                # create a trapezoidal distribution
                inflow_dist.append(tr.TrapezTrunc(inflow[0],
                                                  inflow[1],
                                                  CV[0], 
                                                  CV[1],
                                                  1, 0, float('inf')))
            
        else:
            raise Exception('There is an error in the database for compartment "{a}", year "{b}" and material "{c}".'.format(a = compname, b = str(i+startYear), c = mat))
            
            
    # include inflows in model
    model.addInflow(cp.ExternalListInflow(compname, [cp.RandomChoiceInflow(inflow_dist[x]) for x in periodRange]))  



### LIFETIMES DEFINITION ########################################################################################


#Stock1.localRelease = cp.ListRelease([0.5,0.2,0.2,0.1])
    






### FLOW DEFINITION #############################################################################################


#Inflow1.transfers = [cp.StochasticTransfer(nr.triangular, [0.7, 0.8, 0.9], Stock1, priority = 2),
#                     cp.ConstTransfer(1, Flow1, priority = 1)]
#
#Inflow2.transfers = [cp.StochasticTransfer(nr.triangular, [0.4, 0.6, 0.8], Flow1, priority = 2),
#                     cp.ConstTransfer(1, Sink3, priority = 1)]
#
#Flow1.transfers   = [cp.StochasticTransfer(nr.triangular, [0.4, 0.5, 0.6], Stock1, priority = 2),
#                     cp.ConstTransfer(1, Sink2, priority = 1)]
#

#Stock1.transfers   = [cp.ConstTransfer(1, Sink1, priority = 1)]







## close connection
#connection.close()
#
#

















#
#
#
#
#
#
#
#
#
#
#

