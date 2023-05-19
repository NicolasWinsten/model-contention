#!/bin/bash

# for octomore


NUM_HUGEPAGES=64
ISOLCPUS=18-35,54-71  # attempt to isolate the second socket from the scheduler
                      # because that's where I want to run experiments

sed --in-place=.orig 						\
	\-e "s/\(GRUB_CMDLINE_LINUX_DEFAULT\)/#\1/" 		\
	/etc/default/grub

echo -n "GRUB_CMDLINE_LINUX_DEFAULT=\"quiet splash " 		\
	>> /etc/default/grub

echo -n "isolcpus="$ISOLCPUS " "				\
	>> /etc/default/grub

echo -n "hugepagesz=1G hugepages="$NUM_HUGEPAGES " default_hugepagesz=1G "	\
	>> /etc/default/grub

echo    "intel_pstate=disable\"" >> /etc/default/grub

grub-mkconfig -o /boot/grub/grub.cfg

