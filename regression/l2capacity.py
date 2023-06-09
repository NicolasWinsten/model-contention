# This is an example of how to use pset to run programs and collect counters
#
# This script will collect samples of features from a program's execution,
# in this case a synthetic program making random array accesses (of varying array size)
#
# The samples can be used to experimentally determine the L2 cache size by
# pinpointing an array size that results in the most L2 hits
#
# At least on octomore, `getconf -a | grep CACHE` will report the correct cache sizes
#

import sys
sys.path.append("../pset")
from pset import Program, ProgramSet
import numpy
import pandas as pd


def program(arraysize):
    arrayAccesses = 200000000
    delay = 0
    command = f"./randpd {arraysize} {arrayAccesses} {delay}"
    return Program([command], label = f"size{arraysize}")

ps = ProgramSet(timeout='20s', cpus = range(18,36))

# provide perf event names to capture
ps.addEvent("l2_rqsts.demand_data_rd_hit", sum)
ps.addEvent("l2_rqsts.demand_data_rd_miss", sum)
ps.addEvent("l2_rqsts.l2_pf_hit", sum)
ps.addEvent("l2_rqsts.l2_pf_miss", sum)
ps.addEvent("offcore_response.all_data_rd.llc_miss.local_dram", sum)

data = pd.DataFrame()

for arraySize in [20000, 22000, 24000, 26000, 28000, 30000, 32000, 34000]:
    prog = program(arraySize)

    print("running", prog)
    ps.dir = f"l2-capacity-data"
    ps.setPrograms([prog])
    [results] = ps.run(f"X")

    row = {'arraysize': arraySize, **results}

    data = pd.concat([data, pd.DataFrame([row])], axis=0, ignore_index=True)

data.to_csv("l2-cap.csv", index=False)
print(data)
