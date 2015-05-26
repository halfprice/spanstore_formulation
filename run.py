import commands
import sys

def main():
    e = commands.getstatusoutput('python src/strong_consistency_formulation_generator.py data/storage_latency_matrix_percentile data/vm_latency_matrix_percentile data/region_price_index test/workload_big_test 1000 500 50 2')
    if e[0] != 0:
        print e[1]

if __name__ == '__main__':
    main()
