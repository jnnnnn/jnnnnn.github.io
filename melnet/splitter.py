# Splitter.py: split up a stoptimes.txt file to remove irrelevant data.
# Filters by route to eliminate routes that are not active on a certain day
# Also filters to remove stop times outside a certain time-of-day window
# Also splits the file into hourly chunks
# Can also run zlib over the output (the result of which is within 20% of optimal compression)
# License: public domain or CC0 (your choice)
# Original Author: Jonathan Newnham

import os, csv, datetime, zlib

window_start = datetime.datetime(2017, 5, 29, 5, 0) # 8 May, 5am
window_end = datetime.datetime(2017, 5, 29, 23, 0) # 8 May, 11pm

#window_start = datetime.datetime.now() - datetime.timedelta(0, 60 * 60 * 2)
#window_end = datetime.datetime.now() + datetime.timedelta(0, 60 * 60 * 2)


# compress the output file (not used yet)
def compressfile(fname):
	f = open(fname, 'rb')
	fout = open(fname + '.deflate', 'wb')
	compressor = zlib.compressobj()
	for line in f:
		bits = compressor.compress(line)
		fout.write(bits)
	fout.write(compressor.flush())
	f.close()
	fout.close()

for args, dirname, files in os.walk('gtfs-melbourne'):
	if 'stop_times.txt' in files:
		print("Processing", args)
		services_rows = csv.DictReader(open(os.path.join(args, 'calendar.txt'), 'r', encoding='utf-8-sig'))
		services = { row['service_id'] : row for row in services_rows } # service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date	
		for service_id in services:
			service = services[service_id]
			service['start_date'] = datetime.datetime.strptime(service['start_date'], '%Y%m%d')
			service['end_date'] = datetime.datetime.strptime(service['end_date'], '%Y%m%d')

		trips_rows = csv.DictReader(open(os.path.join(args, 'trips.txt'), 'r', encoding='utf-8-sig'))
		trips = { row['trip_id'] : row for row in trips_rows } # route_id,service_id,trip_id,shape_id,trip_headsign,direction_id
		
		# trip_id,arrival_time,departure_time,stop_id,stop_sequence,stop_headsign,pickup_type,drop_off_type,shape_dist_traveled
		with open(os.path.join(args, 'stop_times.txt'), 'r', encoding='utf-8-sig') as f:
			fread = csv.DictReader(f)		
			
			fnout = os.path.join(args, 'stop_times-filtered.txt')
			with open(fnout, 'w', encoding='utf-8') as fout:

				foutwrite = csv.DictWriter(fout, fread.fieldnames, quoting=csv.QUOTE_ALL, lineterminator='\n')
				foutwrite.writeheader()

				outfiles = {hour : {} for hour in range(5, 23)}
				for hour, dic in outfiles.items():
					dic['fname'] = os.path.join(args, 'stop_times_{hour}.txt').format(hour=hour)
					dic['file'] = open(dic['fname'], 'w', encoding='utf-8')
					dic['writer'] = csv.DictWriter(dic['file'], fread.fieldnames, quoting=csv.QUOTE_ALL, lineterminator='\n')
					dic['writer'].writeheader()

				prevstoptime = None
				prevtrip = None
				for row in fread: 
					try:
						trip = trips[row['trip_id']]
						service = services[trip['service_id']]
						if window_end < service['start_date'] or window_start > service['end_date']:
							continue
						if service[window_start.strftime('%A').lower()] != "1":
							continue
						stoptime = datetime.datetime.strptime(row['departure_time'], '%H:%M:%S').time()								
						if stoptime < window_start.time() or stoptime > window_end.time():
							continue				

						# detect teleporting vehicles and fudge the stop times so they don't jump
						if stoptime == prevstoptime and row['trip_id'] == prevtrip:
							#print("teleportation!", args, row)
							offset += 1					
							row['departure_time'] = stoptime.replace(second=60 - 60//offset).strftime('%H:%M:%S')
						else:
							offset = 1
						prevstoptime = stoptime				
						prevtrip = row['trip_id']

						foutwrite.writerow(row)
						if stoptime.hour in outfiles:
							outfiles[stoptime.hour]['writer'].writerow(row)
						if stoptime.minute > 55 and stoptime.hour+1 in outfiles:
							outfiles[stoptime.hour+1]['writer'].writerow(row)
						if stoptime.minute < 5 and stoptime.hour-1 in outfiles:
							outfiles[stoptime.hour-1]['writer'].writerow(row)
					except Exception as e:
						#print(e)
						pass

			compressfile(fnout)
			for hour, dic in outfiles.items():
				dic['file'].close()
				compressfile(dic['fname'])

