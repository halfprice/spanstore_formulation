import sys

def list_possible_P():

	for i in dependency:
		for j in range(datacenter_number_begin, datacenter_number_end):
			for k in range(datacenter_number_begin, datacenter_number_end):
				for m in range(datacenter_number_begin, datacenter_number_end):
					if (network_price[i][k] > network_price[j][k] and network_price[i][m] > network_price[k][m]) and (network_price[j][m] > network_price[k][m] or j == k):
						P_list['P_'+str(i)+'_'+str(j)+'_'+str(k)+'_'+str(m)] = 1
	#print len(P_list)

def list_possible_I():

	for i in dependency:
		for j in range(datacenter_number_begin, datacenter_number_end):
			for k in range(datacenter_number_begin, datacenter_number_end):
				if (network_price[i][k] > network_price[j][k] or i == j) and in_put_sla_3(i,j,k):
					I_list['I_'+str(i)+'_'+str(j)+'_'+str(k)] = 1

def init():

	global datacenter_number_begin
        global datacenter_number_end
        if sys.argv[2] == 'ec2':
                datacenter_number_begin = 0
                datacenter_number_end = 8
        if sys.argv[2] == 'azure':
                datacenter_number_begin = 13
                datacenter_number_end = 19

	if sys.argv[2] == 'all':
		datacenter_number_begin = 0
		datacenter_number_end = 19

	datacenter_number = 19

	fin = open ('latency_matrix','r')
	lines = fin.readlines()
	fin.close()

	global latency
	latency = {}
	for i in range(datacenter_number):
		latency[i] = {}

	for line in lines:
		items = line[:-1].split(' ')
		if int(items[0]) < datacenter_number and int(items[1]) < datacenter_number:
			latency[int(items[0])][int(items[1])] = float(items[2]) * 1000 #makes it to ms
			latency[int(items[1])][int(items[0])] = float(items[2]) * 1000

	for i in range(datacenter_number):
		latency[i][i] = 0

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
	for i in range(datacenter_number):
		network_price = {}

	for line in lines:
		items = line[:-1].split(' ')
		if line.find('#') < 0 and int(items[0]) < datacenter_number:
			put_price[int(items[0])] = price_multiplier * float(items[1]) / 100000 #how much per 1 put
			get_price[int(items[0])] = price_multiplier * float(items[2]) / 100000 #how much per 1 get
			store_price[int(items[0])] = price_multiplier * float(items[3]) / 1024/1024/30 #how much per 1 KB per day
			network_price[int(items[0])] = {}
			for i in range(datacenter_number):
				network_price[int(items[0])][i] = price_multiplier * float(items[i+4]) / 1024/1024  #the price of transforming 1 KB data from items[0] to i

	for i in range(datacenter_number):
		network_price[i][i] = 0 #no charge for networking in the same data center

	fin = open('dependency','r')
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


	global overall_put
	overall_put = 0
	for i in dependency:
		overall_put += dependency[i]['put_rate']

	fin = open('SLA','r')
	lines = fin.readlines()
	fin.close()

	global PUT_SLA
	global GET_SLA
	if lines[0][-1] == '\n':
		SLA = int(lines[0][:-1]) # in ms
	else:
		SLA = int(lines[0])

	#put get sla are the same
	PUT_SLA = SLA
	GET_SLA = SLA

	global P_list
	P_list = {}
	list_possible_P()
	global I_list
	I_list = {}
	list_possible_I()


def in_get_sla(i,j):


	#print i, j, latency[i][j], GET_SLA, latency[i][j]<= GET_SLA
	if latency[i][j]<= GET_SLA:
		return True
	else:
		return False

def in_put_sla(i,j):  # i sends data directly to j
	
	if latency[i][j] <= PUT_SLA:  #here we assume that l[i,j]+l[j,k] > l[i,k] is always true
		return True
	else:
		return False

def in_put_sla_3(i,j,k):
	if latency[i][j] + latency[j][k] <= PUT_SLA:
		return True
	else:
		return False

def output_objective_function():

	fout.write('MINIMIZE\n  COST :  ')

	need_operation = False

	for i in dependency:
		for j in range(datacenter_number_begin, datacenter_number_end):
			if in_put_sla(i,j):
				if need_operation:
					fout.write(' + ')
				fout.write(' '+str((get_price[j] + network_price[j][i]*object_size)*dependency[i]['get_rate']) +' R_'+str(i)+'_'+str(j)+' \n')
				need_operation = True

	for j in range(datacenter_number_begin, datacenter_number_end):
		if need_operation:
			fout.write(' + ')
		fout.write(' '+str(overall_put*put_price[j])+' C_'+str(j)+' \n')
		need_operation = True

	for i in range(datacenter_number_begin, datacenter_number_end):
		for j  in range(datacenter_number_begin, datacenter_number_end):
			if i != j:
				if need_operation:
					fout.write(' + ')
				fout.write(' '+str(object_size*network_price[i][j])+' F_'+str(i)+'_'+str(j)+' \n')

	for j in range(datacenter_number_begin, datacenter_number_end):
		if need_operation:
			fout.write(' + ')
		fout.write(' '+str(store_price[j]*overall_size*storing_time)+' C_'+str(j)+' \n')

	fout.write('\n')


def output_one_replica_per_data_center():

	for i in dependency:

		need_operation = False

		for j in range(datacenter_number_begin, datacenter_number_end):
			if in_get_sla(i,j):
				if need_operation:
					fout.write(' + ')
				else:
					fout.write(' R1_'+str(i)+' : ')
					need_operation = True

				fout.write(' R_'+str(i)+'_'+str(j)+' ')
		if need_operation:
			fout.write(' = 1 \n')

def output_choose_data_center():

	for j in range(datacenter_number_begin, datacenter_number_end):
		need_operation = False
		for i in dependency:
			if in_get_sla(i,j):
				if need_operation:
					fout.write(' + ')
				else:
					fout.write(' C1_'+str(j)+' : ')
					need_operation = True

				fout.write(' R_'+str(i)+'_'+str(j)+' ')

		if need_operation:
			fout.write(' - C_'+str(j) +' >= 0 \n')

	
	for j in range(datacenter_number_begin, datacenter_number_end):
		need_operation = False
		for i in dependency:
			if in_get_sla(i,j):
				if need_operation:
					fout.write(' + ')
				else:
					fout.write(' C2_'+str(j)+' : ')
					need_operation = True

				fout.write(' R_'+str(i)+'_'+str(j)+' ')

		if need_operation:
			fout.write(' - '+str(datacenter_number_end - datacenter_number_begin)+' C_'+str(j) +' <= 0 \n')


def output_direct_forward_to_chosen_replica():

	for i in dependency:
		for k in range(datacenter_number_begin, datacenter_number_end):
			if in_put_sla(i,k):
				need_operation = False
				for j in range(datacenter_number_begin, datacenter_number_end):
					if ('I_'+str(i)+'_'+str(j)+'_'+str(k) in I_list):
						if need_operation:
							fout.write(' + ')
						else:
							fout.write(' F1_'+str(i)+'_'+str(k)+' : ')
							need_operation = True
						fout.write(' I_'+str(i)+'_'+str(j)+'_'+str(k)+' \n')
				if need_operation:
					fout.write(' - R_'+str(i)+'_'+str(k)+' = 0 \n')

def output_put_must_reach_everywhere():
	for i in dependency:
		for m in range(datacenter_number_begin, datacenter_number_end):
			need_operation = False
			for j in range(datacenter_number_begin, datacenter_number_end):
				if ('I_'+str(i)+'_'+str(j)+'_'+str(m) in I_list):
					if need_operation:
						fout.write(' + ')
					else:
						fout.write(' E1_'+str(i)+'_'+str(m)+' : ')
						need_operation = True
					fout.write(' I_'+str(i)+'_'+str(j)+'_'+str(m)+' \n')

			for j in range(datacenter_number_begin, datacenter_number_end):
				for k in range(datacenter_number_begin, datacenter_number_end):
					if 'P_'+str(i)+'_'+str(j)+'_'+str(k)+'_'+str(m) in P_list:
						if need_operation:
							fout.write(' + ')
						else:
							fout.write(' E1_'+str(i)+'_'+str(m)+' : ')
							need_operation = True
						fout.write(' P_'+str(i)+'_'+str(j)+'_'+str(k)+'_'+str(m)+' \n')

			if need_operation:
				fout.write(' - C_'+str(m) + ' = 0 \n')

def output_two_hop_constraint():

	for i in dependency:
		for j in range(datacenter_number_begin, datacenter_number_end):
			if in_put_sla(i,j):
				for k in range(datacenter_number_begin, datacenter_number_end):
					for m in range(datacenter_number_begin, datacenter_number_end):
						if 'P_'+str(i)+'_'+str(j)+'_'+str(k)+'_'+str(m) in P_list:
							fout.write(' TWO_'+str(i)+'_'+str(j)+'_'+str(k)+'_'+str(m)+' : P_'+str(i)+'_'+str(j)+'_'+str(k)+'_'+str(m)+' - R_'+str(i)+'_'+str(j)+' <= 0 \n')

def output_forward_constraint():

	for i in range(datacenter_number_begin, datacenter_number_end):
		for j in range(datacenter_number_begin, datacenter_number_end):
			need_operation = False
			for k in range(datacenter_number_begin, datacenter_number_end):
				if 'I_'+str(i)+'_'+str(j)+'_'+str(k) in I_list:
					if need_operation:
						fout.write(' + ')
					else:
						fout.write(' F2_'+str(i)+'_'+str(j)+' : ')
						need_operation = True
					fout.write(' '+str(dependency[i]['put_rate'])+' I_'+str(i)+'_'+str(j)+'_'+str(k)+' \n')

				if 'I_'+str(k)+'_'+str(i)+'_'+str(j) in I_list:
					if need_operation:
						fout.write(' + ')
					else:
						fout.write(' F2_'+str(i)+'_'+str(j)+' : ')
						need_operation = True
					fout.write(' '+str(dependency[k]['put_rate'])+' I_'+str(k)+'_'+str(i)+'_'+str(j)+' \n')

			for k in range(datacenter_number_begin, datacenter_number_end):
				for m in range(datacenter_number_begin, datacenter_number_end):
					if 'P_'+str(i)+'_'+str(j)+'_'+str(k)+'_'+str(m) in P_list:
						if need_operation :
							fout.write(' + ')
						else:
							fout.write(' F2_'+str(i)+'_'+str(j)+' : ')
							need_operation = True
						fout.write(' '+str(dependency[i]['put_rate'])+' P_'+str(i)+'_'+str(j)+'_'+str(k)+'_'+str(m)+' \n')
					if 'P_'+str(k)+'_'+str(i)+'_'+str(j)+'_'+str(m) in P_list:
						if need_operation :
							fout.write(' + ')
						else:
							fout.write(' F2_'+str(i)+'_'+str(j)+' : ')
							need_operation = True
						fout.write(' '+str(dependency[k]['put_rate'])+' P_'+str(k)+'_'+str(i)+'_'+str(j)+'_'+str(m)+' \n')
					if 'P_'+str(k)+'_'+str(m)+'_'+str(i)+'_'+str(j) in P_list:
						if need_operation :
							fout.write(' + ')
						else:
							fout.write(' F2_'+str(i)+'_'+str(j)+' : ')
							need_operation = True
						fout.write(' '+str(dependency[k]['put_rate'])+' P_'+str(k)+'_'+str(m)+'_'+str(i)+'_'+str(j)+' \n')

			if need_operation:
				fout.write(' - F_'+str(i)+'_'+str(j)+' = 0 \n')

def output_forward_constraint_merge_forward():

	for i in range(datacenter_number_begin, datacenter_number_end):
		for j in range(datacenter_number_begin, datacenter_number_end):
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
				#if 'D_'+str(i)+'_'+str(i)+'_'+str(j) in D_list:
				#	if need_operation:
				#		fout.write(' + ')
				#	else:
				#		fout.write(' F3_'+str(i)+'_'+str(j)+' : ')
				#		need_operation = True
				#	fout.write(' '+str(dependency[i]['put_rate'])+' D_'+str(i)+'_'+str(i)+'_'+str(j)+' ')
				if need_operation:
					fout.write(' - F_'+str(i)+'_'+str(j)+' = 0\n')

def output_path_constraints():

	global D_list
	D_list = {}

	for i in dependency:
		for k in range(datacenter_number_begin, datacenter_number_end):
			for m in range(datacenter_number_begin, datacenter_number_end):
				if k != m and i != k:
					need_operation = False
					for j in range(datacenter_number_begin, datacenter_number_end):
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
		for k in range(datacenter_number_begin, datacenter_number_end):
			for m in range(datacenter_number_begin, datacenter_number_end):
				if k != m and i != k:
					need_operation = False
					for j in range(datacenter_number_begin, datacenter_number_end):
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
						fout.write(' - '+str(3*(datacenter_number_end - datacenter_number_begin))+' D_'+str(i)+'_'+str(k)+'_'+str(m)+' <= 0 \n')
						D_list['D_'+str(i)+'_'+str(k)+'_'+str(m)] = 1

	for i in dependency:
		for k in range(datacenter_number_begin, datacenter_number_end):
			if i != k:
				need_operation = False
				for m in range(datacenter_number_begin, datacenter_number_end):
					if 'I_'+str(i)+'_'+str(k)+'_'+str(m) in I_list:
						if need_operation:
							fout.write(' + ')
						else:
							fout.write(' D3_'+str(i)+'_'+str(k)+' : ')
							need_operation = True
						fout.write(' I_'+str(i)+'_'+str(k)+'_'+str(m)+' ')
					for j in range(datacenter_number_begin, datacenter_number_end):
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
		for k in range(datacenter_number_begin, datacenter_number_end):
			if i != k:
				need_operation = False
				for m in range(datacenter_number_begin, datacenter_number_end):
					if 'I_'+str(i)+'_'+str(k)+'_'+str(m) in I_list:
						if need_operation:
							fout.write(' + ')
						else:
							fout.write(' D4_'+str(i)+'_'+str(k)+' : ')
							need_operation = True
						fout.write(' I_'+str(i)+'_'+str(k)+'_'+str(m)+' ')
					for j in range(datacenter_number_begin, datacenter_number_end):
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
					fout.write(' - '+str(2*(datacenter_number_end - datacenter_number_begin))+' D_'+str(i)+'_'+str(i)+'_'+str(k)+' <= 0\n')      # N*N+N, N is datacenter number
					D_list['D_'+str(i)+'_'+str(i)+'_'+str(k)] = 1


def output_constraints_function():

	fout.write('\nSUBJECT TO\n')	
	output_one_replica_per_data_center()
	output_choose_data_center()
	output_direct_forward_to_chosen_replica()
	output_put_must_reach_everywhere()
	#output_two_hop_constraint()
	#output_forward_constraint()
	output_path_constraints()
	output_forward_constraint_merge_forward()

def output_general():

	fout.write('\nGENERAL\n')
	#output F
	for i in range(datacenter_number_begin, datacenter_number_end):
		for j in range(datacenter_number_begin, datacenter_number_end):
			if i != j:
				fout.write(' F_'+str(i)+'_'+str(j)+'\n')

def output_binary():

	fout.write('\nBINARY\n')

	#output R
	for i in dependency:
		for j in range(datacenter_number_begin, datacenter_number_end):
			if in_put_sla(i,j):
				fout.write(' R_'+str(i)+'_'+str(j)+' \n')

	#output C
	for i in range(datacenter_number_begin, datacenter_number_end):
		fout.write(' C_'+str(i)+' \n')

	#output I
	for i in dependency:
		for j in range(datacenter_number_begin, datacenter_number_end):
			for k in range(datacenter_number_begin, datacenter_number_end):
				if 'I_'+str(i)+'_'+str(j)+'_'+str(k) in I_list:
					fout.write(' I_'+str(i)+'_'+str(j)+'_'+str(k)+' \n')
	#output P
	for i in dependency:
		for j in range(datacenter_number_begin, datacenter_number_end):
			for k in range(datacenter_number_begin, datacenter_number_end):
				for m in range(datacenter_number_begin, datacenter_number_end):
					if 'P_'+str(i)+'_'+str(j)+'_'+str(k)+'_'+str(m) in P_list:
						fout.write(' P_'+str(i)+'_'+str(j)+'_'+str(k)+'_'+str(m)+'\n')

	#output D
	for i in dependency:
		for j in range(datacenter_number_begin, datacenter_number_end):
			for k in range(datacenter_number_begin, datacenter_number_end):
				if 'D_'+str(i)+'_'+str(j)+'_'+str(k) in D_list:
					fout.write('D_'+str(i)+'_'+str(j)+'_'+str(k)+'\n')
	
	
def main():

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
