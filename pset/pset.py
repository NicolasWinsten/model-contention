# Author: Nicolas Winsten, nicolasd.winsten@gmail.com
# Python: 3.10.6
#
# This module provides an interface for running apps together
# and collecting metrics from their execution
#
#

import sys
import os
import json
import argparse
import re
import itertools as it
import time
from typing import List, Callable, Iterable, Dict, Any
from dataclasses import dataclass
import subprocess


# read getconf to get the number of L3 cache ways
# Note: getconf -a | grep CACHE reports the correct cache sizes on octomore
def _get_l3_assoc():
	getconf = subprocess.Popen(['getconf', '-a'], stdout=subprocess.PIPE)
	grep = subprocess.Popen(['grep', 'LEVEL3_CACHE_ASSOC'], stdin=getconf.stdout, stdout=subprocess.PIPE)
	getconf.stdout.close()
	output = grep.communicate()[0].split()

	if len(output) == 2:
		return int(output[1])
	else:
		err("could not determine L3 cache associativity with getconf")
		err(f"failed to parse: {output}")
		exit(1)
		
L3_CACHE_WAYS = _get_l3_assoc()

# read the number of Class of Service definitions available
def _get_num_COS():
	pqos_info = subprocess.Popen(['pqos', '-d'], stdout=subprocess.PIPE)
	grep_l3 = subprocess.Popen(['grep', '-A2', 'L3 CAT'], stdin=pqos_info.stdout, stdout=subprocess.PIPE)
	grep_cos = subprocess.Popen(['grep', 'Num COS'], stdin=grep_l3.stdout, stdout=subprocess.PIPE)

	pqos_info.stdout.close()
	grep_l3.stdout.close()
	output = grep_cos.communicate()[0].split()

	if len(output) == 3:
		return int(output[2])
	else:
		err("could not determine number of Classes of Service through pqos")
		exit(1)

NUM_COS = _get_num_COS()

def err(*args, **kwargs):
	print(*args, file=sys.stderr, **kwargs)


# These classes are used to define the types of features extracted
# from each execution
@dataclass
class Feature:
	name : str
	combiner: Callable[List[Any], Any]

@dataclass
class PerfCounter(Feature):
	"""Extracted from perf output"""
	pass

@dataclass
class Computed(Feature):
	"""Feature computed from other features"""
	func: Callable	# function to compute this feature from other features of this program
	args: List[str]	# the names of the features to be used as arguments to the function

@dataclass
class Extracted(Feature):
	"""Feature extracted from a pattern in the stdout"""
	regex: str										# pattern to look for in a line of stdout
	group: int

def timestamp() -> int:
	return int(time.time_ns())

# create a Program using a command string, or a list of command strings (that will run concurrently)
@dataclass
class Program:
	def __init__(self, commands: str | Iterable[str], label: str):
		self.commands = [commands] if type(commands) == str else commands
		self.label = label
	
	def __repr__(self):
		return "%s(%r)" % (self.__class__, self.__dict__) 

# an Execution represents a single thread execution within a Program
@dataclass
class Execution:
	commandStr: str
	cpu: int
	stdout: str
	stderr: str
	perfout: str

# ProgramSet defines a list of apps to run concurrently and a set of features to extract from each execution
#
# Define the commands to run, the cpus to target, and the features to capture
#
# use the createScript() method to inspect the resulting script
class ProgramSet:
	def __init__(self, programs: List[Program] = [], cpus: Iterable[int] = [], dir: str = None, timeout: str = ""):
		self.timeout = timeout
		self.dir = dir if dir else f"nickwinsten-{timestamp()}"
		self.programs = programs
		self.features = []
		self.setCpus(cpus)
		self.autoAssignCAT = False  # flag, set to true if the cache should be divided equally among cores

	def __repr__(self):
		return "%s(%r)" % (self.__class__, self.__dict__)

	def feats(self):
		return list(map(lambda f: f.name, self.features))

	
  # set flag to false/true whether you want to automatically assign CAT masks in the created script
	def setAutoCAT(self, flag): self.autoAssignCAT = flag

	def setCpus(self, cpus: Iterable[int]):
		self.cpus = sorted([*set(cpus)])

	def setPrograms(self, progs: List[Program]):
		self.programs = progs

  # Add a perf event to capture from the programs
  # params:
  #   event - the name of the perf event
  #   combiner - function to combine the metric from several threads/executions
	def addEvent(self, event: str, combiner = sum):
		f = PerfCounter(event, combiner)
		if f not in self.features:
			self.features.insert(0, f)

  # define a feature that is computed from several other features
  #
  # example:
  #   ps.computeFeature("demand", lambda x,y:x/y, "LLC-misses", "cycles")
	def computeFeature(self, name: str, f, *events, combiner = sum):
		fs = list(map(lambda f: f.name, self.features))
		if not all(map(lambda e: e in fs, events)):
			err("events", *events, "not defined")
			exit(1)
		f = Computed(name, combiner, f, events)
		self.features.append(f)
 
	# extract values from pattern in stdout of programs
  # params:
  # pattern : regex string where groups define what to capture 
  # group_names : key,value pairs where key is the feature name
  #               and value is the group number
  #
  # example:
  #   ps.extractFeature("hwthread took (\d+) seconds", time=1)
  #
  # Note: the extracted features are assumed to be numbers
	def extractFeature(self, pattern, combiner = sum, **group_names):
		for name, group in group_names.items():
			self.features.append(Extracted(name, combiner, pattern, group))

	# assign cpu and output filenames to each program thread
	def createCommands(self, stamp) -> List[List[Execution]]:
		def take(x, lst):
			return [lst.pop(0) if lst else None for _ in range(x)]

		seen_labels = dict()
		execs = []
		cpus = self.cpus.copy()
		for p in self.programs:
			prefix = f"{self.dir}/{stamp}-{p.label}"
			x = seen_labels.get(p.label)
			if not x:
				seen_labels[p.label] = 1
			else:
				seen_labels[p.label] = x+1
				prefix += f"-x{x}"		# tag programs with the same label

			perf_events = [f.name for f in self.features if isinstance(f, PerfCounter)]
			timeout = f"timeout {self.timeout}" if self.timeout else ""
			cpus_to_use = take(len(p.commands), cpus)
		
      # for each execution, create its command string
			exec_group = []			
			for (i, cpu, comm) in zip(it.count(1), cpus_to_use, p.commands):
				taskset = f"taskset -c {cpu}" if cpu else (err("not enough cpus"), exit(1))
				sub_prefix = prefix + (f"-i{i}" if len(p.commands) > 1 else "")
				stdout = sub_prefix + ".out"
				stderr = sub_prefix + ".err"
				perfout = sub_prefix + ".perf"
				perf = f"perf stat -o {perfout} --no-big-num -e {','.join(perf_events)}" if perf_events else ""
				commandStr = f"{taskset} {perf} {timeout} {comm} >{stdout} 2>{stderr}".strip()
				exec_group.append(Execution(commandStr, cpu=cpu, stdout=stdout, stderr=stderr, perfout=perfout))
			execs.append(exec_group)
		return execs

	# write the script to execute this program set
	# return the filename of the script
	def createScript(self, stamp, execs = None) -> str:
		execs = self.createCommands(stamp) if not execs else execs
		script = open(f"{stamp}.sh", 'w')
		def line(content):
			script.write(content + '\n')

		cpus = [exec_.cpu for exec_group in execs for exec_ in exec_group]

		line("#!/bin/bash")

		# assign CAT masks to divide cache equally among cores
		def assignCAT(items):
			numItems = len(items)
			if numItems > NUM_COS - 1:
				err("(CAT error) not enough Classes of Service for the number of cores being used")
				exit(1)
			waysPerItem = L3_CACHE_WAYS // numItems
			def mkMask(i): return int('1'*waysPerItem + '0'*i*waysPerItem, 2)
			return [mkMask(i) for i in range(numItems)]
		
		# TODO give option to divide cache by core or by program
    # it is probably just better overall to manually set CAT classes
		if self.autoAssignCAT:
			for clazz, cpu, catMask in zip(it.count(1), cpus, assignCAT(cpus)):
				line(f"pqos -e 'llc:{clazz}={catMask}'")
				line(f"pqos -a 'llc:{clazz}={cpu}'")
		
		line("declare -a pids=()")

    # write out the commands
		line(''.join([f"{exe.commandStr} & pids+=($!)\n" for group in execs for exe in group]))
		# write the script barrier that waits for all commands to finish
		total_processes = sum(map(lambda exe: len(exe), execs))
		line(''.join(["wait ${pids[" + str(i) + "]}\n" for i in range(total_processes)]))

		# clean up cache allocations
		if self.autoAssignCAT: line("pqos -R")

		script.close()
		return script.name

	# write out the parameters of this program set
	def writeInfo(self, stamp):
		 info = open(f"{self.dir}/{stamp}.info", 'w')
		 info.write(self.__repr__())
		 info.close()

	# capture features from one execution's output
  # by accessing the output files produced
	def getFeatures(self, execution : Execution):
		stat = dict()
		for feature in self.features:
			match feature:
				case PerfCounter(name):
					pfile = open(execution.perfout, 'r')
					val = [line.split()[0] for line in pfile.readlines() if name in line.split()][0]
					pfile.close()
					stat[name] = int(re.sub(',', '', val))
				case Extracted(name, _, regex, group):
					ofile = open(execution.stdout, 'r')
					for line in ofile.readlines():
						m = re.search(regex, line)
						if m:
							stat[name] = float(m.group(group))
							break
					ofile.close()
				case Computed(name, _, f, args):
					stat[name] = f(*map(lambda a: stat[a], args))
		return stat

  # given one execution group (one 'program'),
  # collect each 'thread's features from its produced output files
  # combine the features into single program-level metrics
	def collectStats(self, execs : List[Execution]):
		stats = list(map(self.getFeatures, execs))
		return {feat.name : feat.combiner(map(lambda stat: stat[feat.name], stats)) for feat in self.features}
			

	# create a script for this program set
	# run it
	# return the collected metrics as a list of dictionaries
  # where item i is collected metrics for program i
	def run(self, stamp="nickwinsten"):
		path = os.getcwd() + "/" + self.dir
		if not os.path.exists(path):
			os.makedirs(path)
		execution_groups = self.createCommands(stamp)
		script = self.createScript(stamp, execution_groups)
		self.writeInfo(stamp)
		print(f"created script {script}")
		print("running...")
		os.system(f"chmod a+x {script}")
		exit_status = os.system(f"./{script}")
		print("exit status:", exit_status & 0xff)

		return list(map(self.collectStats, execution_groups))
	
		






