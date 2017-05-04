import os, csv, datetime

window_start = datetime.datetime(2017, 5, 1, 10, 0) # 1 May, 10am
window_end = datetime.datetime(2017, 5, 1, 11, 0) # 1 May, 11am

for args, dirname, files in os.walk('gtfs'):    
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
		f = csv.DictReader(open(os.path.join(args, 'stop_times.txt'), 'r', encoding='utf-8-sig'))
		fout = csv.DictWriter(
			open(os.path.join(args, 'stop_times-filtered.txt'), 'w', encoding='utf-8-sig'), 
			f.fieldnames,
			quoting=csv.QUOTE_ALL,
			lineterminator='\n')
		fout.writeheader()
		prevstoptime = None
		prevtrip = None
		for row in f: 
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
					stoptime = stoptime.replace(second=30)
					row['departure_time'] = stoptime.strftime('%H:%M:%S')
					#print(row)
				prevstoptime = stoptime				
				prevtrip = row['trip_id']

				fout.writerow(row)
			except Exception as e:
				#print(e)
				pass