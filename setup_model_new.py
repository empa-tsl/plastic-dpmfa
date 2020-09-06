# -*- coding: utf-8 -*-
"""

Created on 09.04.2020
@author: dew
Function for setting up a model based on a database

"""

### PACKAGE IMPORT AND VARIABLE DEFINITION ########################################################################

# import necessary packages
import sqlite3
import numpy as np
import math

from dpmfa import components as cp
from dpmfa import model as mod
import TruncatingFunctions as tr

def setupModel(pathtoDB,modelname,RUNS,mat, startYear, endYear):
    """
    imports an SQL database and implements a model using the dpmfa package
    """
    
    # open database
    connection = sqlite3.connect(pathtoDB)
    cursor = connection.cursor()
    
    # create model
    model = mod.Model(modelname)
    
    # extract years from input
    cursor.execute("SELECT DISTINCT year FROM input")
    years_input = cursor.fetchall()
    years_input = [item for sublist in years_input for item in sublist]
    
    # extract years from tc
    cursor.execute("SELECT DISTINCT year FROM transfercoefficients")
    years_tc = cursor.fetchall()
    years_tc = [item for sublist in years_tc for item in sublist]
    
    print("Temporal range of input: "+str(min(years_input))+" - "+str(max(years_input)))
    print("Temporal range of TCs: "+str(min(years_tc))+" - "+str(max(years_tc)))
    print("Currently considering: "+str(startYear)+" - "+str(endYear))
    
    # define period range (extracted from number of years in inflow)
    periodRange = np.arange(0,endYear-startYear+1)
    
    
    ### COMPARTMENT DEFINITION
    
    # extract possible compartment names from database
    cursor.execute("SELECT DISTINCT * FROM compartments")
    complist = cursor.fetchall()
    
    # extract list of compartments being in the lifetimes table
    cursor.execute("SELECT DISTINCT comp FROM lifetimes")
    stocklist = cursor.fetchall()
    # flatten the list
    stocklist = [item for sublist in stocklist for item in sublist]
    
    # extract list of compartments with outflows
    cursor.execute("SELECT DISTINCT comp1 FROM transfercoefficients")
    outflowlist = cursor.fetchall()
    # flatten the list
    outflowlist = [item for sublist in outflowlist for item in sublist]
    
    # create the dictionary of compartments that will be inserted into the model
    CompartmentDict = {}
    
    # loop over compartments
    for i in np.arange(len(complist)):
        
        # get names for checking
        compfull = complist[i][0]
        compname = complist[i][1]
        
        # test if compname has lifetimes associated. If yes, insert as Stock
        if compfull in stocklist:
            CompartmentDict[compfull] = cp.Stock(compname, logInflows=True, logOutflows=True, logImmediateFlows=True)
            print('Inserting "',compname, '" as a Stock compartment')
            if(complist[i][2] != "Stock"):
                print('The estimation as "Stock" does not correspond to the compartments table in the database')
            
        # test if comp has outflows. If yes, insert as FlowCompartment
        elif compname in outflowlist:
            CompartmentDict[compfull] = cp.FlowCompartment(compname, logInflows=True, logOutflows=True)
            print('Inserting "',compname, '" as a Flow compartment')
            if(complist[i][2] != "Flow"):
                print('The estimation as "Flow" does not correspond to the compartments table in the database')
            
        # otherwise, insert as Sink
        else:
            CompartmentDict[compfull] = cp.Sink(compname, logInflows=True)
            print('Inserting "',compname, '" as a Sink')
            if(complist[i][2] != "Sink"):
                print('The estimation as "Sink" does not correspond to the compartments table in the database')
    
    
    ### FLOW DEFINITION
    
    # loop over compartments with a defined outflow
    for comp in outflowlist:
        
        # extract destination compartments
        cursor.execute("SELECT DISTINCT comp2 FROM transfercoefficients WHERE (comp1='"+comp+"' AND mat = '"+mat+"')")
        destlist = cursor.fetchall()
        # flatten the list
        destlist = [item for sublist in destlist for item in sublist]
        
        # short compartment name for implementation
        for i in range(len(complist)):
            if complist[i][1] == comp:
                ind = i
        compname = complist[ind][0]
        
        # create a transfer list
        CompartmentDict[compname].transfers = []
        
        # loop over destination compartments
        for dest in destlist:
            print("Implementing flow from "+comp+" to "+dest+"...")
            
            # short compartment name for implementation
            for i in range(len(complist)):
                if complist[i][1] == dest:
                    ind = i
            destname = complist[ind][0]
            
            # import data
            cursor.execute("SELECT * FROM transfercoefficients WHERE (comp1 = '"+comp+"' AND comp2 = '"+dest+"' AND mat = '"+mat+"')")
            df = cursor.fetchall()
            
            # create vectors
            dfvalue = []
            dfsource = []
            dfyears = []
            dfpriority = []
            
            for i in np.arange(len(df)):
                dfvalue.append(df[i][5])
                dfsource.append(df[i][12])
                dfyears.append(df[i][3])
                dfpriority.append(df[i][6])
            
            # test that priorities are adequate
            if(len(set(dfpriority)) != 1):
                raise Exception('The priorities are not equal for all years for the transfer coefficient from "{a}" to "{b}".'.format(a = comp, b = dest))
            
            # implement transfers
            if(all(x == 0 for x in dfvalue)):
                # if all TCs are 0, implement a ConstTransfer (no distribution possible)
                CompartmentDict[compname].transfers.append(cp.ConstTransfer(0, CompartmentDict[destname], priority = dfpriority[0]))
            
            elif(all(x == 1 for x in dfvalue)):
                # if all TCs are 1, implement a ConstTransfer (no distribution possible)
                CompartmentDict[compname].transfers.append(cp.ConstTransfer(1, CompartmentDict[destname], priority = dfpriority[0]))
                
            elif(all((x == "rest" or x == "Rest") for x in dfvalue) or
                 all((x == "rest" or x == "Rest") for x in dfsource)):
                # if all TCs are "rest", implement a ConstTransfer with low priority
                CompartmentDict[compname].transfers.append(cp.ConstTransfer(1, CompartmentDict[destname], priority = 1))               
                
            else:
                
                # create list for storing distributions for all years
                distlist = []
                
                # loop over years
                for i in set(dfyears):
                    
                    # find index corresponding to year i
                    # logical list (true = corresponding year)
                    logind = [i in x for x in df]
                    ind = [i for i, x in enumerate(logind) if x]
                    
                    # check if there are any double TCs, if yes, append trapezoidal distribution
                    if len(ind) == 2:
                        value1 = df[ind[0]][5]
                        value2 = df[ind[1]][5]
                        
                        # calculate the first CV
                        dqis = df[ind[0]][7:12]
                        CV1 = 1.5*math.sqrt(math.exp(2.21*(dqis[0]-1)) +
                                            math.exp(2.21*(dqis[1]-1)) +
                                            math.exp(2.21*(dqis[2]-1)) +
                                            math.exp(2.21*(dqis[3]-1)) +
                                            math.exp(2.21* dqis[4]   ) )/100*2.45
                        
                        # calculate the second CV
                        dqis = df[ind[1]][7:12]
                        CV2 = 1.5*math.sqrt(math.exp(2.21*(dqis[0]-1)) +
                                            math.exp(2.21*(dqis[1]-1)) +
                                            math.exp(2.21*(dqis[2]-1)) +
                                            math.exp(2.21*(dqis[3]-1)) +
                                            math.exp(2.21* dqis[4]   ) )/100*2.45
                        
                        distlist.append(cp.TransferDistribution(tr.TrapezTrunc, [value1, value2, CV1, CV2, 1, 0, 1]))
                        
                    elif len(ind) == 1:
                        # if no, append triangular distribution
                        
                        value = df[ind[0]][5]
                        
                        # calculate the CV
                        if value == 0:
                            CV = 0
                        else:
                            dqis = df[ind[0]][7:12]
                            
                            CV = 1.5*math.sqrt(math.exp(2.21*(dqis[0]-1)) +
                                               math.exp(2.21*(dqis[1]-1)) +
                                               math.exp(2.21*(dqis[2]-1)) +
                                               math.exp(2.21*(dqis[3]-1)) +
                                               math.exp(2.21* dqis[4]   ) )/100*2.45
                            
                        distlist.append(cp.TransferDistribution(tr.TriangTrunc, [value, CV, 1, 0, 1]))
                        
                    else:
                        raise Exception('There should be exactly one or two datapoints in the database for the TC from "{a}" to "{b}", year "{c}" and material "{d}".'.format(a = comp, b = dest, c = i, d = mat))
    
                # implement a TimeDependentListTransfer based on all distributions calculated above
                CompartmentDict[compname].transfers.append(cp.TimeDependentDistributionTransfer(distlist,
                               CompartmentDict[destname],
                               priority = dfpriority[0]))
                      
    ### CLEAN OUT LIST OF COMPARTMENTS

    # check if some compartments are empty, if yes remove to avoid bugs (mormalization of zero TCs does not work)
    cursor.execute("SELECT DISTINCT comp FROM input WHERE mat = '"+mat+"' AND NOT value = 0")
    inputlist = cursor.fetchall()
    inputlist = [item for sublist in inputlist for item in sublist]
    
    # stores a logical value for each compartment in a dictionary
    complog = {c:False for c in [l[1] for l in complist]}
    
    for comp in inputlist:
       
        # check if inflow is not zero for any period
        cursor.execute("SELECT value FROM input WHERE comp='"+comp+"' AND mat='"+mat+"'")        
        data = cursor.fetchall()
        data = [item for sublist in data for item in sublist]
        
        # skip compartment if there is no input
        if not any(x != 0 for x in data):
            continue
            
        # else do not clean out compartment
        complog[comp] = True
        
        # list for storing compartments already analyzed
        companalyzed = []
        
        # start while loop at comp
        comptoanalyze = [comp]
        
        while len(comptoanalyze) != 0:
            
            # copy for loop
            comploop = comptoanalyze
            
            # loop over compartments
            for startcomp in comploop:
                
                # loop over destination compartments
                cursor.execute("SELECT DISTINCT comp2 FROM transfercoefficients WHERE (comp1='"+startcomp+"' AND mat = '"+mat+"' AND NOT value == 0)")
                dest = cursor.fetchall()
                dest = [item for sublist in dest for item in sublist]
                
                # append startcomp to companalyzed
                companalyzed.append(startcomp)
                
                # if no destination compartments, move on
                if len(dest) == 0:
                    continue
                
                # else look at destination compartments closer
                for endcomp in dest:
                    
                    # check only if wasn't checked earlier
                    if endcomp in companalyzed:
                        continue
                    
                    # import data
                    cursor.execute("SELECT value FROM transfercoefficients WHERE (comp1 = '"+startcomp+"' AND comp2 = '"+endcomp+"' AND mat = '"+mat+"')")
                    data = cursor.fetchall()
                    data = [item for sublist in data for item in sublist]
                    
                    # check if any data point is not zero, if yes, mark as not for cleaning out
                    if any(x != 0 for x in data):
                            
                        complog[endcomp] = True
                        
                        # add destinations from that compartment to comptoanalyze
                        cursor.execute("SELECT DISTINCT comp2 FROM transfercoefficients WHERE (comp1 = '"+endcomp+"' AND mat = '"+mat+"' AND NOT value == 0)")
                        otherdest = cursor.fetchall()
                        otherdest = [item for sublist in otherdest for item in sublist]
                        
                        # set to true since flow not zero
                        for d in otherdest:
                            complog[d] = True
                        
                        # save as to analyze further
                        comptoanalyze = comptoanalyze + otherdest
                    
                    # remove from comptoanalyze
                    comptoanalyze = [x for x in comptoanalyze if x != endcomp]
                    
                    # remove duplicates
                    comptoanalyze = list(set(comptoanalyze))
                
                # add all intermediate destinations to companalyzed
                companalyzed = list(set(companalyzed + dest))
            
            # remove comps already analyzed
            comptoanalyze = [x for x in comptoanalyze if not x in companalyzed]
    
    
    # remove from dictionary
    for i in np.arange(len(complist)):
        
        # remove compartment from dictionary if not in log
        if not complog[complist[i][1]]:
            CompartmentDict.pop(complist[i][0])
        
        else:
            
            if isinstance(CompartmentDict[complist[i][0]], cp.Sink):
                continue
            
            # remove transfers from dictionary if target is not in log
            transfers = CompartmentDict[complist[i][0]].transfers
            
            for dest in [t.target.name for t in transfers]:
                if not complog[dest]:
                    CompartmentDict[complist[i][0]].transfers = [x for x in CompartmentDict[complist[i][0]].transfers if complog[x.target.name]]
    
    
    ### INPUT DEFINITION
    
    # extract list of compartments with input
    cursor.execute("SELECT DISTINCT comp FROM input")
    inputlist = cursor.fetchall()
    inputlist = [item for sublist in inputlist for item in sublist]
    
    # loop over compartments
    for j in np.arange(len(complist)):
        
        # get names for checking
        compfull = complist[j][0]
        compname = complist[j][1]
        
        # check if in model still (since cleaning compartments)
        if not complog[compname]:
            print("--> "+compname+ " skipped")
            continue
        
        # if there is no input for that compartment, continue
        if not compname in inputlist:
            continue
        
        # define comp
        comp = CompartmentDict[compfull]
        
        # check if any input data is negative
        cursor.execute("SELECT value FROM input WHERE comp='"+compname+"' AND mat='"+mat+"'")        
        data = cursor.fetchall()
        data = [item for sublist in data for item in sublist]
    
        if any(x < 0 for x in data):
            raise Exception("There is a negative input for compartment "+compname)
        
        # for storing distributions (one entry per year)
        inflow_dist = []
        
        for i in periodRange:
            
            # import data from database for compartment compname and year i+startYear and material mat
            cursor.execute("SELECT * FROM input WHERE comp='"+compname+"' AND year="+str(i+startYear)+" AND mat='"+mat+"'")        
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
                                                      RUNS, 0, float('inf')))
                
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
                                                      RUNS, 0, float('inf')))
                
            else:
                raise Exception('There is an error in the database for compartment "{a}", year "{b}" and material "{c}".'.format(a = compname, b = str(i+startYear), c = mat))
                
                
        # include inflows in model
        model.addInflow(cp.ExternalListInflow(comp, [cp.RandomChoiceInflow(inflow_dist[x]) for x in periodRange]))  
    
    
    ### LIFETIMES DEFINITION
    
    # extract list of compartments with input
    cursor.execute("SELECT * FROM lifetimes")
    df = cursor.fetchall()
    
    # loop over stocks
    for comp in stocklist:
        
        if not comp in CompartmentDict:
            continue
    
        # create lifetime vectors
        lifetimedist = []
        
        for i in np.arange(len(df)):
            if(df[i][1] == comp):
                lifetimedist.append(df[i][3])
        
        # insert lifetime distribution into compartment object
        CompartmentDict[comp].localRelease = cp.ListRelease(lifetimedist)
    
    
    ### IMPLEMENT COMPARTMENTS INTO MODEL
    
    # transform into list for implementing into model
    CompartmentList = list(CompartmentDict.values())
    
    # insert compartments into model                 
    model.setCompartments(CompartmentList)
    
    # close connection
    connection.close()
    
    return model
