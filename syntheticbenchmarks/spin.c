/*
Author: Nicolas Winsten, nicolasd.winsten@gmail.com

This is a synthetic program executing a dummy spinloop

Usage: ./a.out <number of loops>

**/

#define _GNU_SOURCE

#include <stdio.h>
#include <stdlib.h>
#include <sys/time.h>
#include <limits.h>
#include <string.h>
#include <sched.h>

volatile unsigned long long num;

int main(int argc, char **argv) {
  struct timeval startTime, stopTime;
  double elapsed;

  num = strtoull(argv[1], NULL, 10);

  int hwthread = sched_getcpu();
	printf("starting spin on hwthread %d\n", hwthread);
	gettimeofday(&startTime, NULL);
	for (; num > 0; num--);
	gettimeofday(&stopTime, NULL);
	elapsed = ((stopTime.tv_sec - startTime.tv_sec) + (stopTime.tv_usec-startTime.tv_usec)/1000000.0);
  printf("spin on hwthread %d took %f seconds\n", hwthread, elapsed);

  return 0;        
}

