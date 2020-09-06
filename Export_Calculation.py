# -*- coding: utf-8 -*-

# import necessary packages
import sqlite3
import numpy as np
import os

from time import localtime, strftime

from dpmfa import components as cp
from dpmfa import model as mod
from dpmfa import simulator as sc
   
# open database
#pathtoDB = os.path.join("data_casestudy","DPMFA_Plastic_EU_inclExport.db")
pathtoDB = os.path.join("data_casestudy","DPMFA_Plastic_CH_inclExport.db")
connection = sqlite3.connect(pathtoDB)
cursor = connection.cursor()


# set material
mat = "LDPE"
#mat = "EPS"
#mat = "PP"
#mat = "HDPE"
#mat = "PS"
#mat = "PVC"
#mat = "PET"

#for mat in ["LDPE", "HDPE", "PP", "PS", "EPS", "PVC", "PET"]
    
print("\n\n"+strftime("%H:%M:%S", localtime())+" Starting export calculation for "+mat+"...\n")

# create model
model = mod.Model("Export calculation "+mat)

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


### COMPARTMENT DEFINITION

print(strftime("%H:%M:%S", localtime())+" Inserting compartments")

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
        
    # test if comp has outflows. If yes, insert as FlowCompartment
    elif compname in outflowlist:
        CompartmentDict[compfull] = cp.FlowCompartment(compname, logInflows=True, logOutflows=True)
        
    # otherwise, insert as Sink
    else:
        CompartmentDict[compfull] = cp.Sink(compname, logInflows=True)


### FLOW DEFINITION

print(strftime("%H:%M:%S", localtime())+" Inserting transfers")

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
                
                # check if there are any double TCs, if yes, calculate the mean
                if len(ind) == 2:
                    value = (df[ind[0]][5]+df[ind[1]][5])/2
                    distlist.append(cp.TransferConstant(value))
                    
                elif len(ind) == 1:
                    value = df[ind[0]][5]
                    distlist.append(cp.TransferConstant(value))
                    
                else:
                    raise Exception('There should be exactly one or two datapoints in the database for the TC from "{a}" to "{b}", year "{c}" and material "{d}".'.format(a = comp, b = dest, c = i, d = mat))

            # implement a TimeDependentListTransfer based on all distributions calculated above
            CompartmentDict[compname].transfers.append(cp.TimeDependentDistributionTransfer(distlist,
                           CompartmentDict[destname],
                           priority = dfpriority[0]))
    

### CLEAN OUT LIST OF COMPARTMENTS

print(strftime("%H:%M:%S", localtime())+" Cleaning compartments")

# check if some compartments are empty, if yes remove to avoid bugs (mormalization of zero TCs does not work)
cursor.execute("SELECT DISTINCT comp FROM input WHERE mat = '"+mat+"' AND NOT value = 0")
inputlist = cursor.fetchall()
inputlist = [item for sublist in inputlist for item in sublist]

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
    
    # loop over destination compartments
    cursor.execute("SELECT DISTINCT comp2 FROM transfercoefficients WHERE (comp1='"+comp+"' AND NOT value == 0 AND mat = '"+mat+"')")
    comptoanalyze = cursor.fetchall()
    comptoanalyze = [item for sublist in comptoanalyze for item in sublist]
    
    # list for storing compartments already analyzed
    companalyzed = []
    companalyzed.append(comp)
    
    # start while loop at comp
    startcomp = comp
    
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

print("")



### LIFETIMES DEFINITION

print(strftime("%H:%M:%S", localtime())+" Inserting lifetimes")

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
    
print(strftime("%H:%M:%S", localtime())+" Inserting compartments")

# transform into list for implementing into model
CompartmentList = list(CompartmentDict.values())

# insert compartments into model                 
model.setCompartments(CompartmentList)


### INPUT DEFINITION

print(strftime("%H:%M:%S", localtime())+" Inserting input and calculating trade")

# extract list of compartments with input
cursor.execute("SELECT DISTINCT comp FROM input")
inputlist = cursor.fetchall()
inputlist = [item for sublist in inputlist for item in sublist]

# define order in which export should be calculated
comporder = ['Recycled Material Production',
             'Primary Production',
             'Transport',
             'Fibre Production',
             'Non-Textile Manufacturing',
             'Textile Manufacturing',
             'Packaging (sector)',
             'Automotive (sector)',
             'Electrical and Electronic Equipment (sector)',
             'Clothing (sector)',
             'Household Textiles (sector)',
             'Technical Textiles (sector)']

# loop over compartments
for compname in comporder:
    
    # check if in model still
    if not complog[compname]:
        print("--> "+compname+ " skipped")
        continue
    
    print("--> "+compname)
    
    # get name reference
    ind = [k for k, e in enumerate([t[1] for t in complist]) if e == compname]
    compfull = complist[ind[0]][0]
    comp = CompartmentDict[compfull]

    # check if any input data is negative
    cursor.execute("SELECT value FROM input WHERE comp='"+compname+"' AND mat='"+mat+"'")        
    data = cursor.fetchall()
    data = [item for sublist in data for item in sublist]
    
    if all(x >= 0 for x in data):
        
        # implement input into model as is
        model.addInflow(cp.ExternalListInflow(comp, [cp.FixedValueInflow(d) for d in data]))  
    
    # if some input values are negative, need to do the export calculation
    else:
        
        # import data from database for compartment compname and material mat
        cursor.execute("SELECT * FROM input WHERE comp='"+compname+"' AND mat='"+mat+"'")        
        data = cursor.fetchall()
        
        # one entry per year (combining multiple years into one entry)
        expcomp = []
        
        for i in periodRange+startYear:
            
            # find corresponding entries
            temp = [t[2] for t in data]
            ind = [k for k, e in enumerate(temp) if e == i]
            
            expcomp.append([data[k] for k in ind])
        
        # copy model into new one for intermediate TC calculation
        tempmodel = model
        
        # insert all other inflows, either as is or if negative replace by zero
        for othercomp in inputlist:
            
            # skip if compartment was cleaned out before (everything zero)
            if not othercomp in CompartmentDict:
                continue
            
            # get name reference
            ind = [k for k, e in enumerate([t[1] for t in complist]) if e == othercomp]
            othercompfull = complist[ind[0]][0]
    
            # check if inflow already in model, if yes, skip
            if othercomp in [t.target for t in model.inflows]:
                continue
            
            # load input data for other comp
            cursor.execute("SELECT * FROM input WHERE comp='"+othercomp+"' AND mat='"+mat+"'")        
            datacomp = cursor.fetchall()
            
            # one entry per year (averaging multiple years into one entry)
            values = []
            for i in periodRange+startYear:
                # find corresponding entries
                ind = [k for k, e in enumerate([t[2] for t in datacomp]) if e == i]
                values.append(np.mean([datacomp[k][4] for k in ind]))
            
            # if negative, set to zero
            values = [0 if d < 0 else d for d in values]
            
            # implement into tempmodel
            tempmodel.addInflow(cp.ExternalListInflow(CompartmentDict[othercompfull], [cp.FixedValueInflow(d) for d in values]))
            
        
        # perform dpmfa
        simulator = sc.Simulator(1, len(periodRange), 2250, True, True) # 2250 is just a seed
        simulator.setModel(tempmodel)
        simulator.runSimulation()
        
        # get mass in comp
        mass = simulator.getLoggedTotalOutflows()
        masscomp = mass[compname]
        
        TClist = []
        
        # calculate transfer factor
        for i in periodRange:
            
            if masscomp[0][i] == 0:
                TC = 0
                TClist.append(TC)
            
            else: 
                # first case: only one datapoint in database
                if len(expcomp[i]) == 1:
                                           
                    TC = -expcomp[i][0][4]/masscomp[0][i]
                    TClist.append(TC)
                    
                    if TC < 0:
                        continue
                    if abs(TC) > 1:
                        TC = 1
                        print("WARNING: The export flow from "+compname+" should have been "+str(round(-expcomp[i][0][4]/masscomp[0][i],3))+" (higher than 1) but was replaced by 1 (year "+str(i+startYear)+", comp="+str(round(masscomp[0][i]*1000,3))+", export="+str(round(-expcomp[i][0][4]*1000,3))+").")
                    
                    # implement into database
                    format_str = """INSERT INTO transfercoefficients (comp1, comp2, year, mat, value, priority, dqisgeo, dqistemp, dqismat, dqistech, dqisrel, source)
                    VALUES ("{c1}", "{c2}", "{y}", "{mt}", "{val}", "{prio}", "{DQ1}", "{DQ2}", "{DQ3}", "{DQ4}", "{DQ5}", "{src}");"""
                    
                    sql_command = format_str.format(c1 = compname,
                                                    c2 = "Export",
                                                    y = i+startYear,
                                                    mt = mat,
                                                    val = TC,
                                                    prio = 3,
                                                    DQ1 = expcomp[i][0][5],
                                                    DQ2 = expcomp[i][0][6],
                                                    DQ3 = expcomp[i][0][7], 
                                                    DQ4 = expcomp[i][0][8],
                                                    DQ5 = expcomp[i][0][9],
                                                    src = expcomp[i][0][10])
                    
                    cursor.execute(sql_command)
                
                
                # otherwise: if two datapoints in database
                else:
                    
                    TC = [-expcomp[i][0][4]/masscomp[0][i],-expcomp[i][1][4]/masscomp[0][i]]
                    TClist.append(np.mean(TC))
                    
                    if any(TC < 0):
                        if any(TC > 0):
                            raise Exception("Error 2 in Export calculation")
                        else:
                            continue
                    if any(abs(TC) > 1):
                        raise Exception("Error 3 in Export calculation")
                    
                    # implement into database
                    format_str = """INSERT INTO transfercoefficients (comp1, comp2, year, mat, value, priority, dqisgeo, dqistemp, dqismat, dqistech, dqisrel, source)
                    VALUES ("{c1}", "{c2}", "{y}", "{mt}", "{val}", "{prio}", "{DQ1}", "{DQ2}", "{DQ3}", "{DQ4}", "{DQ5}", "{src}");"""
                    
                    sql_command = format_str.format(c1 = compname,
                                                    c2 = "Export",
                                                    y = i+startYear,
                                                    mt = mat,
                                                    val = TC[0],
                                                    prio = 3,
                                                    DQ1 = expcomp[i][0][5],
                                                    DQ2 = expcomp[i][0][6],
                                                    DQ3 = expcomp[i][0][7], 
                                                    DQ4 = expcomp[i][0][8],
                                                    DQ5 = expcomp[i][0][9],
                                                    src = expcomp[i][0][10])
                    
                    cursor.execute(sql_command)
                    
                    format_str = """INSERT INTO transfercoefficients (comp1, comp2, year, mat, value, priority, dqisgeo, dqistemp, dqismat, dqistech, dqisrel, source)
                    VALUES ("{c1}", "{c2}", "{y}", "{mt}", "{val}", "{prio}", "{DQ1}", "{DQ2}", "{DQ3}", "{DQ4}", "{DQ5}", "{src}");"""
                    
                    sql_command = format_str.format(c1 = compname,
                                                    c2 = "Export",
                                                    y = i+startYear,
                                                    mt = mat,
                                                    val = TC[1],
                                                    prio = 3,
                                                    DQ1 = expcomp[i][1][5],
                                                    DQ2 = expcomp[i][1][6],
                                                    DQ3 = expcomp[i][1][7], 
                                                    DQ4 = expcomp[i][1][8],
                                                    DQ5 = expcomp[i][1][9],
                                                    src = expcomp[i][1][10])
                    
                    cursor.execute(sql_command)
        
        # replace negative entries of net import by zero
        cursor.execute("UPDATE input SET value = 0 WHERE (comp = '"+compname+"' AND value < 0 AND mat = '"+mat+"');")
        
        # add export flow into model
        CompartmentDict[compfull].transfers.append(cp.TimeDependentDistributionTransfer([cp.TransferConstant(t) for t in TClist],
                       CompartmentDict["Export"],
                       priority = 3))
        
        # add inflow into model
        data = []
        for i in expcomp:
            if len(i) == 1:
                poi = i[0][4]
            else:
                poi = np.mean([t[4] for t in i])
            if poi < 0:
                data.append(0)
            else:
                data.append(i[0][4]) 
        
        model.addInflow(cp.ExternalListInflow(comp, [cp.FixedValueInflow(d) for d in data]))


### FINAL CORRECTION FOR EXPORT FLOWS

# for every export TC calculated, fill up the database with "0" for the years where no export takes place

# get a list of all compartments with an export flow
cursor.execute("SELECT DISTINCT comp1 FROM transfercoefficients WHERE comp2='Export' AND mat='"+mat+"'")        
expcomps = cursor.fetchall()
expcomps = [item for sublist in expcomps for item in sublist]

for comp in expcomps:
    
    cursor.execute("SELECT DISTINCT year FROM transfercoefficients WHERE comp1='"+comp+"' AND comp2='Export' AND mat='"+mat+"'")        
    data = cursor.fetchall()
    data = [item for sublist in data for item in sublist]
    
    # if there is data for each year, skip
    if all(elem in data for elem in np.arange(startYear,endYear+1)):
        continue
    
    for i in np.arange(startYear,endYear+1):
        
        # check if data in database
        cursor.execute("SELECT * FROM transfercoefficients WHERE comp1='"+comp+"' AND comp2='Export' AND mat='"+mat+"' AND year="+str(i))        
        data = cursor.fetchall()
        
        if len(data) != 0:
            continue
        
        else:
            
            # get priority from remaining data
            cursor.execute("SELECT DISTINCT priority FROM transfercoefficients WHERE comp1='"+comp+"' AND comp2='Export' AND mat='"+mat+"'")        
            prio = cursor.fetchall()
            
            # insert zeroes into database
            format_str = """INSERT INTO transfercoefficients (comp1, comp2, year, mat, value, priority, dqisgeo, dqistemp, dqismat, dqistech, dqisrel, source)
            VALUES ("{c1}", "{c2}", "{y}", "{mt}", "{val}", "{prio}", "{DQ1}", "{DQ2}", "{DQ3}", "{DQ4}", "{DQ5}", "{src}");"""
            
            sql_command = format_str.format(c1 = comp,
                                            c2 = "Export",
                                            y = i,
                                            mt = mat,
                                            val = 0,
                                            prio = prio[0][0],
                                            DQ1 = 0,
                                            DQ2 = 0,
                                            DQ3 = 0, 
                                            DQ4 = 0,
                                            DQ5 = 0,
                                            src = "Export calculation")
            
            cursor.execute(sql_command)

# commit changes
connection.commit()
  
# close connection
connection.close()

