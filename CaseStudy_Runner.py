# -*- coding: utf-8 -*-
"""

Created on 09.04.2020
@author: dew
Test model for importing SQL databases

"""

import os
import csv
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

import setup_model_new as su
from dpmfa import simulator as sc
from dpmfa import components as cp


#import numpy.random as nr
#from scipy.stats import gaussian_kde 
#import pandas as pd


startYear = 1950 # year of start of modelling
Tperiods = 67 # total number of periods considered
Speriod = 30 # special period for detailed output printing
RUNS = 10000 # number of runs (numerical precision)

pathtoDB = os.path.join("data_casestudy","DPMFA_Plastic_EU_inclExport.db")
#mat = "PS"
#mat = "PP"
#mat = "EPS"
#mat = "PVC"
#mat = "HDPE"
#mat = "PET"
mat = "LDPE"

modelname = mat+" in Europe"
startYear = 1950
endYear = 2016
# for plots
xScale=np.arange(startYear,startYear+Tperiods)

# define model
model = su.setupModel(pathtoDB,modelname,RUNS,mat, startYear, endYear)

# check validity
#model.checkModelValidity()
#model.debugModel()


# set up the simulator object
simulator = sc.Simulator(RUNS, Tperiods, 2250, True, True) # 2250 is just a seed
# define what model  needs to be run
simulator.setModel(model)
# run the model
#simulator.debugSimulator()
simulator.runSimulation()


### plot inflow

# compartment with loggedInflows
loggedInflows = simulator.getLoggedInflows() 

# create pdf document with multiple pages
pp = PdfPages('output_casestudy/EU/TimeSeries_INFLOW_'+mat+'.pdf')
    
## display mean for each inflow
for key, value in loggedInflows.items():
    data = value*1000
        
    mean=[]                                       
    q25=[]
    q75=[]
    minimum=[]
    maximum=[]
    
    for i in range(0,np.shape(data)[1]):
        mean.append(np.mean(data[:,i]))
        q25.append(np.percentile(data[:,i],25))
        q75.append(np.percentile(data[:,i],75))
        minimum.append(np.min(data[:,i]))
        maximum.append(np.max(data[:,i]))
    
    # create a new figure
    fig = plt.figure('INFLOW_'+ key) 
    plt.xlabel('Year',fontsize=14)
    plt.ylabel('Flow mass (kt)',fontsize=14)
    plt.title('Inflow into '+key)
    plt.rcParams['font.size']=12 # tick's font
    plt.xlim(xmin=startYear-0.5, xmax=startYear+Tperiods-0.5)
    plt.fill_between(xScale, minimum, maximum, color='blanchedalmond', label="Range")
    plt.plot(xScale,mean, color = 'darkred', linewidth=2, label='Mean Value')
    plt.plot(xScale, q25, color = 'red', linestyle='dashed', linewidth=1.5, label = '25% Quantile')
    plt.plot(xScale, q75, color = 'red', linestyle='dashed', linewidth=1.5, label = '75% Quantile')
    plt.legend(loc='upper left', fontsize = 'small')
    plt.tight_layout()
    pp.savefig()
    # fig.savefig('output_casestudy/EU/TimeSeries_INFLOW_'+ key+'.pdf', bbox_inches='tight')

# close the multipage pdf object
pp.close()

### plot outflow

# compartment with loggedOutflows
loggedOutflows = simulator.getLoggedOutflows()

# create pdf document with multiple pages
pp = PdfPages('output_casestudy/EU/TimeSeries_OUTFLOW_'+mat+'.pdf')

for Comp in loggedOutflows:
    
    # in this case name is the key, value is the matrix(data), in this case .items is needed
    for comp, value in Comp.outflowRecord.items():
        
        data = value*1000
        
        mean=[]                                       
        q25=[]
        q75=[]
        minimum=[]
        maximum=[]
        
        for i in range(0,np.shape(data)[1]):
            mean.append(np.mean(data[:,i]))
            q25.append(np.percentile(data[:,i],25))
            q75.append(np.percentile(data[:,i],75))
            minimum.append(np.min(data[:,i]))
            maximum.append(np.max(data[:,i]))

        # create a new figure
        fig = plt.figure('OUTFLOW_'+ Comp.name +' to ' + comp) 
        plt.xlabel('Year',fontsize=14)
        plt.ylabel('Flow mass (kt)',fontsize=14)    
        plt.title('Flow from '+Comp.name+' to ' + comp)
        plt.rcParams['font.size']=12 # tick's font
        plt.xlim(xmin=startYear-0.5, xmax=startYear+Tperiods-0.5)
        plt.fill_between(xScale, minimum, maximum, color='blanchedalmond', label="Range")
        plt.plot(xScale,mean, color = 'darkred', linewidth=2, label='Mean Value')
        plt.plot(xScale, q25, color = 'red', linestyle='dashed', linewidth=1.5, label = '25% Quantile')
        plt.plot(xScale, q75, color = 'red', linestyle='dashed', linewidth=1.5, label = '75% Quantile')
        plt.legend(loc='upper left', fontsize = 'small')
        plt.tight_layout()
        pp.savefig()

# close the multipage pdf object
pp.close()


### plot stocks
stocks = simulator.getStocks()

# create pdf document with multiple pages
pp = PdfPages('output_casestudy/EU/TimeSeries_STOCK_'+mat+'.pdf')

for stock in stocks:

    data = stock.inventory*1000
    
    mean=[]                                       
    q25=[]
    q75=[]
    minimum=[]
    maximum=[]
    
    for i in range(0,np.shape(data)[1]):
        mean.append(np.mean(data[:,i]))
        q25.append(np.percentile(data[:,i],25))
        q75.append(np.percentile(data[:,i],75))
        minimum.append(np.min(data[:,i]))
        maximum.append(np.max(data[:,i]))
    
    # create a new figure
    fig = plt.figure('STOCK_'+ stock.name) 
    plt.xlabel('Year',fontsize=14)
    plt.ylabel('Flow mass (kt)',fontsize=14)
    plt.title('Mass in stock '+stock.name)
    plt.rcParams['font.size']=12 # tick's font
    plt.xlim(xmin=startYear-0.5, xmax=startYear+Tperiods-0.5)
    plt.fill_between(xScale, minimum, maximum, color='blanchedalmond', label="Range")
    plt.plot(xScale,mean, color = 'darkred', linewidth=2, label='Mean Value')
    plt.plot(xScale, q25, color = 'red', linestyle='dashed', linewidth=1.5, label = '25% Quantile')
    plt.plot(xScale, q75, color = 'red', linestyle='dashed', linewidth=1.5, label = '75% Quantile')
    plt.legend(loc='upper left', fontsize = 'small')
    plt.tight_layout()
    pp.savefig()

# close the multipage pdf object
pp.close()


### plot sinks
sinks = simulator.getSinks()

# create pdf document with multiple pages
pp = PdfPages('output_casestudy/EU/TimeSeries_SINK_'+mat+'.pdf')

for sink in sinks:

    if isinstance(sink,cp.Stock):
        continue
    
    data = sink.inventory*1000
    
    mean=[]                                       
    q25=[]
    q75=[]
    minimum=[]
    maximum=[]
    
    for i in range(0,np.shape(data)[1]):
        mean.append(np.mean(data[:,i]))
        q25.append(np.percentile(data[:,i],25))
        q75.append(np.percentile(data[:,i],75))
        minimum.append(np.min(data[:,i]))
        maximum.append(np.max(data[:,i]))
    
    # create a new figure
    fig = plt.figure('SINK_'+ sink.name) 
    plt.xlabel('Year',fontsize=14)
    plt.ylabel('Flow mass (kt)',fontsize=14)
    plt.title('Mass in sink '+sink.name)
    plt.rcParams['font.size']=12 # tick's font
    plt.xlim(xmin=startYear-0.5, xmax=startYear+Tperiods-0.5)
    plt.fill_between(xScale, minimum, maximum, color='blanchedalmond', label="Range")
    plt.plot(xScale,mean, color = 'darkred', linewidth=2, label='Mean Value')
    plt.plot(xScale, q25, color = 'red', linestyle='dashed', linewidth=1.5, label = '25% Quantile')
    plt.plot(xScale, q75, color = 'red', linestyle='dashed', linewidth=1.5, label = '75% Quantile')
    plt.legend(loc='upper left', fontsize = 'small')
    plt.tight_layout()
    pp.savefig()

# close the multipage pdf object
pp.close()


## display mean ± std for each outflow
print('-----------------------')
for Speriod in [66]:
    print('Logged Outflows period '+str(Speriod)+' (year: '+str(startYear+Speriod)+'):')
    print('')
    # loop over the list of compartments with loggedoutflows
    for Comp in loggedOutflows:
        print('Flows from ' + Comp.name +':' )
        # in this case name is the key, value is the matrix(data), in this case .items is needed
        for Target_name, value in Comp.outflowRecord.items():
            print(' --> ' + str(Target_name)+ ': Mean = '+str(round(np.mean(value[:,Speriod]*1000),0))+' ± '+str(round(np.std(value[:,Speriod]*1000),0))   )
        print('')
print('-----------------------')


### export data

# export outflows to csv
for Comp in loggedOutflows: # loggedOutflows is the compartment list of compartmensts with loggedoutflows
    for Target_name, value in Comp.outflowRecord.items(): # in this case name is the key, value is the matrix(data), in this case .items is needed     
        with open(os.path.join("output_casestudy","EU","csv","loggedOutflows_"+mat+"_" + Comp.name + "_to_" + Target_name + ".csv"), 'w') as RM :
            a = csv.writer(RM, delimiter=' ')
            data = np.asarray(value)
            a.writerows(data)

# export inflows to csv
for Comp in loggedInflows: # loggedOutflows is the compartment list of compartmensts with loggedoutflows
    with open(os.path.join("output_casestudy","EU","csv","loggedInflows_"+mat+"_" + Comp + ".csv"), 'w') as RM :
        a = csv.writer(RM, delimiter=' ')
        data = np.asarray(loggedInflows[Comp])
        a.writerows(data) 

# export sinks to csv
for sink in sinks:
    if isinstance(sink,cp.Stock):
        continue
    with open(os.path.join("output_casestudy","EU","csv","sinks_"+mat+"_" + sink.name + ".csv"), 'w') as RM :
        a = csv.writer(RM, delimiter=' ')
        data = np.asarray(sink.inventory)
        a.writerows(data)

# export stocks to csv
for stock in stocks:
    with open(os.path.join("output_casestudy","EU","csv","stocks_"+mat+"_" + stock.name + ".csv"), 'w') as RM :
        a = csv.writer(RM, delimiter=' ')
        data = np.asarray(stock.inventory)
        a.writerows(data)
