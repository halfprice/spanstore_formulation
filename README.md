SPANStore: Cost-Effective Geo-Replicated Storage Spanning Multiple Cloud Services
=================================================================================

This code contains a python implementation of the two SPANStore formulations.

See details about SPANStore in our [paper](http://zwu.me/papers/sosp13.pdf).

Licensing
---------
This code is released under the MIT License.

Requirements
------------
Python >= 2.6

CPLEX ILP solver >= 1.2 (The code is only tested using CPLEX 1.2)

Usage
-----
**1 . Generate ILP formulation**

Following command generates a ILP formulation file (formulation.lp) based on input files and arguments. *formulation.lp* is solvable by CPLEX solver.
```
python strong(eventual)_consistency_formulation_generator.py <storage latency matrix> <VM latency matrix> <cloud pricing matrix> <application workload file> <PUT SLO in ms> <GET SLO in ms> <which percentile latency to consider> <# of failures to tolerate>
```
with the meaning arguments
```
<storage latency matrix>: latency of storage request issued from one data center to another data center. See details in the data folder.

<VM latency matrix>: similar with <storage latency matrix>.

<cloud pricing matrix>: pricing policy of each cloud region. See details in the data folder.

<application workload file>: see details below.
```

The format of application workload file is as follows:
```
line 1: averagesize <average object size in kb>
line 2: overallsize <overall object size in kb>
line 3: time <how long does the objects are stored in storage in days>

After line 3 there are n lines with each line indicating the workload of one data center in the access set. N is the size of access set.
Each line is in the format:
  <data center index> <# of PUTs from clients> <# of GETs from clients>
```
See example workload files in *test folder*.

For example, to generate ILP formulation of strong consistency, you can run
```
python src/strong_consistency_formulation_generator.py data/storage_latency_matrix_percentile data/vm_latency_matrix_percentile data/region_price_index test/workload_test 1000 500 50 2
```

**2 . Solve ILP using CPLEX**

Solve the generated formulation using CPLEX solver.
```
ilpsolver formulation.lp result
```
CPLEX solver is not included in this repo.

**3 . Parse results**

You can parse the results by using the simple parser provided, or write your own parser.
```
python parse_result_strong.py result parsed_result
```

The parsed_result will list any variables that is set to 1 in the optimal solution.

Contact
-------
If you have any questions, please contact [Zhe Wu](http://zwu.me).
