/**
Author: Nicolas Winsten, nicolasd.winsten@gmail.com

This is a synthetic program for executing strided array accesses in reverse

Usage: ./a.out [] [] <array size> <stride> <repetitions> <delay-size>

stride:  number of elements to skip on each array access

repetitions: number of times to stride through the array

delay-size: number of junk computations to perform in between array accesses

*/


#define _GNU_SOURCE

#include <stdio.h>
#include <stdlib.h>
#include <sys/time.h>
#include <sys/types.h>
#include <unistd.h>
#include <string.h>
#include <sched.h>
#include <sys/mman.h>
#include <signal.h>

// flag, set to true if array elements should be initialized
int doInit = 1;

// flag, set to true if more loops should be added to normalize number of accesses with stride
// (essentially, repeats the workload `stride` times)
int doOuterLoop = 0;

volatile unsigned long long progress = 0;	// counter to track number of array accesses
unsigned long long completion = 0;				// total number of expected accesses (including stores) set in main()

// junk variable used in delay loop computation
// it is global here to get around O2 optimizations
long long junk = 0;

void report(int signum) {
  printf("\n%llu out of %llu accesses completed\n", progress, completion);
  //printf("%lld computation\n", junk);
  if (signum != 0) exit(1);
}


// return number of flags given in argv
int handleOpts(int argc, char **args) {
  if (argc == 0 || args[0][0] != '-') return 0;
  else if (strcmp(args[0], "-no-init") == 0) doInit = 0;
  else if (strcmp(args[0], "-with-outer-loop") == 0) { doOuterLoop = 1; }
  else { 
    fprintf(stderr, "unrecognized opt: %s\n", args[0]);
    exit(1);
  }
  return 1 + handleOpts(argc - 1, args + 1);
}

int main(int argc, char **argv) {
  struct timeval startTime, stopTime;
  double elapsed;
        
	// emit number of accesses completed if execution is stopped early
	signal(SIGTERM, report);
	signal(SIGINT, report);
	
	int numFlags = handleOpts(argc - 1, argv + 1);
  unsigned long long arraySize = strtoull(argv[numFlags+1], NULL, 10);
  int stride = atoi(argv[numFlags+2]);
  int reps = atoi(argv[numFlags+3]);
	int delay = atoi(argv[numFlags+4]);

  int hwthread = sched_getcpu();

	// compute the size of the working set of this program
	size_t elementSize = sizeof(long);
	size_t cacheLineSize = 64;	// assuming the cache block size is 64 bytes
	size_t workingSetSize;
	if (stride*elementSize > cacheLineSize)
		workingSetSize = cacheLineSize*arraySize/stride;
	else
		workingSetSize = arraySize*elementSize;	
  
	printf("doInit: %d, doOuterLoop: %d\n", doInit, doOuterLoop);
	printf("arraySize: %llu, stride: %d, reps: %d, delay: %d\n", arraySize, stride, reps, delay);
	//printf("%zuMB\n", arraySize*sizeof(long)/1000000);
	printf("%fMB\n", workingSetSize/1000000.0);

  /*volatile*/ long *a = (long *)
	  mmap(NULL, sizeof(long) * arraySize, PROT_WRITE | PROT_READ,
		MAP_PRIVATE | MAP_ANONYMOUS | MAP_HUGETLB, -1, 0);
 
	long long i, j, k, l, outloop;
  
	if (doOuterLoop) outloop = stride; else outloop = 1;
	// completion = total number of array accesses
	completion = (arraySize / stride) +  (reps * outloop * (arraySize / stride));

	printf("filling...\n");fflush(stdout);

	if (doInit)
  for (i = arraySize-stride; i >= 0; i-=stride, progress++)
    a[i] = 1;

	printf("accessing..."); fflush(stdout);
  gettimeofday(&startTime, NULL);
  for (k = 0; k < reps; k++) {
    for (j = 0; j < outloop; j++)
    for (i = arraySize-stride; i >= 0; i-=stride) {
      progress = progress + a[i];
			for (l = 0; l < delay; l++) {
				junk = junk + (i - j + k - l);
	    } // delay loop 
	  }
  }
	gettimeofday(&stopTime, NULL);
	printf("done\n"); fflush(stdout);
	report(0);

  elapsed = ((stopTime.tv_sec - startTime.tv_sec) + (stopTime.tv_usec-startTime.tv_usec)/1000000.0);
  printf("hwthread %d took %f seconds\n", hwthread, elapsed);
  return 0;  
}

