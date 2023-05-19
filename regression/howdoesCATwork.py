
import sys
sys.path.append("../pset")
from pset import Program, ProgramSet
import numpy
import random
import pandas as pd
import os

# create program object whose working set resides in L3
def work_program():
	arraySize = 1250000		# 1.25M longs -> 10MB which fits into L3 on octomore (45MiB)
	stride = 8						# large enough stride to ensure cache misses on each array access
	reps = 99999999				# exorbitant number of repetitions to ensure the timeout normalizes all runtimes
	delay = 0
	command = f"./rpd -with-outer-loop {arraySize} {stride} {reps} {delay}"
	return Program([command], label="work")


# create a program object for a spinloop
def spin_program():
	num_loops = 999999999
	return Program([f"./spin {num_loops}"], label="spin")

ps = ProgramSet(timeout = '5s', cpus = [18,19])

# provide perf events to capture
l3_miss_event = "offcore_response.all_data_rd.llc_miss.local_dram"
ps.addEvent(l3_miss_event, sum)

scriptName, _ = os.path.splitext(os.path.basename(__file__))
ps.dir = scriptName + "-data"

data = pd.DataFrame()

# execute the program with successively larger portions of the bitmask
# also run a spinloop beside the working program that is assigned the leftover bits
for cat_mask_bits in range(1,20):
		cat_mask1 = int('1'*cat_mask_bits,2)
		cat_mask2 = cat_mask1 ^ 0xfffff
		print("CAT_MASKS", hex(cat_mask1), hex(cat_mask2))

		# define Class of Services with capacity bit masks
		# here we define COS1 and COS2
		os.system(f"pqos -e 'llc:1={cat_mask1};llc:2={cat_mask2}'")

		# assign the COS to cpus
		# here we assign COS1 to hwthread 18 and COS2 to hwthread 19
		os.system(f"pqos -a 'llc:1=18;llc:2=19'")

		# run them together for contended features
		print("running contended")
		ps.setPrograms([work_program(), spin_program()])
		[stat, spinstat] = ps.run(f"XY")
		
		row = {
			'CAT_bits_allocated': cat_mask_bits,
			'llc_misses': stat[l3_miss_event],
			'neighbor_type': 'spin',
			'neighbor_llc_misses': spinstat[l3_miss_event]
		}

		data = pd.concat([data, pd.DataFrame([row])], axis=0, ignore_index=True)

# execute the program with successively larger portions of the bitmask
# also run a second l3 workload beside the working program that is assigned the leftover bits
for cat_mask_bits in range(1,20):
		cat_mask1 = int('1'*cat_mask_bits,2)
		cat_mask2 = cat_mask1 ^ 0xfffff
		print("CAT_MASKS", hex(cat_mask1), hex(cat_mask2))

		# define Class of Services with capacity bit masks
		# here we define COS1 and COS2
		os.system(f"pqos -e 'llc:1={cat_mask1};llc:2={cat_mask2}'")

		# assign the COS to cpus
		# here we assign COS1 to hwthread 18 and COS2 to hwthread 19
		os.system(f"pqos -a 'llc:1=18;llc:2=19'")

		# run them together for contended features
		print("running contended")
		ps.setPrograms([work_program(), work_program()])
		[stat, neighborstat] = ps.run(f"XY")
		
		row = {
			'CAT_bits_allocated': cat_mask_bits,
			'llc_misses': stat[l3_miss_event],
			'neighbor_type': 'l3',
			'neighbor_llc_misses': neighborstat[l3_miss_event], 
		}

		data = pd.concat([data, pd.DataFrame([row])], axis=0, ignore_index=True)


os.system("pqos -R")

# redo the experiment without a "counter-balance" thread
for cat_mask_bits in range(1,20):
		cat_mask = int('1'*cat_mask_bits,2)
		os.system(f"pqos -e 'llc:1={cat_mask}'")

		ps.setPrograms([work_program()])
		[stat] = ps.run("X")

		row = {
			'CAT_bits_allocated': cat_mask_bits,
			'llc_misses': stat[l3_miss_event],
			'neighbor_type': 'none',
			'neighbor_llc_misses': None
		}
	
		data = pd.concat([data, pd.DataFrame([row])], axis=0, ignore_index=True)


	
data.to_csv(scriptName + ".csv", index=False)
print(data)

os.system("pqos -R")

