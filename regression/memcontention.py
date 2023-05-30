# This is an example of using pset to collect program runtime characteristics
#
# This script will collect data for program pairs that contend on the memory bus


import sys
sys.path.append("/home/winsten1/pset")
from pset import Program, ProgramSet
import numpy
import random
import pandas as pd
import os

# create program object for an out-of-cache program that constantly hits RAM
def program(instances, delay):
	arraySize = 99999999	# large array size, ensure it is out of cache
	stride = 15						# large enough stride to ensure cache misses on each array access
	reps = 9999999				# exorbitant number of repetitions to ensure the timeout normalizes all runtimes
	command = f"./rpd -with-outer-loop {arraySize} {stride} {reps} {delay}"
	return Program([command]*instances, label = f"d{delay}i{instances}")

ps = ProgramSet(timeout='20s', cpus = range(18,36))

# provide perf events to capture
ps.addEvent("offcore_response.all_data_rd.llc_miss.local_dram", sum)
ps.addEvent("cycles", min)

# extract a feature from each thread's stdout (in this case the array access counter)
ps.extractFeature(r"(\d+) out of \d+ accesses completed", sum, progress=1)

# define a derived feature
ps.computeFeature("demand", lambda x,y: x/y, "offcore_response.all_data_rd.llc_miss.local_dram", "cycles")

scriptName, _ = os.path.splitext(os.path.basename(__file__))
ps.dir = scriptName + "-data"

data = pd.DataFrame()
delays = [0,1,2,3,4,5,6,7,8,9,12,15,18,24,32,64]
instances = [1,2,3,4,5,6,7,8,9]

for _ in range(100):
		[delayX, delayY] = random.choices(delays, k=2)
		[instancesX, instancesY] = random.choices(instances, k=2)

                # creating multiple instances to simulate threads
                # when go to actual multithreaded program, ideal would be if perf
                #    is able to collect all counters; then only one instance per program needed
		progX = program(instancesX, delayX)
		progY = program(instancesY, delayY)

		# collect baseline features for each program
		print("running", progX)
		ps.setPrograms([progX])
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
		row['instancesX'] = instancesX
		for k,v in baseX.items():
			row[k+'X'] = v

		row['delayY'] = delayY
		row['instancesY'] = instancesY
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

