"""A python script to plot optimal trade routes in Elite:Dangerous.
Uses data from Slopey's BPC.
Author: Jonathan Newnham
License: Public Domain
"""

import sqlite3
from collections import defaultdict
import os, sys, pprint

import logging
logging.basicConfig(format='%(asctime)s  %(message)s')
logger = logging.getLogger('eliteroute')
logger.setLevel("INFO")

MAX_SINGLE_ROUTE_DISTANCE = 23
MINIMUM_SINGLE_ROUTE_PROFIT = 300 # can make everything much more efficient
NUM_ROUTES = 300 # show the most profitable routes only

status_file = sys.stdout
outfile_path = "results.txt"
outfile = open(outfile_path, 'w')
PPrinter = pprint.PrettyPrinter(width=120, stream=outfile)

logger.info("Opening sqlite db..")
connection = sqlite3.connect("C:\Program Files (x86)\Slopey's ED BPC\ED.db")
logger.info("Opened.")

allsystems = set()

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

logger.info("Flattening dictionary..")
all_trade_routes = [ (source, 
					  destination, 
					  sdp[source][destination][1], # commodity
					  sdp[source][destination][0], # profit
					  distances[source][destination]) 
                    for source in sdp
                    for destination in sdp[source]
                    ]

# include empty routes? (increases complexity significantly)
if True:
	for source in allsystems:
		for destination in allsystems:
			if destination not in sdp[source]:
				sdp[source][destination] = 0, "nothing"

logger.info("Sorting by profitability..")
all_trade_routes.sort(key=lambda row: -row[3]) # puts most profitable trip first

def streq(str1, str2):
	return str1.upper() == str2.upper()

print("\n\n", file=outfile)
if len(sys.argv) > 2:
	source = sys.argv[1]
	destination = sys.argv[2]
	print ("Possible trades from {} to {}: ".format(source, destination), file=outfile)
	PPrinter.pprint([route for route in all_trade_routes 
		if route[0] == source and route[1] == destination][:NUM_ROUTES])
	print ("Best trades between {} and {} via a third system: ".format(sys.argv[1], sys.argv[2]), file=outfile)
	all_double_jumps = []
	for intermediate_system in allsystems:
		if source in sdp and intermediate_system in sdp[source] and intermediate_system in sdp and destination in sdp[intermediate_system]:
			avgprofit = (sdp[source][intermediate_system][0] + sdp[intermediate_system][destination][0])/2
			all_double_jumps.append((avgprofit,
				"{:.0f} avg. profit via {} ({} + {} Ly) -- carry {} and {}".format(
					avgprofit,
					intermediate_system,
					distances[source][intermediate_system],
					distances[intermediate_system][destination],
					sdp[source][intermediate_system][1],
					sdp[intermediate_system][destination][1]
				)))
	all_double_jumps.sort(reverse=True)
	for avgprofit, description in all_double_jumps[:NUM_ROUTES]:
		print (description, file=outfile)

elif len(sys.argv) > 1:
	print("Best destinations when starting from " + sys.argv[1] + ":", file=outfile)
	PPrinter.pprint([route for route in all_trade_routes if streq(route[0], sys.argv[1])][:NUM_ROUTES])

	print("Best sources when travelling to " + sys.argv[1] + ":", file=outfile)	
	PPrinter.pprint([route for route in all_trade_routes if streq(route[1], sys.argv[1])][:NUM_ROUTES])
else:
	print("Best routes: ", file=outfile)
	PPrinter.pprint(all_trade_routes[:NUM_ROUTES])

	with open(os.path.expandvars("best-route-data.tsv"), 'w') as outdata:
		outdata.write("Start\tMove\tEnd\tDistance\tWeight\tDescription\n")
		for source, destination, commodity, profit, distance in all_trade_routes[:NUM_ROUTES]:
			outdata.write("\t".join([
				source, 
				commodity,
				destination, 
				"%f"%distance,
				"%d"%profit,			
				"{}, {:.0f} Ly".format(commodity, distance)]))
			outdata.write("\n")

print("Results written to " + outfile_path, file=status_file)



# open outfile in the default text editor, console window is a bit shit
os.startfile(outfile_path)