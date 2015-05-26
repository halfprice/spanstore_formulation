import sys


MAX_LATENCY = 1000000

'''
Read configuration files and initialize all states
'''
def init():
    global datacenter_number
    global datacenter_number_max
    datacenter_number_max = 19

    global datacenter_in_use
    datacenter_in_use = []
    for i in range(8):
        datacenter_in_use.append(i)
    for i in range(13, 19):
        datacenter_in_use.append(i)
    datacenter_number = len(datacenter_in_use)

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

    fin = open('storage latency matrix','r') #TODO input 1
    lines = fin.readlines()
    fin.close()
    for line in lines:
        items = line[:-1].split(' ')
        if int(items[0]) < datacenter_number_max and int(items[1]) < datacenter_number_max:
            latency[int(items[0])][int(items[1])][items[2]][items[3]] = float(items[4])

    fin = open('/home/csgrads/zwu005/research/metaCloud/data/information/vm_latency_matrix_percentile','r') #TODO input 2
    lines = fin.readlines()
    fin.close()

    for line in lines:
        items = line[:-1].split(' ')
        if int(items[0]) < datacenter_number_max and int(items[1]) < datacenter_number_max:
            latency[int(items[0])][int(items[1])][items[2]][items[3]] = float(items[4]) #makes it to ms

    fin = open(sys.argv[1],'r')  #give it a price
    lines = fin.readlines()
    fin.close()

    price_multiplier = 100000

    global get_price
    global put_price
    global store_price
    global network_price
    get_price = {}
    put_price = {}
    store_price = {}
    network_price = {}

    for line in lines:
        items = line[:-1].split(' ')
        if line.find('#') < 0 and int(items[0]) < datacenter_number_max:
            put_price[int(items[0])] = price_multiplier * float(items[1]) / 100000 #how much per 1 put
            get_price[int(items[0])] = price_multiplier * float(items[2]) / 100000 #how much per 1 get
            store_price[int(items[0])] = price_multiplier * float(items[3]) / 1024/1024/30 #how much per 1 KB per day
            network_price[int(items[0])] = {}
            for i in range(datacenter_number_max):
                network_price[int(items[0])][i] = price_multiplier * float(items[i+4]) / 1024/1024  #the price of transforming 1 KB data from items[0] to i

    for i in range(datacenter_number_max):
        if i in network_price:
            network_price[i][i] = 0 #no charge for networking in the same data center

    fin = open(sys.argv[2],'r')
    lines = fin.readlines()
    fin.close()

    global dependency
    global object_size
    global overall_size
    global storing_time
    dependency = {}

    for line in lines:
        items = line[:-1].split()
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

    global locking_latency
    locking_latency = {}
    dependency_set = []
    dependency_string = ''
    for region in dependency:
        dependency_set.append(region)
    sorted_list = sorted(dependency_set)
    for region in sorted_list:
        dependency_string += str(region) + ' '
    dependency_string = dependency_string[:-1]#remove the last space
    fin = open('/home/csgrads/zwu005/research/metaCloud/data/measurement_related/finding_locking_sets/locking_sets','r')
    lines = fin.readlines()
    fin.close()
    for line in lines:
        items = line[:-1].split('||')
        if items[0] == dependency_string:
            current_percentile = items[1]
            locking_latency[current_percentile] = {}
            pairs = items[2].split(' ')
            for pair in pairs:
                dcs = pair.split('>')
                if int(dcs[0]) not in locking_latency[current_percentile]:
                    locking_latency[current_percentile][int(dcs[0])] = 0
                if latency[int(dcs[0])][int(dcs[1])]['VM'][current_percentile] > locking_latency[current_percentile][int(dcs[0])]:
                    locking_latency[current_percentile][int(dcs[0])] = latency[int(dcs[0])][int(dcs[1])]['VM'][current_percentile]

    fin = open(sys.argv[3],'r')
    lines = fin.readlines()
    fin.close()

    global PUT_SLA
    global GET_SLA
    global percentile
    PUT_SLA = int(lines[0][:-1]) # in ms
    if lines[1][-1] == '\n':
        GET_SLA = int(lines[1][:-1]) # in ms
    else:
        GET_SLA = int(lines[1])
    if lines[2][-1] == '\n':
        percentile = lines[2][:-1] # in ms
    else:
        percentile = lines[2]

    global failure_tolerance
    failure_tolerance = int(sys.argv[4])


def in_get_sla(i,j):

    if latency[i][j]['GET'][percentile]<= GET_SLA:
        return True
    else:
        return False

def in_put_sla_2(i,j):  # i sends data directly to j
	
    if latency[i][j]['VM'][percentile] + latency[i][j]['PUT'][percentile] <= PUT_SLA:  #here we assume that l[i,j]+l[j,k] > l[i,k] is always true
    #if locking_latency[percentile][i] + latency[i][j]['PUT'][percentile] <= PUT_SLA:  #here we assume that l[i,j]+l[j,k] > l[i,k] is always true
        return True
    else:
        return False

def in_put_sla_3(i,j,k):  # i sends data to j through k

    if latency[i][k]['VM'][percentile]+latency[k][j]['PUT'][percentile]+latency[i][j]['VM'][percentile] <= PUT_SLA: #lock directly required from the put data center, and there is propagaion from i to j
    #if locking_latency[percentile][i]+latency[i][k]['VM'][percentile]+latency[k][j]['PUT'][percentile] <= PUT_SLA: #lock directly required from the put data center, and there is propagaion from i to j
        return True
    else:
        return False

def output_objective_function():

    fout.write('MINIMIZE\n  COST :  ')

    need_operation = False

    for j in dependency:
        if dependency[j]['get_rate'] > 0:
            for i in datacenter_in_use: #range(datacenter_number):
                if in_get_sla(j,i):
                    if need_operation:
                        fout.write(' + ')

                    fout.write(' '+str(dependency[j]['get_rate'] * get_price[i])+'  G_'+str(i)+'_'+str(j)+' ')
                    fout.write(' + '+str(dependency[j]['get_rate'] * network_price[i][j] * object_size)+'  G_'+str(i)+'_'+str(j)+' ')
                    fout.write('\n')
                    need_operation = True

                
    #M[j][k] only needs to output once
    has_m = {}
    for i in datacenter_in_use:#range(datacenter_number):
        has_m[i] = {}
        for j in datacenter_in_use:#range(datacenter_number):
            has_m[i][j] = False

    for j in dependency:
        if dependency[j]['put_rate'] > 0:
            for i in datacenter_in_use:#range(datacenter_number):
                for k in datacenter_in_use:#range(datacenter_number):
                    if in_put_sla_3(j,i,k) and (j == k or network_price[j][i] > network_price[k][i] ):
                        if need_operation:
                            fout.write(' + ')

                        if not has_m[j][k]:
                            fout.write(' '+str(dependency[j]['put_rate'] * network_price[j][k] * object_size)+'  M_'+str(j)+'_'+str(k)+' + ')
                            has_m[j][k] = True
                        fout.write(' '+str(dependency[j]['put_rate'] * put_price[i])+'  R_'+str(j)+'_'+str(i)+'_'+str(k)+' ')
                        fout.write(' + '+str(dependency[j]['put_rate'] * network_price[k][i] * object_size)+'  R_'+str(j)+'_'+str(i)+'_'+str(k)+' ')
                        fout.write('\n')
                        need_operation = True

    for i in datacenter_in_use:#range(datacenter_number):
        if need_operation:
            fout.write(' + ')
        fout.write(' '+ str(store_price[i]*overall_size*storing_time)+' C_'+str(i)+' ')
        fout.write('\n')

    fout.write('\n')





def output_constraints_function():

    fout.write('\nSUBJECT TO\n')

    #puts have intersection
    for i in dependency:
        for j in dependency:
            if dependency[i]['put_rate'] > 0 and dependency[j]['put_rate'] > 0:
                k_exist = False #chech if there is intersection constraints. If not, that means the current formulation couldn't be solved.
                for k in datacenter_in_use:#range(datacenter_number):
                    if in_put_sla_2(i,k) and in_put_sla_2(j,k):
                        k_exist = True
                        fout.write(' X1_'+str(i)+'_'+str(j)+'_'+str(k)+' : ' + 'X_'+str(i)+'_'+str(j)+'_'+str(k)+' - P_'+str(k)+'_'+str(i)+' - P_'+str(k)+'_'+str(j)+' <= 0\n')
                        fout.write(' X2_'+str(i)+'_'+str(j)+'_'+str(k)+' : ' +'P_'+str(k)+'_'+str(i)+' + P_'+str(k)+'_'+str(j)+' - 2  X_'+str(i)+'_'+str(j)+'_'+str(k)+' <= 0\n')

                need_operation = False

                if not k_exist:
                    print 'no solution: no X'
                    exit()

                for k in datacenter_in_use:#range(datacenter_number):
                    if in_put_sla_2(i,k) and in_put_sla_2(j,k):
                        if need_operation:
                            fout.write(' + ')
                        else:
                            fout.write(' X3_'+str(i)+'_'+str(j)+' : ') #add a name for this constraint

                        fout.write(' P_'+str(k)+'_'+str(i)+' + P_'+str(k)+'_'+str(j) + ' - X_'+str(i)+'_'+str(j)+'_'+str(k)+' ')
                        need_operation = True

                if need_operation:
                    fout.write(' > '+str(failure_tolerance + 1)+'\n')

                        
    #gets and puts have intersection
    for i in dependency:
        for j in dependency:
            if dependency[i]['get_rate'] > 0 and dependency[j]['put_rate'] > 0:
                k_exist = False
                for k in datacenter_in_use:#range(datacenter_number):
                    if in_get_sla(i,k) and in_put_sla_2(j,k):
                        k_exist = True
                        fout.write(' Y1_'+str(i)+'_'+str(j)+'_'+str(k)+' : ' + 'Y_'+str(i)+'_'+str(j)+'_'+str(k)+' - G_'+str(k)+'_'+str(i)+' - P_'+str(k)+'_'+str(j)+' <= 0\n')
                        fout.write(' Y2_'+str(i)+'_'+str(j)+'_'+str(k)+' : ' +'G_'+str(k)+'_'+str(i)+' + P_'+str(k)+'_'+str(j)+' - 2  Y_'+str(i)+'_'+str(j)+'_'+str(k)+' <= 0\n')

                need_operation = False

                if not k_exist:
                    print 'no solution: no Y'
                    exit()

                for k in datacenter_in_use:#range(datacenter_number):
                    if in_get_sla(i,k) and in_put_sla_2(j,k):
                        if need_operation:
                            fout.write(' + ')
                        else:
                            fout.write(' Y3_'+str(i)+'_'+str(j)+' : ') #add a name for this constraint

                        fout.write(' G_'+str(k)+'_'+str(i)+' + P_'+str(k)+'_'+str(j) + ' - Y_'+str(i)+'_'+str(j)+'_'+str(k)+' ')
                        need_operation = True

                if need_operation:
                    fout.write(' > '+str(failure_tolerance + 1)+'\n')

    #propagation server constraints:
    for i in dependency:
        if dependency[i]['put_rate'] > 0:
            for k in datacenter_in_use:#range(datacenter_number):
                need_operation = False
                for j in datacenter_in_use:#range(datacenter_number):
                    if in_put_sla_3(i,j,k) and (i == k or network_price[i][j] > network_price[k][j]):
                        if need_operation:
                            fout.write(' + ')
                        else:
                            fout.write(' M1_'+str(i)+'_'+str(k)+' : ')

                        fout.write(' R_'+str(i)+'_'+str(j)+'_'+str(k)+' ')
                        need_operation = True

                if need_operation:
                    fout.write(' - M_'+str(i)+'_'+str(k)+' >= 0\n')

                need_operation = False
                for j in datacenter_in_use:#range(datacenter_number):
                    if in_put_sla_3(i,j,k) and (i == k or network_price[i][j] > network_price[k][j]):
                        if need_operation:
                            fout.write(' + ')
                        else:
                            fout.write(' M2_'+str(i)+'_'+str(k)+' : ')

                        fout.write(' R_'+str(i)+'_'+str(j)+'_'+str(k)+' ')
                        need_operation = True

                if need_operation:
                    fout.write(' - '+str(datacenter_number)+'  M_'+str(i)+'_'+str(k)+' <=0 \n')

    #use Pi,j to eliminate quadratic
    for j in dependency:
        if dependency[j]['put_rate'] > 0:
            for i in datacenter_in_use:#range(datacenter_number):
                need_operation = False
                for k in datacenter_in_use:#range(datacenter_number):
                    if in_put_sla_3(j,i,k) and (j == k or network_price[j][i] > network_price[k][i]):
                        if need_operation:
                            fout.write(' + ')
                        else:
                            fout.write(' P1_'+str(i)+'_'+str(j)+' : ')

                        fout.write(' R_'+str(j)+'_'+str(i)+'_'+str(k)+' ')
                        need_operation = True

                if need_operation:
                    fout.write(' - P_'+str(i)+'_'+str(j)+' >= 0\n')

                need_operation = False
                for k in datacenter_in_use:#range(datacenter_number):
                    if in_put_sla_3(j,i,k) and (j == k or network_price[j][i] > network_price[k][i]):
                        if need_operation:
                            fout.write(' + ')
                        else:
                            fout.write(' P2_'+str(i)+'_'+str(j)+' : ')

                        fout.write(' R_'+str(j)+'_'+str(i)+'_'+str(k)+' ')
                        need_operation = True

                if need_operation:
                    fout.write(' - '+str(datacenter_number)+'  P_'+str(i)+'_'+str(j)+' <= 0\n')


    #storage constraints

    for i in datacenter_in_use:#range(datacenter_number):
        need_operation = False
        for j in dependency:
            if dependency[j]['get_rate'] > 0 and in_get_sla(i,j):
                if need_operation:
                    fout.write(' + ')
                else:
                    fout.write(' C1_'+str(i)+' : ')

                fout.write(' G_'+str(i)+'_'+str(j)+' ')
                need_operation = True

            if dependency[j]['put_rate'] > 0 and in_put_sla_2(i,j):
                if need_operation:
                    fout.write(' + ')
                else:
                    fout.write(' C1_'+str(i)+' : ')

                fout.write(' P_'+str(i)+'_'+str(j)+' ')

                need_operation = True

        if need_operation:
            fout.write(' - C_'+str(i)+' >= 0\n')

    for i in datacenter_in_use:#range(datacenter_number):
        need_operation = False
        for j in dependency:
            if dependency[j]['get_rate'] > 0 and in_get_sla(i,j):
                if need_operation:
                    fout.write(' + ')
                else:
                    fout.write(' C2_'+str(i)+' : ')

                fout.write(' G_'+str(i)+'_'+str(j)+' ')
                need_operation = True

            if dependency[j]['put_rate'] > 0 and in_put_sla_2(i,j):
                if need_operation:
                    fout.write(' + ')
                else:
                    fout.write(' C2_'+str(i)+' : ')

                fout.write(' P_'+str(i)+'_'+str(j)+' ')

                need_operation = True

        if need_operation:
            fout.write(' - '+str(2*datacenter_number)+' C_'+str(i)+' <= 0\n')
	


def output_binary():

    fout.write('\nBINARY\n')

    #output G
    for j in dependency:
        if dependency[j]['get_rate'] > 0:
            for i in datacenter_in_use:#range(datacenter_number):
                if in_get_sla(j,i):
                    fout.write(' G_'+str(i)+'_'+str(j)+'\n')


    #output P
    for j in dependency:
        if dependency[j]['put_rate'] > 0:
            for i in datacenter_in_use:#range(datacenter_number):
                if in_put_sla_2(j,i):
                    fout.write(' P_'+str(i)+'_'+str(j)+'\n')

    #output R
    for i in dependency:
        if dependency[i]['put_rate'] > 0:
            for j in datacenter_in_use:#range(datacenter_number):
                for k in datacenter_in_use:#range(datacenter_number):
                    if in_put_sla_3(i,j,k) and (i == k or network_price[i][j] > network_price[k][j]):
                        fout.write(' R_'+str(i)+'_'+str(j)+'_'+str(k)+'\n')

    #output X
    for i in dependency:
        for j in dependency:
            if dependency[i]['put_rate'] > 0 and dependency[j]['put_rate'] > 0:
                for k in datacenter_in_use:#range(datacenter_number):
                    if in_put_sla_2(i,k) and in_put_sla_2(j,k):
                        fout.write(' X_'+str(i)+'_'+str(j)+'_'+str(k)+'\n')


    #output Y
    for i in dependency:
        for j in dependency:
            if dependency[i]['get_rate'] > 0 and dependency[j]['put_rate'] > 0:
                for k in datacenter_in_use:#range(datacenter_number):
                    if in_get_sla(i,k) and in_put_sla_2(j,k):
                        fout.write(' Y_'+str(i)+'_'+str(j)+'_'+str(k)+'\n')

    #output M
    for i in dependency:
        if dependency[i]['put_rate'] > 0:
            for k in datacenter_in_use:#range(datacenter_number):
                exist_j = False
                for j in datacenter_in_use:#range(datacenter_number):
                    if in_put_sla_3(i,j,k) and (i == k or network_price[i][j] > network_price[k][j]):
                        exist_j = True
                        break
                if exist_j:
                    fout.write(' M_'+str(i)+'_'+str(k)+'\n')

    #output C
    for i in datacenter_in_use:#range(datacenter_number):
        fout.write(' C_'+str(i)+'\n')
	

def main():

    if len(sys.argv) != 5:
        print 'usage: python generating_formulation.py <price matrix> <dependency> <SLA> <# of failures to tolarant>'
        exit(0)

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
