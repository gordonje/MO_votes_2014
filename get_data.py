from os import path
import shutil
from datetime import datetime
import requests
from bs4 import BeautifulSoup
import json
import csv
import json

start_time = datetime.now()

# If there's a current xml file, rename it and put it in /data/archive
if path.exists('data/feed_data.xml'):
	time_str = str(start_time.date()) + "-" + str(start_time.hour) + str(start_time.minute) + str(start_time.second)
	shutil.copy2('data/feed_data.xml', 'data/archive/feed_data_' + time_str + '.xml')

county_fips = {}

with open('data/counties_FIPS.csv', 'rU') as f:
	reader = csv.DictReader(f, ['FIPS','FIPS_County_Name','Results_County_Name','Same'])

	for line in reader:
		county_fips[line['Results_County_Name']] = line['FIPS'] 

# request and parse the xml data
# Test AccessKey=004117454660
# Election Day AccessKey=482021566655 (DON'T FORGET TO CHANGE THIS!!!!!)
response = requests.get('http://enrarchives.sos.mo.gov/APFeed/Apfeed.asmx/GetElectionResults?AccessKey=482021566655')

soup = BeautifulSoup(response.content, 'xml')

# save the current version of the xml
with open('data/feed_data.xml', 'w') as f:
	f.write(str(soup))

# set a variable to store the results as we go
output = {
	    'last_updated': soup.find('ElectionResults')['LastUpdated']
	  , 'races': {}
}

for type_race in soup.findAll('TypeRace'):

	type_name = type_race.find('Type').text.strip()

	output['races'][type_name] = {}

	for race in type_race.findAll('Race'):
		# splitting the district names out of the race names
		if len(race.find('RaceTitle').text.split(' - ', 1)) > 1:
			race_name = race.find('RaceTitle').text.split(' - ', 1)[1].strip()
		else:
			race_name = race.find('RaceTitle').text.strip()

		output['races'][type_name][race_name] = {
									  'reporting_precincts': 0
									, 'total_precincts': 0
									, 'candidates': {}
									, 'county_results': {}
								}

		for county in race.findAll('Counties'):

			county_name = county.find('CountyName').text.strip()

			reporting_precincts = int(county.find('CountyResults').find('ReportingPrecincts').text.strip())
			total_precincts = int(county.find('CountyResults').find('TotalPrecincts').text.strip())

			# add counties to county results with fips as key
			output['races'][type_name][race_name]['county_results'][str(county_fips[county_name])] = {
																			  'county': county_name
																			, 'reporting_precincts': reporting_precincts
																			, 'total_precincts': total_precincts
																			, 'candidates': {}
																		}
						
			output['races'][type_name][race_name]['reporting_precincts'] += reporting_precincts
			output['races'][type_name][race_name]['total_precincts'] += total_precincts

			for candidate in county.find('CountyResults').findAll('Candidate'):

				candidate_id = candidate.find('CandidateID').text.strip()
				yes_votes = int(candidate.find('YesVotes').text.strip())

				# handling cases when there's no county votes tag
				if candidate.find('NoVotes') != None:
					no_votes = int(candidate.find('NoVotes').text.strip())
				else:
					no_votes = None

				# adding the candidate info to the race node
				if candidate_id not in output['races'][type_name][race_name]['candidates'].keys():
					output['races'][type_name][race_name]['candidates'][candidate_id] = {
															  'candidate_name': candidate.find('LastName').text.strip()
															, 'party': candidate.findParent('Party').find('PartyName').text.strip()
															, 'yes_votes': 0
															, 'no_votes': 0
														}

				output['races'][type_name][race_name]['county_results'][county_fips[county_name]]['candidates'][candidate_id] = {
																		    'yes_votes': yes_votes
																		  , 'no_votes': no_votes
																		}

				output['races'][type_name][race_name]['candidates'][candidate_id]['yes_votes'] += yes_votes
				if no_votes != None:
					output['races'][type_name][race_name]['candidates'][candidate_id]['no_votes'] += no_votes

# going back over the output to calculate percent precincts reported, total votes cast in each race and county
for race_type in output['races'].keys():

	for race in output['races'][race_type].keys():

		output['races'][race_type][race]['pct_precincts_reported'] = round( float(output['races'][race_type][race]['reporting_precincts']) / float(output['races'][race_type][race]['total_precincts']), 2 )
		output['races'][race_type][race]['total_votes'] = 0

		for candidate_id in output['races'][race_type][race]['candidates'].keys():
			output['races'][race_type][race]['total_votes'] += output['races'][race_type][race]['candidates'][candidate_id]['yes_votes']
			output['races'][race_type][race]['total_votes'] += output['races'][race_type][race]['candidates'][candidate_id]['no_votes']

		# if it's a race for which we're displaying results by county (e.g., the state auditor or the ballot initatives)...
		if race_type in ('State of Missouri', 'Ballot Issues'):
			# ...then for each county, if it's Jackson...
			for fips in output['races'][race_type][race]['county_results'].keys():
				if output['races'][race_type][race]['county_results'][fips]['county'] == 'Jackson':
					# ...then add KC's precincts reported and total precincts to Jackson County...
					output['races'][race_type][race]['county_results'][fips]['reporting_precincts'] += output['races'][race_type][race]['county_results']['999']['reporting_precincts']
					output['races'][race_type][race]['county_results'][fips]['total_precincts'] += output['races'][race_type][race]['county_results']['999']['total_precincts']
					# ... and for each candidate, add the yes and no votes to the same candidate under jackson county.
					for candidate_id in output['races'][race_type][race]['county_results'][fips]['candidates'].keys():
						output['races'][race_type][race]['county_results'][fips]['candidates'][candidate_id]['yes_votes'] += output['races'][race_type][race]['county_results']['999']['candidates'][candidate_id]['yes_votes']
						if output['races'][race_type][race]['county_results'][fips]['candidates'][candidate_id]['no_votes'] != None:
							output['races'][race_type][race]['county_results'][fips]['candidates'][candidate_id]['no_votes'] += output['races'][race_type][race]['county_results']['999']['candidates'][candidate_id]['no_votes']


# If there's a current json file, rename it and put it in /data/archive
if path.exists('data/election_data.json'):
	time_str = str(start_time.date()) + "-" + str(start_time.hour) + str(start_time.minute) + str(start_time.second)
	shutil.copy2('data/election_data.json', 'data/archive/election_data_' + time_str + '.json')

# output the json file
json_file = open('data/election_data.json', 'w')
json_file.write(json.dumps(output))
json_file.close()
