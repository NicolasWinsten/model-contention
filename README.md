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
