import sys

MAX_LATENCY = 1000000

# Only consider those possible relay path that can cause cost reduction.
# By only considering useful variables, this can reduce searching space.
def list_possible_P():

    for i in dependency:
        for j in datacenter_in_use:
            for k in datacenter_in_use:
                for m in datacenter_in_use:
                    if (network_price[i][k] > network_price[j][k] and network_price[i][m] > network_price[k][m]) and (network_price[j][m] > network_price[k][m] or j == k):
                        P_list['P_'+str(i)+'_'+str(j)+'_'+str(k)+'_'+str(m)] = 1

def list_possible_I():

    for i in dependency:
        for j in datacenter_in_use:
            for k in datacenter_in_use:
                if (network_price[i][k] > network_price[j][k] or i == j) and in_put_slo_3(i,j,k):
                    I_list['I_'+str(i)+'_'+str(j)+'_'+str(k)] = 1

# Read configuration files.
# Initialize program states.
def init():

    global datacenter_in_use
    datacenter_in_use = []
    for i in range(8):
        datacenter_in_use.append(i)
    for i in range(13, 19):
        datacenter_in_use.append(i)

    global datacenter_number
    global datacenter_number_max
    datacenter_number = len(datacenter_in_use)
    datacenter_number_max = 19

    global latency
    latency = {}
    for i in datacenter_in_use:
        latency[i] = {}
        for j in datacenter_in_use:
            latency[i][j] = {}
            latency[i][j]['PUT'] = {}
            latency[i][j]['GET'] = {}
            latency[i][j]['VM'] = {}
            for k in ['50', '80', '90', '99', '99.9']:
                latency[i][j]['PUT'][k] = MAX_LATENCY
                latency[i][j]['GET'][k] = MAX_LATENCY
                latency[i][j]['VM'][k] = MAX_LATENCY

    # Read storage latency matrix
    fin = open(sys.argv[1],'r')
    for line in fin:
        items = line.strip().split()
        if int(items[0]) < datacenter_number_max and int(items[1]) < datacenter_number_max:
            latency[int(items[0])][int(items[1])][items[2]][items[3]] = float(items[4])
    fin.close()

    # Read VM latency matrix
    fin = open(sys.argv[2],'r')
    for line in fin:
        items = line.strip().split()
        if int(items[0]) < datacenter_number_max and int(items[1]) < datacenter_number_max:
            latency[int(items[0])][int(items[1])][items[2]][items[3]] = float(items[4])
    fin.close()

    # We use this price multiplier to change the unit of cost
    # With this multiplier, CPLEX can find more accurate optimal solution
    # since it only guarantees optimal solution within 1e-6
    price_multiplier = 100000

    global get_price
    global put_price
    global store_price
    global network_price
    get_price = {}
    put_price = {}
    store_price = {}
    network_price = {}
    for i in range(datacenter_number_max):
        network_price = {}

    fin = open(sys.argv[3],'r')  #give it a price
    for line in fin:
        items = line.strip().split()
        if line.find('#') < 0 and int(items[0]) < datacenter_number_max:
            put_price[int(items[0])] = price_multiplier * float(items[1]) / 100000 #how much per 1 put
            get_price[int(items[0])] = price_multiplier * float(items[2]) / 100000 #how much per 1 get
            store_price[int(items[0])] = price_multiplier * float(items[3]) / 1024/1024/30 #how much per 1 KB per day
            network_price[int(items[0])] = {}
            for i in range(datacenter_number_max):
                network_price[int(items[0])][i] = price_multiplier * float(items[i+4]) / 1024/1024  #the price of transforming 1 KB data from items[0] to i
    fin.close()

    # Manually change network pricing of local
    for i in range(datacenter_number_max):
        if i in network_price:
            network_price[i][i] = 0 #no charge for networking in the same data center


    global dependency
    global object_size
    global overall_size
    global storing_time
    dependency = {}

    fin = open(sys.argv[4],'r')
    for line in fin:
        items = line.strip().split()
        if line.find('averagesize') > -1:
            object_size = float(items[1])
        elif line.find('overallsize') > -1:
            overall_size = float(items[1])
        elif line.find('time') > -1:
            storing_time = float(items[1])
        else:
            dependency[int(items[0])] = {}
            dependency[int(items[0])]['put_rate'] = int(items[1])
            dependency[int(items[0])]['get_rate'] = int(items[2])
    fin.close()


    global overall_put
    overall_put = 0
    for i in dependency:
        overall_put += dependency[i]['put_rate']

    global PUT_SLO
    global GET_SLO
    global percentile

    # Read SLO, in ms.
    PUT_SLO = int(sys.argv[5])
    GET_SLO = PUT_SLO  # in eventual consistency setting, PUT_SLO = GET_SLO

    # What percentile latency are we considering here.
    percentile = sys.argv[6]

    # How many data center failure we want to tolerate.
    global number_of_failure_to_tolerate
    number_of_failure_to_tolerate = int(sys.argv[7])


    # 3 hop and 4 hop relay can generate huge search space.
    # Here we elimite those relay paths that will never lead to cost reduction to reduce search space.
    global P_list
    P_list = {}
    list_possible_P()

    global I_list
    I_list = {}
    list_possible_I()


# Check if data center i's GET request to data center j is within GET SLO.
def in_get_slo(i,j):

    if latency[i][j]['GET'][percentile] <= GET_SLO:
        return True
    else:
        return False

# Check if data center i is able to directly PUT object to data center j within PUT SLO.
def in_put_slo(i,j):  # i sends data directly to j

    if latency[i][j]['PUT'][percentile] <= PUT_SLO:
        return True
    else:
        return False

# Check if data center i is able to indirectly PUT object to data center j through
# data center k within PUT SLO
# Note that cost optimal data transfer that is bounded by SLO will never use 4-hop relay.
def in_put_slo_3(i,j,k):
    if latency[i][j]['VM'][percentile] + latency[j][k]['PUT'][percentile] <= PUT_SLO:
        return True
    else:
        return False

# This function generates objective function.
# Line 18~24 in the formulation.
def output_objective_function():

    fout.write('MINIMIZE\n  COST :  ')

    need_operation = False

    # Cost for GETs
    for i in dependency:
        for j in datacenter_in_use:
            if in_put_slo(i,j) and in_get_slo(i,j):
                if need_operation:
                    fout.write(' + ')
                fout.write(' '+str((get_price[j] + network_price[j][i]*object_size)*dependency[i]['get_rate']) +' R_'+str(i)+'_'+str(j)+' \n')
                need_operation = True

    # Cost for PUT request
    for j in datacenter_in_use:
        if need_operation:
            fout.write(' + ')
        fout.write(' '+str(overall_put*put_price[j])+' C_'+str(j)+' \n')
        need_operation = True

    # Cost for PUT network
    for i in datacenter_in_use:
        for j  in datacenter_in_use:
            if i != j:
                if need_operation:
                    fout.write(' + ')
                fout.write(' '+str(object_size*network_price[i][j])+' F_'+str(i)+'_'+str(j)+' \n')

    # Storage cost
    for j in datacenter_in_use:
        if need_operation:
            fout.write(' + ')
        fout.write(' '+str(store_price[j]*overall_size*storing_time)+' C_'+str(j)+' \n')

    fout.write('\n')

# Every data center has f + 1 PUT/GET replicas that is constrained by SLO
# Corresponding to line 26~27 in the formulation.
def output_replica_number_contraint():

    for i in dependency:
        need_operation = False
        for j in datacenter_in_use:
            if in_get_slo(i,j) and in_put_slo(i,j):
                if need_operation:
                    fout.write(' + ')
                else:
                    fout.write(' R1_'+str(i)+' : ')
                    need_operation = True

                fout.write(' R_'+str(i)+'_'+str(j)+' ')
        if need_operation:
            fout.write(' = '+str(number_of_failure_to_tolerate + 1)+' \n')

# If data center j is used to hold replicas for data center i,
# data center j is used.
# This corresponds to line 28~29 in the formulation.
def output_choose_data_center():

    for j in datacenter_in_use:
        need_operation = False
        for i in dependency:
            if in_get_slo(i,j) and in_put_slo(i,j):
                if need_operation:
                    fout.write(' + ')
                else:
                    fout.write(' C1_'+str(j)+' : ')
                    need_operation = True

                fout.write(' R_'+str(i)+'_'+str(j)+' ')

        if need_operation:
            fout.write(' - C_'+str(j) +' >= 0 \n')


    for j in datacenter_in_use:
        need_operation = False
        for i in dependency:
            if in_get_slo(i,j) and in_put_slo(i,j):
                if need_operation:
                    fout.write(' + ')
                else:
                    fout.write(' C2_'+str(j)+' : ')
                    need_operation = True

                fout.write(' R_'+str(i)+'_'+str(j)+' ')

        if need_operation:
            fout.write(' - '+str(datacenter_number)+' C_'+str(j) +' <= 0 \n')

# If k is a replica in data center i's PUT/GET set, there has to be a sychronously forwarding path
# from i to k
# This corresponds to line 30~31 in the formulation.
def output_direct_forward_to_chosen_replica():

    for i in dependency:
        for k in datacenter_in_use:
            if in_put_slo(i,k) and in_get_slo(i,k):
                need_operation = False
                for j in datacenter_in_use:
                    if ('I_'+str(i)+'_'+str(j)+'_'+str(k) in I_list):
                        if need_operation:
                            fout.write(' + ')
                        else:
                            fout.write(' F1_'+str(i)+'_'+str(k)+' : ')
                            need_operation = True
                        fout.write(' I_'+str(i)+'_'+str(j)+'_'+str(k)+' \n')
                if need_operation:
                    fout.write(' - R_'+str(i)+'_'+str(k)+' = 0 \n')


# For every data center that holds an replica of the object, there has to be a path,
# either sychronous or asychronous path from the data center issuing the request to
# the data center that holds the replica.
# Corresponding to line 32~33 in the formulation.
def output_put_must_reach_everywhere():

    for i in dependency:
        for m in datacenter_in_use:
            need_operation = False
            for j in datacenter_in_use:
                if ('I_'+str(i)+'_'+str(j)+'_'+str(m) in I_list):
                    if need_operation:
                        fout.write(' + ')
                    else:
                        fout.write(' E1_'+str(i)+'_'+str(m)+' : ')
                        need_operation = True
                    fout.write(' I_'+str(i)+'_'+str(j)+'_'+str(m)+' \n')

            for j in datacenter_in_use:
                for k in datacenter_in_use:
                    if 'P_'+str(i)+'_'+str(j)+'_'+str(k)+'_'+str(m) in P_list:
                        if need_operation:
                            fout.write(' + ')
                        else:
                            fout.write(' E1_'+str(i)+'_'+str(m)+' : ')
                            need_operation = True
                        fout.write(' P_'+str(i)+'_'+str(j)+'_'+str(k)+'_'+str(m)+' \n')

            if need_operation:
                fout.write(' - C_'+str(m) + ' = 0 \n')



# This corresponds to line 34~36 in the formulation.
def output_path_constraints():

    global D_list
    D_list = {}

    # Line 35
    for i in dependency:
        for k in datacenter_in_use:
            for m in datacenter_in_use:
                if k != m and i != k:
                    need_operation = False
                    for j in datacenter_in_use:
                        if ('P_'+str(i)+'_'+str(j)+'_'+str(k)+'_'+str(m) in P_list):
                            if need_operation:
                                fout.write(' + ')
                            else:
                                fout.write(' D1_'+str(i)+'_'+str(k)+'_'+str(m)+' : ')
                                need_operation = True

                            fout.write(' P_'+str(i)+'_'+str(j)+'_'+str(k)+'_'+str(m)+' \n')
                        if ('P_'+str(i)+'_'+str(k)+'_'+str(m)+'_'+str(j) in P_list):
                            if need_operation:
                                fout.write(' + ')
                            else:
                                fout.write(' D1_'+str(i)+'_'+str(k)+'_'+str(m)+' : ')
                                need_operation = True
                            fout.write(' P_'+str(i)+'_'+str(k)+'_'+str(m)+'_'+str(j)+' \n')
                    if 'I_'+str(i)+'_'+str(k)+'_'+str(m) in I_list:
                        if need_operation:
                            fout.write(' + ')
                        else:
                            fout.write(' D1_'+str(i)+'_'+str(k)+'_'+str(m)+' : ')
                            need_operation = True
                        fout.write(' I_'+str(i)+'_'+str(k)+'_'+str(m)+' ')
                    if need_operation:
                        fout.write(' - D_'+str(i)+'_'+str(k)+'_'+str(m)+' >= 0 \n')
                        D_list['D_'+str(i)+'_'+str(k)+'_'+str(m)] = 1

    for i in dependency:
        for k in datacenter_in_use:
            for m in datacenter_in_use:
                if k != m and i != k:
                    need_operation = False
                    for j in datacenter_in_use:
                        if ('P_'+str(i)+'_'+str(j)+'_'+str(k)+'_'+str(m) in P_list):
                            if need_operation:
                                fout.write(' + ')
                            else:
                                fout.write(' D2_'+str(i)+'_'+str(k)+'_'+str(m)+' : ')
                                need_operation = True

                            fout.write(' P_'+str(i)+'_'+str(j)+'_'+str(k)+'_'+str(m)+' \n')
                        if ('P_'+str(i)+'_'+str(k)+'_'+str(m)+'_'+str(j) in P_list):
                            if need_operation:
                                fout.write(' + ')
                            else:
                                fout.write(' D2_'+str(i)+'_'+str(k)+'_'+str(m)+' : ')
                                need_operation = True
                            fout.write(' P_'+str(i)+'_'+str(k)+'_'+str(m)+'_'+str(j)+' \n')
                    if 'I_'+str(i)+'_'+str(k)+'_'+str(m) in I_list:
                        if need_operation:
                            fout.write(' + ')
                        else:
                            fout.write(' D2_'+str(i)+'_'+str(k)+'_'+str(m)+' : ')
                            need_operation = True
                        fout.write(' I_'+str(i)+'_'+str(k)+'_'+str(m)+' ')
                    if need_operation:
                        fout.write(' - '+str(3*(datacenter_number))+' D_'+str(i)+'_'+str(k)+'_'+str(m)+' <= 0 \n')
                        D_list['D_'+str(i)+'_'+str(k)+'_'+str(m)] = 1

    # Line 36
    for i in dependency:
        for k in datacenter_in_use:
            if i != k:
                need_operation = False
                for m in datacenter_in_use:
                    if 'I_'+str(i)+'_'+str(k)+'_'+str(m) in I_list:
                        if need_operation:
                            fout.write(' + ')
                        else:
                            fout.write(' D3_'+str(i)+'_'+str(k)+' : ')
                            need_operation = True
                        fout.write(' I_'+str(i)+'_'+str(k)+'_'+str(m)+' ')
                    for j in datacenter_in_use:
                        if 'P_'+str(i)+'_'+str(k)+'_'+str(m)+'_'+str(j) in P_list:
                            if need_operation:
                                fout.write(' + ')
                            else:
                                fout.write(' D3_'+str(i)+'_'+str(k)+' : ')
                                need_operation = True
                            fout.write(' P_'+str(i)+'_'+str(k)+'_'+str(m)+'_'+str(j)+' ')
                if 'I_'+str(i)+'_'+str(i)+'_'+str(k) in I_list:
                    if need_operation:
                        fout.write(' + ')
                    else:
                        fout.write(' D3_'+str(i)+'_'+str(k)+' : ')
                        need_operation = True
                    fout.write(' I_'+str(i)+'_'+str(i)+'_'+str(k)+' \n')
                if need_operation:
                    fout.write(' - D_'+str(i)+'_'+str(i)+'_'+str(k)+' >= 0\n')
                    D_list['D_'+str(i)+'_'+str(i)+'_'+str(k)] = 1

    for i in dependency:
        for k in datacenter_in_use:
            if i != k:
                need_operation = False
                for m in datacenter_in_use:
                    if 'I_'+str(i)+'_'+str(k)+'_'+str(m) in I_list:
                        if need_operation:
                            fout.write(' + ')
                        else:
                            fout.write(' D4_'+str(i)+'_'+str(k)+' : ')
                            need_operation = True
                        fout.write(' I_'+str(i)+'_'+str(k)+'_'+str(m)+' ')
                    for j in datacenter_in_use:
                        if 'P_'+str(i)+'_'+str(k)+'_'+str(m)+'_'+str(j) in P_list:
                            if need_operation:
                                fout.write(' + ')
                            else:
                                fout.write(' D4_'+str(i)+'_'+str(k)+' : ')
                                need_operation = True
                            fout.write(' P_'+str(i)+'_'+str(k)+'_'+str(m)+'_'+str(j)+' \n')
                if 'I_'+str(i)+'_'+str(i)+'_'+str(k) in I_list:
                    if need_operation:
                        fout.write(' + ')
                    else:
                        fout.write(' D4_'+str(i)+'_'+str(k)+' : ')
                        need_operation = True
                    fout.write(' I_'+str(i)+'_'+str(i)+'_'+str(k)+' \n')
                if need_operation:
                    fout.write(' - '+str(2*(datacenter_number))+' D_'+str(i)+'_'+str(i)+'_'+str(k)+' <= 0\n')      # N*N+N, N is the number of datacenter
                    D_list['D_'+str(i)+'_'+str(i)+'_'+str(k)] = 1


# This constraint helps simplify line 22.
# It uses F_ij to represent sigma(F_ijk) * PutRate_k
def output_forward_constraint_merge_forward():

    for i in datacenter_in_use:
        for j in datacenter_in_use:
            if i != j:
                need_operation = False
                for k in dependency:
                    if 'D_'+str(k)+'_'+str(i)+'_'+str(j) in D_list:
                        if need_operation:
                            fout.write(' + ')
                        else:
                            fout.write(' F3_'+str(i)+'_'+str(j)+' : ')
                            need_operation = True
                        fout.write(' '+str(dependency[k]['put_rate'])+' D_'+str(k)+'_'+str(i)+'_'+str(j)+' ')
                if need_operation:
                    fout.write(' - F_'+str(i)+'_'+str(j)+' = 0\n')


def output_constraints_function():

    fout.write('\nSUBJECT TO\n')

    output_replica_number_contraint()

    output_choose_data_center()

    output_direct_forward_to_chosen_replica()

    output_put_must_reach_everywhere()

    output_path_constraints()

    output_forward_constraint_merge_forward()

def output_general():

    fout.write('\nGENERAL\n')

    #output F, F is used to simplify line 22 in the formulation.
    # It stands for the number of objects that are sent through link (i,j), therefore, it is a general variable.
    for i in datacenter_in_use:
        for j in datacenter_in_use:
            if i != j:
                fout.write(' F_'+str(i)+'_'+str(j)+'\n')

def output_binary():

    fout.write('\nBINARY\n')

    #output R, which is R_ij in the formulation
    for i in dependency:
        for j in datacenter_in_use:
            if in_put_slo(i,j) and in_get_slo(i,j):
                fout.write(' R_'+str(i)+'_'+str(j)+' \n')

    #output C, which is C_i in the formulation
    for i in datacenter_in_use:
        fout.write(' C_'+str(i)+' \n')

    #output I, which is P_S_ijk in the formulation
    for i in dependency:
        for j in datacenter_in_use:
            for k in datacenter_in_use:
                if 'I_'+str(i)+'_'+str(j)+'_'+str(k) in I_list:
                    fout.write(' I_'+str(i)+'_'+str(j)+'_'+str(k)+' \n')

    #output P, which is P_A_ijkm in the formulation.
    for i in dependency:
        for j in datacenter_in_use:
            for k in datacenter_in_use:
                for m in datacenter_in_use:
                    if 'P_'+str(i)+'_'+str(j)+'_'+str(k)+'_'+str(m) in P_list:
                        fout.write(' P_'+str(i)+'_'+str(j)+'_'+str(k)+'_'+str(m)+'\n')

    #output D, which is F_ijk in the formulation.
    for i in dependency:
        for j in datacenter_in_use:
            for k in datacenter_in_use:
                if 'D_'+str(i)+'_'+str(j)+'_'+str(k) in D_list:
                    fout.write('D_'+str(i)+'_'+str(j)+'_'+str(k)+'\n')
	
	
def main():

    if len(sys.argv) != 8:
        print 'usage: python eventual_consistency_formulation_generator.py <storage latency matrix> <VM latency matrix> <cloud pricing matrix> <application workload file> <PUT/GET SLO in ms> <which percentile latency to consider> <# of failures to tolerate>'
        exit(1)

    init()

    global fout
    fout = open('formulation.lp','w')

    output_objective_function()

    output_constraints_function()

    output_general()

    output_binary()

    fout.write('\nEND\n')

    fout.close()

if __name__ == '__main__':
	main()
