# This is an example of how to use pset to run programs and collect counters
# 
# This script will collect samples of executions
#
# Each execution is comprised of two programs X and Y (here we use a synthetic program of varying RAM access demand)
# First X and Y are run separately to collect their baseline features,
# then they are run together to collect their features and slowdown when contended.
# The resulting data is output to a csv file
#
#
# The samples in this script are meant to characterize the slowdown of L3 spillage and memory contention (on octomore)



import sys
sys.path.append("../pset")
from pset import Program, ProgramSet
import numpy
import pandas as pd
import random
import os

possible_delays = [0,1,2,3,4,5,6,12,18,24,32,64]

# create a Program object for 9 instances of a ./rpd (reverse stride with delay) execution
def program(delay):
	arraySize = 700000	# 700,000 longs -> 5.6MB -> x7 instances makes 39.2MB
											# 39.2MB fits into L3 on octomore,
											# but two programs of 39.2MB will spill the L3 and contend for memory (14 total threads hitting RAM)

	#arraySize = 550000 # use 4.4MB per instance if using CAT
	
	stride = 8					# a stride of 8 *should* cause a different cache block to be accessed per data read
	
	reps = 999999999		# reps is set very high to ensure timeout will cut the program off at 20s to make consistent measurements 
	command = f"./rpd -with-outer-loop {arraySize} {stride} {reps} {delay}"
	# create 7 "threads" (instances) of the command
	return Program([command]*7, label = f"delay{delay}")

ps = ProgramSet(timeout='20s', cpus = range(18,36))

# attempt to divide cache evenly between threads in programset
# ps.setAutoCAT(True)

# provide perf event names to capture

# we want to capture the sum of the RAM data reads for all a program's threads
ps.addEvent("offcore_response.all_data_rd.llc_miss.local_dram", sum)

# capture the minimum runtime length of a program's threads
ps.addEvent("cycles", min)

# compute a derived event/feature from preexisting features
# here we compute a "demand" feature by dividing RAM data reads by cycles
ps.computeFeature("demand", lambda x,y:x/y, "offcore_response.all_data_rd.llc_miss.local_dram", "cycles")

# extract a feature from each of a program's threads' stdout
# provide a regular expression with groups surrounding the desired feature
# assign the feature names by providing keyword arguments
# here we extract a "progress" feature from the first group and a "total" feature from the second
ps.extractFeature(r"(\d+) out of (\d+) accesses completed", sum, progress=1, total=2)

data = pd.DataFrame()

scriptName, _ = os.path.splitext(os.path.basename(__file__))

# set directory to place all perf, stdout, and stderr outputs of samples
ps.dir = scriptName + "-data"


for _ in range(100):
		[delayX, delayY] = random.choices(possible_delays, k=2)
		[progX, progY] = [program(delayX), program(delayY)]

		# execute programs separately first
		print("running", progX)
		ps.setPrograms([progX])
		[baseX] = ps.run(f"X")

		print("running", progY)
		ps.setPrograms([progY])
		[baseY] = ps.run(f"Y")

		# then execute them at the same time
		print("running contended")
		ps.setPrograms([progX,progY])
		[contendedX, contendedY] = ps.run(f"XY")

		# measure slowdown based on the number of array accesses made
		slowdownX = baseX['progress'] / contendedX['progress']
		slowdownY = baseY['progress'] / contendedY['progress']

		# create dataframe row for this sample run
		row = dict()
		row['delayX'] = delayX
		for k,v in baseX.items(): # gather features from program X's baseline run
			row[k+'X'] = v

		row['delayY'] = delayY
		for k,v in baseY.items(): # gather features from program Y's baseline run
			row[k+'Y'] = v

		# gather features from the contended runs
		for k,v in contendedX.items():
			row[k+"X'"] = v
		for k,v in contendedY.items():
			row[k+"Y'"] = v

		row['slowdownX'] = slowdownX
		row['slowdownY'] = slowdownY


		# add record to the dataframe
		data = pd.concat([data, pd.DataFrame([row])], axis=0, ignore_index=True)

data.to_csv(scriptName + ".csv", index=False)
#data.to_csv(scriptName + "-withCAT.csv", index=False)
print(data)

