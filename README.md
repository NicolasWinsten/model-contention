# model-contention

## ancillary tools

### msr-safe
https://github.com/LLNL/msr-safe

variorium may not work without msr-safe because these tools require manipulating model specific registers

### variorium
https://github.com/LLNL/variorum

Building variorium will produce simple executables for disabling/enabling turbo.
This is important for gathering meaningful measurements by disallowing dynamic changes to core frequency.

### CAT
Cache allocation technology can be leveraged using the `pqos` command. This allows you to set degrees of isolation and capacity that an app has in the cache.

See regression/howdoesCATwork.py to see an example of it being used.


## setup
Note: you will need root access to make use of this repo
(this is just the steps I take)

### enabling hugepages
To enable hugepages, we make changes to the grub file:

```
# backup the grub file just in case...
cp /etc/default/grub grub.bak
# modify this script to change the number/size of hugepages
./set_hugepage_bootparams.sh
```

after a reboot, do the following to verify the changes:
```
awk '/HugePages_Total|Hugepagesize/ {print $0}' /proc/meminfo
```

### msr-safe
https://github.com/LLNL/msr-safe
(You will need to clone the repository outside of octomore -- on cztb2 for example -- and continue the setup on octomore)
```
# outside of octomore
git clone https://github.com/LLNL/msr-safe
# back on octomore
cd msr-safe
make
sudo insmod ./msr-safe.ko
```

For what we need out of variorium, we need to adjust the msr_allowlist.
```
# I go overkill and set all the bits on msr 1A0 because I don't know which exact bits are necessary
cat msr_allowlist1A0.bak > /dev/cpu/msr_allowlist
```

### variorium
https://github.com/LLNL/variorum

Like before, clone the repo outside of octomore. Then follow build instructions on octomore.
Once built, there will be an executable in the examples directory thatcan be used to enable/disable turbo.

### determining characteristics of the cache
at least on octomore, the following command will provide info on the cache hierarchy.
Together with `lscpu`, it should provide enough understanding:
```
getconf -a | grep CACHE
```

