# This is an example of using pset to collect program runtime characteristics
#
# This script will collect data for program pairs that contend on L3


import sys
sys.path.append("../pset")
from pset import Program, ProgramSet
import numpy
import random
import pandas as pd
import os

# create program object for an out-of-cache program that constantly hits RAM
def program(delay):
	arraySize = 5000000		# 5M longs -> 40MB which fits into L3 on octomore (45MiB)
	stride = 8						# large enough stride to ensure cache misses on each array access
	reps = 9999999				# exorbitant number of repetitions to ensure the timeout normalizes all runtimes
	command = f"./rpd -with-outer-loop {arraySize} {stride} {reps} {delay}"
	return Program([command], label = f"d{delay}")

ps = ProgramSet(timeout='20s', cpus = range(18,36))

# provide perf events to capture
ps.addEvent("offcore_response.all_data_rd.llc_miss.local_dram", sum)
ps.addEvent("cycles", min)

# extract a feature from each thread's stdout (in this case the array access counter)
# progress=1 is setting the variable and passing name/value pair to extractFeature
ps.extractFeature(r"(\d+) out of \d+ accesses completed", sum, progress=1)

# define a derived feature
ps.computeFeature("demand", lambda x,y: x/y, "offcore_response.all_data_rd.llc_miss.local_dram", "cycles")

scriptName, _ = os.path.splitext(os.path.basename(__file__))
# name output directory --- use time of day if want to avoid collision
ps.dir = scriptName + "-data"

data = pd.DataFrame()
delays = [0,1,2,3,4,5,6,7,8,9,12,15,18,24,32,64]

for _ in range(100):
		[delayX, delayY] = random.choices(delays, k=2)

		progX = program(delayX)
		progY = program(delayY)

		# collect baseline features for each program
		print("running", progX)
		ps.setPrograms([progX])
                # X is the descriptive string for this run
		baseX = ps.run(f"X")[0]

		print("running", progY)
		ps.setPrograms([progY])
		baseY = ps.run(f"Y")[0]

		# run them together for contended features
		print("running contended")
		ps.setPrograms([progX,progY])
		[contendedX, contendedY] = ps.run(f"XY")
		
		slowdownX = baseX['progress'] / contendedX['progress']
		slowdownY = baseY['progress'] / contendedY['progress']

		row = {}
		row['delayX'] = delayX
		for k,v in baseX.items():
			row[k+'X'] = v

		row['delayY'] = delayY
		for k,v in baseY.items():
			row[k+'Y'] = v
		for k,v in contendedX.items():
			row[k+"X'"] = v
		for k,v in contendedY.items():
			row[k+"Y'"] = v
		row['slowdownX'] = slowdownX
		row['slowdownY'] = slowdownY


		data = pd.concat([data, pd.DataFrame([row])], axis=0, ignore_index=True)
		
data.to_csv(scriptName + ".csv", index=False)
print(data)

