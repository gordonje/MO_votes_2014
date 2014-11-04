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
	reader = csv.DictReader(f)
	
	for line in reader:
		county_fips[line['County_Name']] = {
										  'fips': str(line['FIPS'])
										, 'active_voters': int(line['Active_Voters'])
										, 'inactive_voters': int(line['Inactive_Voters'])
										, 'total_voters': int(line['Total_Voters'])
										}

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
			output['races'][type_name][race_name]['county_results'][county_fips[county_name]['fips']] = {
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

				output['races'][type_name][race_name]['county_results'][county_fips[county_name]['fips']]['candidates'][candidate_id] = {
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

			output['races'][race_type][race]['active_voters'] = 0

			for fips in output['races'][race_type][race]['county_results'].keys():
				# then for each county, we are going to add the voter numbers
				county_name = output['races'][race_type][race]['county_results'][fips]['county']

				output['races'][race_type][race]['county_results'][fips]['active_voters'] = county_fips[county_name]['active_voters']
				output['races'][race_type][race]['county_results'][fips]['inactive_voters'] = county_fips[county_name]['inactive_voters']
				output['races'][race_type][race]['county_results'][fips]['total_voters'] = county_fips[county_name]['total_voters']
				# and add up the total number of active voters
				output['races'][race_type][race]['active_voters'] += output['races'][race_type][race]['county_results'][fips]['active_voters']
				# also, if it is Jackson County...
				if output['races'][race_type][race]['county_results'][fips]['county'] == 'Jackson':
					# ...then add KC's precincts reported and total precincts to Jackson County...
					output['races'][race_type][race]['county_results'][fips]['reporting_precincts'] += output['races'][race_type][race]['county_results']['999']['reporting_precincts']
					output['races'][race_type][race]['county_results'][fips]['total_precincts'] += output['races'][race_type][race]['county_results']['999']['total_precincts']
					# ... and add the KC's active, inactive and total voters to Jackson County...
					output['races'][race_type][race]['county_results'][fips]['active_voters'] += county_fips['Kansas City']['active_voters']
					output['races'][race_type][race]['county_results'][fips]['inactive_voters'] += county_fips['Kansas City']['inactive_voters']
					output['races'][race_type][race]['county_results'][fips]['inactive_voters'] += county_fips['Kansas City']['total_voters']
					# ... and for each candidate, add the yes and no votes to the same candidate under jackson county.
					for candidate_id in output['races'][race_type][race]['county_results'][fips]['candidates'].keys():
						output['races'][race_type][race]['county_results'][fips]['candidates'][candidate_id]['yes_votes'] += output['races'][race_type][race]['county_results']['999']['candidates'][candidate_id]['yes_votes']
						if output['races'][race_type][race]['county_results'][fips]['candidates'][candidate_id]['no_votes'] != None:
							output['races'][race_type][race]['county_results'][fips]['candidates'][candidate_id]['no_votes'] += output['races'][race_type][race]['county_results']['999']['candidates'][candidate_id]['no_votes']


			for candidate_id in output['races'][race_type][race]['candidates'].keys():
				# add up the total number of votes casts in the race
				output['races'][race_type][race]['total_votes'] += output['races'][race_type][race]['candidates'][candidate_id]['yes_votes']
				output['races'][race_type][race]['total_votes'] += output['races'][race_type][race]['candidates'][candidate_id]['no_votes']
				
			# calculate the turnout in the race
			output['races'][race_type][race]['pct_turnout'] = round( float(output['races'][race_type][race]['total_votes']) / float(output['races'][race_type][race]['active_voters']), 2 )

# If there's a current json file, rename it and put it in /data/archive
if path.exists('data/election_data.json'):
	time_str = str(start_time.date()) + "-" + str(start_time.hour) + str(start_time.minute) + str(start_time.second)
	shutil.copy2('data/election_data.json', 'data/archive/election_data_' + time_str + '.json')

# output the json file
json_file = open('data/election_data.json', 'w')
json_file.write(json.dumps(output))
json_file.close()
