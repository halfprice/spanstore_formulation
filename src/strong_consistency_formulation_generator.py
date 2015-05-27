import sys


MAX_LATENCY = 1000000


# Read configuration files and initialize all states
def init():
    global datacenter_number
    global datacenter_number_max

    global datacenter_in_use
    datacenter_in_use = []
    for i in range(8):
        datacenter_in_use.append(i)
    for i in range(13, 19):
        datacenter_in_use.append(i)
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

    # Read cloud pricing
    fin = open(sys.argv[3],'r')
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

    # Read application workload
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

    global PUT_SLO
    global GET_SLO
    global percentile

    # Read SLO, in ms.
    PUT_SLO = int(sys.argv[5])
    GET_SLO = int(sys.argv[6])

    # What percentile latency are we considering here.
    percentile = sys.argv[7]

    # How many data center failure we want to tolerate.
    global number_of_failure_to_tolerate
    number_of_failure_to_tolerate = int(sys.argv[8])


# Check if data center i's GET request to data center j is within GET SLO.
def in_get_slo(i,j):

    if latency[i][j]['GET'][percentile]<= GET_SLO:
        return True
    else:
        return False

# Check if data center i is able to directly PUT object to data center j within PUT SLO.
def in_put_slo_2(i,j):  # i sends data directly to j

    # Two operations are involved in this PUT request.
    # First, data center i needs to require lock in data center j
    # Second, data center i issue PUT request to data center j	
    if latency[i][j]['VM'][percentile] + latency[i][j]['PUT'][percentile] <= PUT_SLO:
        return True
    else:
        return False

# Check if data center i is able to indirectly PUT object to data center j through
# data center k within PUT SLO
def in_put_slo_3(i,j,k):  # i sends data to j through k

    # Operation is similar in in_put_slo_2, with only difference
    # that locking is directly required from i to j
    if latency[i][j]['VM'][percentile] + latency[i][k]['VM'][percentile] + latency[k][j]['PUT'][percentile] <= PUT_SLO: #lock directly required from the put data center, and there is propagaion from i to j
        return True
    else:
        return False

# This function generates objective function
# Line 12~18 in formulation.
def output_objective_function():

    fout.write('MINIMIZE\n  COST :  ')


    # Cost for GETs. Line 14 in the formulation.
    need_operation = False
    for j in dependency:
        if dependency[j]['get_rate'] > 0:
            for i in datacenter_in_use:
                if in_get_slo(j,i):
                    if need_operation:
                        fout.write(' + ')

                    fout.write(' '+str(dependency[j]['get_rate'] * get_price[i])+'  G_'+str(i)+'_'+str(j)+' ')
                    fout.write(' + '+str(dependency[j]['get_rate'] * network_price[i][j] * object_size)+'  G_'+str(i)+'_'+str(j)+' ')
                    fout.write('\n')
                    need_operation = True

    # Cost for PUTs. Line 16 in the formulation.
    has_m = {}
    for i in datacenter_in_use:
        has_m[i] = {}
        for j in datacenter_in_use:
            has_m[i][j] = False

    for j in dependency:
        if dependency[j]['put_rate'] > 0:
            for i in datacenter_in_use:
                for k in datacenter_in_use:
                    if in_put_slo_3(j,i,k) and (j == k or network_price[j][i] > network_price[k][i] ):
                        if need_operation:
                            fout.write(' + ')

                        if not has_m[j][k]:
                            fout.write(' '+str(dependency[j]['put_rate'] * network_price[j][k] * object_size)+'  R_'+str(j)+'_'+str(k)+' + ')
                            has_m[j][k] = True
                        fout.write(' '+str(dependency[j]['put_rate'] * put_price[i])+'  F_'+str(j)+'_'+str(i)+'_'+str(k)+' ')
                        fout.write(' + '+str(dependency[j]['put_rate'] * network_price[k][i] * object_size)+'  F_'+str(j)+'_'+str(i)+'_'+str(k)+' ')
                        fout.write('\n')
                        need_operation = True

    # Storage cost. Line 18 in the formulation.
    for i in datacenter_in_use:
        if need_operation:
            fout.write(' + ')
        fout.write(' '+ str(store_price[i]*overall_size*storing_time)+' C_'+str(i)+' ')
        fout.write('\n')

    fout.write('\n')


def output_put_intersection_constraints():

    # PUTs have intersection (Line 20~23)
    # Constraint type X1 and X2 implement constraint line 21 in the formulation.
    # Constraint type X3 implements constraint line 23 in the formulation.
    for i in dependency:
        for j in dependency:
            if dependency[i]['put_rate'] > 0 and dependency[j]['put_rate'] > 0:
                # Chech if intersections exist based on SLO latency constraints. If not, that means the current formulation can not be solved.
                k_exist = False
                for k in datacenter_in_use:
                    if in_put_slo_2(i,k) and in_put_slo_2(j,k):
                        k_exist = True
                        fout.write(' X1_'+str(i)+'_'+str(j)+'_'+str(k)+' : ' + 'X_'+str(i)+'_'+str(j)+'_'+str(k)+' - P_'+str(k)+'_'+str(i)+' - P_'+str(k)+'_'+str(j)+' <= 0\n')
                        fout.write(' X2_'+str(i)+'_'+str(j)+'_'+str(k)+' : ' +'P_'+str(k)+'_'+str(i)+' + P_'+str(k)+'_'+str(j)+' - 2  X_'+str(i)+'_'+str(j)+'_'+str(k)+' <= 0\n')

                need_operation = False

                if not k_exist:
                    print 'no solution: no X'
                    exit()

                for k in datacenter_in_use:
                    if in_put_slo_2(i,k) and in_put_slo_2(j,k):
                        if need_operation:
                            fout.write(' + ')
                        else:
                            fout.write(' X3_'+str(i)+'_'+str(j)+' : ') #add a name for this constraint

                        fout.write(' P_'+str(k)+'_'+str(i)+' + P_'+str(k)+'_'+str(j) + ' - X_'+str(i)+'_'+str(j)+'_'+str(k)+' ')
                        need_operation = True

                if need_operation:
                    fout.write(' > '+str(2 * number_of_failure_to_tolerate)+'\n')


def output_put_get_intersection_constraints():
                        
    # GETs and PUTs have intersection
    # Contraint type Y1 and Y2 implement constraint line 25 in the formulation.
    # Contraint type Y3 implements constraint line 26 in the formulation.
    for i in dependency:
        for j in dependency:
            if dependency[i]['get_rate'] > 0 and dependency[j]['put_rate'] > 0:
                k_exist = False
                for k in datacenter_in_use:#range(datacenter_number):
                    if in_get_slo(i,k) and in_put_slo_2(j,k):
                        k_exist = True
                        fout.write(' Y1_'+str(i)+'_'+str(j)+'_'+str(k)+' : ' + 'Y_'+str(i)+'_'+str(j)+'_'+str(k)+' - G_'+str(k)+'_'+str(i)+' - P_'+str(k)+'_'+str(j)+' <= 0\n')
                        fout.write(' Y2_'+str(i)+'_'+str(j)+'_'+str(k)+' : ' +'G_'+str(k)+'_'+str(i)+' + P_'+str(k)+'_'+str(j)+' - 2  Y_'+str(i)+'_'+str(j)+'_'+str(k)+' <= 0\n')

                need_operation = False

                if not k_exist:
                    print 'no solution: no Y'
                    exit()

                for k in datacenter_in_use:#range(datacenter_number):
                    if in_get_slo(i,k) and in_put_slo_2(j,k):
                        if need_operation:
                            fout.write(' + ')
                        else:
                            fout.write(' Y3_'+str(i)+'_'+str(j)+' : ') #add a name for this constraint

                        fout.write(' G_'+str(k)+'_'+str(i)+' + P_'+str(k)+'_'+str(j) + ' - Y_'+str(i)+'_'+str(j)+'_'+str(k)+' ')
                        need_operation = True

                if need_operation:
                    fout.write(' > '+str(2 * number_of_failure_to_tolerate)+'\n')

def output_relay_constraints():

    # Propagation server constraints
    # Line 28 in the formulation.
    for i in dependency:
        if dependency[i]['put_rate'] > 0:
            for k in datacenter_in_use:#range(datacenter_number):
                need_operation = False
                for j in datacenter_in_use:#range(datacenter_number):
                    if in_put_slo_3(i,j,k) and (i == k or network_price[i][j] > network_price[k][j]):
                        if need_operation:
                            fout.write(' + ')
                        else:
                            fout.write(' M1_'+str(i)+'_'+str(k)+' : ')

                        fout.write(' F_'+str(i)+'_'+str(j)+'_'+str(k)+' ')
                        need_operation = True

                if need_operation:
                    fout.write(' - R_'+str(i)+'_'+str(k)+' >= 0\n')

                need_operation = False
                for j in datacenter_in_use:#range(datacenter_number):
                    if in_put_slo_3(i,j,k) and (i == k or network_price[i][j] > network_price[k][j]):
                        if need_operation:
                            fout.write(' + ')
                        else:
                            fout.write(' M2_'+str(i)+'_'+str(k)+' : ')

                        fout.write(' F_'+str(i)+'_'+str(j)+'_'+str(k)+' ')
                        need_operation = True

                if need_operation:
                    fout.write(' - '+str(datacenter_number)+'  R_'+str(i)+'_'+str(k)+' <=0 \n')

    # Use Pi,j to eliminate quadratic
    # Line 30 in the formulation.
    for j in dependency:
        if dependency[j]['put_rate'] > 0:
            for i in datacenter_in_use:#range(datacenter_number):
                need_operation = False
                for k in datacenter_in_use:#range(datacenter_number):
                    if in_put_slo_3(j,i,k) and (j == k or network_price[j][i] > network_price[k][i]):
                        if need_operation:
                            fout.write(' + ')
                        else:
                            fout.write(' P1_'+str(i)+'_'+str(j)+' : ')

                        fout.write(' F_'+str(j)+'_'+str(i)+'_'+str(k)+' ')
                        need_operation = True

                if need_operation:
                    fout.write(' - P_'+str(i)+'_'+str(j)+' >= 0\n')

                need_operation = False
                for k in datacenter_in_use:#range(datacenter_number):
                    if in_put_slo_3(j,i,k) and (j == k or network_price[j][i] > network_price[k][i]):
                        if need_operation:
                            fout.write(' + ')
                        else:
                            fout.write(' P2_'+str(i)+'_'+str(j)+' : ')

                        fout.write(' F_'+str(j)+'_'+str(i)+'_'+str(k)+' ')
                        need_operation = True

                if need_operation:
                    fout.write(' - '+str(datacenter_number)+'  P_'+str(i)+'_'+str(j)+' <= 0\n')

def output_storage_constraints():

    # Storage constraints
    # Line 32 in the formulation.
    for i in datacenter_in_use:
        need_operation = False
        for j in dependency:
            if dependency[j]['get_rate'] > 0 and in_get_slo(i,j):
                if need_operation:
                    fout.write(' + ')
                else:
                    fout.write(' C1_'+str(i)+' : ')

                fout.write(' G_'+str(i)+'_'+str(j)+' ')
                need_operation = True

            if dependency[j]['put_rate'] > 0 and in_put_slo_2(i,j):
                if need_operation:
                    fout.write(' + ')
                else:
                    fout.write(' C1_'+str(i)+' : ')

                fout.write(' P_'+str(i)+'_'+str(j)+' ')

                need_operation = True

        if need_operation:
            fout.write(' - C_'+str(i)+' >= 0\n')

    for i in datacenter_in_use:
        need_operation = False
        for j in dependency:
            if dependency[j]['get_rate'] > 0 and in_get_slo(i,j):
                if need_operation:
                    fout.write(' + ')
                else:
                    fout.write(' C2_'+str(i)+' : ')

                fout.write(' G_'+str(i)+'_'+str(j)+' ')
                need_operation = True

            if dependency[j]['put_rate'] > 0 and in_put_slo_2(i,j):
                if need_operation:
                    fout.write(' + ')
                else:
                    fout.write(' C2_'+str(i)+' : ')

                fout.write(' P_'+str(i)+'_'+str(j)+' ')

                need_operation = True

        if need_operation:
            fout.write(' - '+str(2 * datacenter_number)+' C_'+str(i)+' <= 0\n')
	

# This founction generates contraints.
# Line 19~32 in the formulation.
def output_constraints_function():

    fout.write('\nSUBJECT TO\n')

    output_put_intersection_constraints()

    output_put_get_intersection_constraints()

    output_relay_constraints()

    output_storage_constraints()


def output_binary():

    fout.write('\nBINARY\n')

    #output G, which is GR_ij variable in the formulation
    for j in dependency:
        if dependency[j]['get_rate'] > 0:
            for i in datacenter_in_use:
                if in_get_slo(j,i):
                    fout.write(' G_'+str(i)+'_'+str(j)+'\n')


    #output P, which is PR_ij variable in the formulation
    for j in dependency:
        if dependency[j]['put_rate'] > 0:
            for i in datacenter_in_use:
                if in_put_slo_2(j,i):
                    fout.write(' P_'+str(i)+'_'+str(j)+'\n')

    #output F, which is F_ikj variable in the formulation.
    # Note that in here, F_ijk = F_ikj in the paper (notice the order of indexes)
    for i in dependency:
        if dependency[i]['put_rate'] > 0:
            for j in datacenter_in_use:
                for k in datacenter_in_use:
                    if in_put_slo_3(i,j,k) and (i == k or network_price[i][j] > network_price[k][j]):
                        fout.write(' F_'+str(i)+'_'+str(j)+'_'+str(k)+'\n')

    #output X, which is U_P_ijk variable in the formulation.
    for i in dependency:
        for j in dependency:
            if dependency[i]['put_rate'] > 0 and dependency[j]['put_rate'] > 0:
                for k in datacenter_in_use:#range(datacenter_number):
                    if in_put_slo_2(i,k) and in_put_slo_2(j,k):
                        fout.write(' X_'+str(i)+'_'+str(j)+'_'+str(k)+'\n')


    #output Y, which is U_G_ijk variable in the formulation.
    for i in dependency:
        for j in dependency:
            if dependency[i]['get_rate'] > 0 and dependency[j]['put_rate'] > 0:
                for k in datacenter_in_use:
                    if in_get_slo(i,k) and in_put_slo_2(j,k):
                        fout.write(' Y_'+str(i)+'_'+str(j)+'_'+str(k)+'\n')

    #output R, which is R_ik variable in the formulation.
    for i in dependency:
        if dependency[i]['put_rate'] > 0:
            for k in datacenter_in_use:
                exist_j = False
                for j in datacenter_in_use:
                    if in_put_slo_3(i,j,k) and (i == k or network_price[i][j] > network_price[k][j]):
                        exist_j = True
                        break
                if exist_j:
                    fout.write(' R_'+str(i)+'_'+str(k)+'\n')

    #output C, which is C_i variable in the formulation.
    for i in datacenter_in_use:
        fout.write(' C_'+str(i)+'\n')
	

def main():

    if len(sys.argv) != 9:
        print 'usage: python strong_consistency_formulation_generator.py <storage latency matrix> <VM latency matrix> <cloud pricing matrix> <application workload file> <PUT SLO in ms> <GET SLO in ms> <which percentile latency to consider> <# of failures to tolerate>'
        exit(1)

    init()

    global fout

    fout = open('formulation.lp','w')

    output_objective_function()

    output_constraints_function()

    output_binary()

    fout.write('\nEND\n')

    fout.close()

if __name__ == '__main__':
    main()
