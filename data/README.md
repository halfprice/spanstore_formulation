File description
================

Cloud data center and index mapping
-----------------------------------
*region_index_mapping* file contains the mapping between cloud data centers and indexes that are used in the formulation.

Measurement data
----------------
The measurement data in *storage_latency_matrix_percentile* and *vm_latency_matrix_percentile* are gathered during June 2013.

The format of those two files is:
```
<Request sender data center index> <request receiver data center index> <type of measurement> <percentile> <latency in ms>
```

Cloud pricing
-------------
File *region_price_index* reflects the pricing at June 2013.

The format is:
```
<data center index> <put/100,000> <get/100,000> <storage/GB> <[i,j]networking/GB>
```
