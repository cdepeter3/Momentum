# -*- coding: utf-8 -*-
"""
Created on Mon Nov 25 21:45:27 2019

@author: conno
"""

# http://kazuar.github.io/scraping-tutorial/
# https://medium.com/@raiyanquaium/how-to-web-scrape-using-beautiful-soup-in-python-without-running-into-http-error-403-554875e5abed

from urllib.request import Request, urlopen
import requests
import time
from bs4 import BeautifulSoup
import lxml.html as lh
import pandas as pd
import numpy as np
from tqdm import tqdm
from datetime import date

### Connect to website, initialize things ###
urlBase = 'https://finviz.com/screener.ashx?v=152&ft=2&o=ticker&c=0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47,48,49,50,51,52,53,54,55,56,57,58,59,60,61,62,63,64,65,66,67,68,69,70'

req = Request(urlBase , headers={'User-Agent': 'Mozilla/5.0'})
webpage = urlopen(req).read()
soup = BeautifulSoup(webpage, "html.parser")

one_a_tag = soup.findAll('a')[36]
link = one_a_tag['href']

lastPage = int(soup.findAll('a')[-3].contents[0])

colNames = []
rows_list = []
i=0

### Data Scraping ###
tic = time.time()
for pageNum in tqdm(range(1, lastPage)): # range(1, lastPage) gets all data, range(1, _smallNumber_) for testing
    if pageNum==1:
        url = urlBase
        page = requests.get(url , headers={'User-Agent': 'Mozilla/5.0'})
        doc = lh.fromstring(page.content)
        tr_elements = doc.xpath('//tr')
        
        for t in tr_elements[28]:
            i+=1
            name=t.text_content()
            colNames.append(name)
        results = pd.DataFrame(index = [0], columns=colNames)
    else:
        time.sleep(0.3)
        num = (pageNum-1)*20 + 1
        url = urlBase + "&r=" + str(num)
        
        page = requests.get(url , headers={'User-Agent': 'Mozilla/5.0'})
        doc = lh.fromstring(page.content)
        tr_elements = doc.xpath('//tr')
    i=0
        
    for j in range(29,len(tr_elements)):
        dict1 = {}
        T=tr_elements[j]
        if len(T) != 71: # this is the number of columns being scraped
            break
        i=0
        colCount = 0
        for t in T.iterchildren():
            data=t.text_content()
            dict1[results.columns[colCount]] = data
            if i>0:
                try:
                    data=int(data)
                except:
                    pass
            i+=1
            colCount += 1
        rows_list.append(dict1)
results = pd.DataFrame(rows_list)
results = results[colNames]

toc = time.time()
print(toc - tic)


### Data Crunching ### 

# Fix Data Format
results['Date'] = date.today()
results.iloc[:, 67] = results.iloc[:, 67].str.replace(',', '').astype(float) # Commas in Number
results.iloc[:, 70] = pd.to_datetime(results.iloc[:, 70]) # Date
results["Earnings Time"] = results.iloc[:, 68].str[-1:] # 'a' for earnings after closing bell, 'b' for before opening bell
results.iloc[:, 68] = pd.to_datetime(results.iloc[:, 68].str[:-2], format="%b %d", errors='coerce') # Earnings date, excluding the /a or /b from prior line

for col in (7, 8, 9, 10, 11, 12, 13, 16, 31, 35, 36, 37, 38, 48, 49, 59, 62, 64, 65, 69): 
    results.iloc[:,col] = pd.to_numeric(results.iloc[:,col], errors='coerce') # format numbers

for col in (14, 15, 17, 18, 19, 20, 21, 22, 23, 26, 27, 28, 29, 30, 32, 33, 34, 39, 40, 41, 42, 43, 44, 45, 46, 47, 50, 51, 52, 53, 54, 55, 56, 57, 58, 60, 61, 66):
    results.iloc[:,col] = pd.to_numeric(results.iloc[:,col].str[:-1])/100 # format percentages

for col in (6, 24, 25, 63): # format numbers with letters (eg. 527K, 81.4M)
    results.iloc[:, col] = results.iloc[:,col].astype(str)
    for row in range(0, len(results)):
        if results.iloc[row, col][-1] == 'K':
            results.iloc[row, col] = pd.to_numeric(results.iloc[row, col][:-1])*1e3
        elif results.iloc[row, col][-1] == 'M':
            results.iloc[row, col] = pd.to_numeric(results.iloc[row, col][:-1])*1e6
        elif results.iloc[row, col][-1] == 'B':
            results.iloc[row, col] = pd.to_numeric(results.iloc[row, col][:-1])*1e9
        else:
            results.iloc[row, col] = pd.to_numeric(results.iloc[row, col][:-1])

#  Output this day's data to the csv
results.to_csv('C:/Users/conno/Desktop/Misc/Investment Data/finvizData.csv', mode='a', index=False, header=False)


### Momentum Calculations ###

totalInv = 6000
numberOfStocks = 20
invPerStock = totalInv / numberOfStocks

# Find price change over past 12 months excluding most recent month
results['TTM_sansLast'] = results['Perf Year'] / (1 + results['Perf Month'])
results['MktCap'] = results['Price'] * results['Outstanding'] # Market Cap

# as proxy for value, sum percentile of P/S and P/B within the industy (can't compare those metrics between industries). Lowest rank = most 'value' stock
results['ValueRank'] = results.groupby(['Sector'])['P/S'].rank(pct=True) + results.groupby(['Sector'])['P/B'].rank(pct=True) 

## Filters
results = results.loc[results['Avg Volume'] > 5e4] # Volume Constraint
results = results.loc[(results['Price'] > 10) & (results['Price'] < invPerStock)] # Price Constraint
results = results.loc[results['MktCap'] > 3e8] # Market Cap Constraint
results = results.loc[results['Country'] == 'USA'] # Country Constraint (avoid issues with taxes, different standards for financial statements, etc)

results = results.sort_values('TTM_sansLast', ascending=False)

# Get top decile of momentum, then sort by value and pick top 20 stocks
topDecile = results.iloc[0:int(round(len(results))/10), :]
topDecile = topDecile.sort_values('ValueRank')

chosenTickers = topDecile.iloc[:numberOfStocks, 1] # tickers of top 20
top20 = topDecile.iloc[:numberOfStocks, :] # all data for top 20

## Calculate Optimal Position Size/Share Count
chosenPrices = topDecile.iloc[:numberOfStocks, -5]
numShares = np.floor(invPerStock / chosenPrices)
dollarsAllocated = numShares * chosenPrices

# get as close to equal allocation while buying integer number of shares
while (totalInv - dollarsAllocated.sum() > min(chosenPrices)): # while still under total investment constraint:
    tempMaxMin = []
    
    # for each stock, determine how close allocation would be to equal if one more share of that stock were bought
    for i in range(0, numberOfStocks):
        addShares = pd.DataFrame(np.zeros((len(numShares), 1)))#.reindex_like(numShares).iloc[:, 0]
        addShares['IndCol'] = numShares.index
        addShares = addShares.set_index('IndCol', drop=True)
        addShares.iloc[i] += 1
        tempDolAlloc = (numShares.add(addShares.iloc[:,0])) * chosenPrices
        if tempDolAlloc.sum() > totalInv:
            tempMaxMin.append(1e12)
        else:
            tempMaxMin.append(max(tempDolAlloc) - min(tempDolAlloc)) # proxy for how far from equal allocation
    
    # add one share to the stock that would keep portfolio closest to equal allocation
    indToAdd = tempMaxMin.index(min(tempMaxMin))
    numShares.iloc[indToAdd, ] += 1
    dollarsAllocated = numShares * chosenPrices

# Random calcs
# stDev = np.std(dollarsAllocated)
# spread_max = (max(dollarsAllocated) - min(dollarsAllocated)) / max(dollarsAllocated)
# spread_min = (max(dollarsAllocated) - min(dollarsAllocated)) / min(dollarsAllocated)


# Export data
output = pd.concat([chosenTickers, chosenPrices, numShares, dollarsAllocated], axis=1)
output.columns = [date.today(), 'Share Price', 'Share Count', 'Dollars']
output.to_csv('C:/Users/conno/Desktop/Misc/momentumStratOutput.csv', mode='a', index=False)
top20.to_csv('C:/Users/conno/Desktop/Misc/allData.csv', mode='a', index=False)


