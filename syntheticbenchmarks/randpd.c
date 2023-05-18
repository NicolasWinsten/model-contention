/**
Author: Nicolas Winsten, nicolasd.winsten@gmail.com

This is a synthetic program for executing random array access.

Usage: ./a.out [-no-init] <array size> <number of accesses> <delay-size>

delay-size corresponds to the number of junk computations made between each array access

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

int doInit = 1; // set to true if array should be initialized

// counter to track number of accesses made
volatile unsigned long long progress = 0;

// total number of expected accesses (including stores) set in main()
unsigned long long completion = 0;

// junk variable used in delay loop computation
// it is global here to get around O2 optimizations 
long long junk = 0;

void report(int signum) {
  printf("\n%llu out of %llu accesses completed\n", progress, completion);
  if (signum != 0) exit(1);
}


// return number of flags given in argv
int handleOpts(int argc, char **args) {
  if (argc == 0 || args[0][0] != '-') return 0;
  else if (strcmp(args[0], "-no-init") == 0) doInit = 0;
  else { 
    fprintf(stderr, "unrecognized opt: %s\n", args[0]);
    exit(1);
  }
  return 1 + handleOpts(argc - 1, args + 1);
}

int main(int argc, char **argv) {
  struct timeval startTime, stopTime;
	double elapsed;
        
	signal(SIGTERM, report);
	signal(SIGINT, report);
	
	int numFlags = handleOpts(argc - 1, argv + 1);
  unsigned long long arraySize = strtoull(argv[numFlags+1], NULL, 10);
  unsigned long long accesses = strtoull(argv[numFlags+2], NULL, 10);
	int delay = atoi(argv[numFlags+3]);

  int hwthread = sched_getcpu();
        
  printf("doInit: %d\n", doInit);
	printf("arraySize: %llu, accesses: %llu, delay: %d\n", arraySize, accesses, delay);

  // volatile // possibly need volatile if compiler optimizations can figure
	// out the array is filled with 1
  long *a = (long *)
	  mmap(NULL, sizeof(long) * arraySize, PROT_WRITE | PROT_READ,
		MAP_PRIVATE | MAP_ANONYMOUS | MAP_HUGETLB, -1, 0);
 
	unsigned long long i, l;
	//volatile long long junk;
	// completion = total number of array accesses (including stores)
	completion = arraySize + accesses;

	printf("filling...\n");fflush(stdout);


	if (doInit)
  for (i = 0; i < arraySize; i++, progress++)
    a[i] = 1;

	printf("accessing..."); fflush(stdout);

  gettimeofday(&startTime, NULL);
    for (i = 0; i < accesses; i++) {
      progress = progress + a[rand() % arraySize];
			for (l = 0; l < delay; l++) {
				junk = junk + (i - l);
	    } // delay loop 
	  }
	gettimeofday(&stopTime, NULL);
	
	printf("done\n"); fflush(stdout);
	report(0);

  elapsed = ((stopTime.tv_sec - startTime.tv_sec) + (stopTime.tv_usec-startTime.tv_usec)/1000000.0);
  printf("hwthread %d took %f seconds\n", hwthread, elapsed);
  return 0;  
}

