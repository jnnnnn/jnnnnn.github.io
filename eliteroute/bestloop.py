"""A python script to generate optimal trade route loops in Elite:Dangerous.
Uses data from Slopey's BPC.
Author: Jonathan Newnham
License: Public Domain

Further work:
This code doesn't do routing or unreachable system elimination, because it's
not really needed for the Type 6 and Type 9. You could do it easily enough by
starting with the complete distance graph, removing links that are too far,
then running graph_cycles.strongly_connected_components() over the graph to
return groups of systems that are all reachable from each other.
"""

import sqlite3
from collections import defaultdict
import os, sys, pprint, math
import graph_cycles # local file

import logging
logging.basicConfig(format='%(asctime)s  %(message)s')
logger = logging.getLogger('eliteroute')
logger.setLevel("INFO")

MAX_SINGLE_ROUTE_DISTANCE = 23
MINIMUM_SINGLE_ROUTE_PROFIT = 300 # can make everything much more efficient
MAX_LOOP_LENGTH = 6 # more than 5 can be veeeery slow
NUM_ROUTES = 20 # show the most profitable routes only

status_file = sys.stdout
outfile_path = "results-loop.txt"
outfile = open(outfile_path, 'w')
PPrinter = pprint.PrettyPrinter(width=300, stream=outfile)

logger.info("Opening sqlite db..")
connection = sqlite3.connect("C:\Program Files (x86)\Slopey's ED BPC\ED.db")
logger.info("Opened.")

def get_prices():
	cursor = connection.cursor()
	cursor.execute("""
	select scstationsystem, scstationcommod, scstationprice, scstationsell, scstationstock, scstationlastupdate
	from sc
	order by scstationcommod
	""")
	rows = cursor.fetchall()
	return rows

def get_distances():
	cursor = connection.cursor()
	cursor.execute("""
	select sysfrom, systo, distance
	from distances
	order by sysfrom
	""")
	rows = cursor.fetchall()
	distances = defaultdict(lambda: defaultdict(int))
	for system1, system2, distance in rows:
		distances[system1][system2] = distance
	return distances

logger.info("Loading distances..")
distances = get_distances()

logger.info("Loading prices..")
allsystems = set()
places_to_buy = defaultdict(list) # commodity -> system, buyprice
places_to_sell = defaultdict(list) # commodity -> system, sellprice
for system, commodity, buyprice, sellprice, quantity_available, lastupdate in get_prices():
	allsystems.add(system)
	if buyprice > 0:
		places_to_buy[commodity].append((system, buyprice))
	if sellprice > 0:
		places_to_sell[commodity].append((system, sellprice))

logger.info("Building dictionary of all possible trades..")
sdp = defaultdict(dict) # source system -> destination system -> (profit per unit, commodity)
for commodity in places_to_buy:
	for source, buyprice in places_to_buy[commodity]:
		for destination, sellprice in places_to_sell[commodity]:
			profit = sellprice - buyprice
			if profit < MINIMUM_SINGLE_ROUTE_PROFIT: continue
			if distances[source][destination] > MAX_SINGLE_ROUTE_DISTANCE: continue
			if destination not in sdp[source]:
				sdp[source][destination] = profit, commodity
			elif profit > sdp[source][destination][0]:
				sdp[source][destination] = profit, commodity

# PPrinter.pprint(sdp)

# include empty routes? (increases complexity significantly)
if False:
	for source in allsystems:
		for destination in allsystems:
			if destination not in sdp[source]:
				sdp[source][destination] = 0, "nothing"

graph = { source : list(sdp[source].keys()) for source in allsystems }

alltraderoutes = []
for length in range(2, MAX_LOOP_LENGTH+1):
	logger.info("Finding all {}-step cycles..".format(length))	
	for cycle in graph_cycles.cycles(graph, cycle_length=length):
		profit = 0
		distance = 0
		commodities = []
		for i in range(len(cycle)):
			source = cycle[i]
			destination = cycle[(i+1) % len(cycle)]			
			assert(source in sdp)
			assert(destination in sdp[source])
			profit += sdp[source][destination][0]
			commodities.append(sdp[source][destination][1])
			distance += distances[source][destination]
		
		# if statement saves memory -- often can't store all possible routes in memory at once..	
		if len(alltraderoutes) < NUM_ROUTES or math.floor(profit / len(cycle)) > alltraderoutes[NUM_ROUTES - 1][0]:
			alltraderoutes.append((
				math.floor(profit / len(cycle)),
				math.ceil(distance / len(cycle)),
				cycle,
				commodities))
			alltraderoutes.sort(reverse=True) # most profitable first

print("Best cyles, ordered by profit / jump : ", file=outfile)
PPrinter.pprint(alltraderoutes[:NUM_ROUTES])

# write out the routes for display with the state diagram explorer
with open(os.path.expandvars("best-loop-data.tsv"), 'w') as outdata:
		outdata.write("Start\tMove\tEnd\tDistance\tWeight\tDescription\n")
		for avgprofit, avgdistance, systems, commodities in sorted(alltraderoutes[:NUM_ROUTES]):
			for i in range(len(systems)):		
				source = systems[i]
				destination = systems[(i+1)%len(systems)]
				distance = math.ceil(distances[source][destination])
				profit = sdp[source][destination][0]	
				outdata.write("\t".join([
					source,
					commodities[i], 
					destination,
					str(distance),
					str(profit),
					"Profit: {}/unit ({:d} Ly)".format(profit, distance)
					]))
				outdata.write("\n")

logger.info("Done.")

# open outfile in the default text editor, console window is a bit shit
os.startfile(outfile_path)
