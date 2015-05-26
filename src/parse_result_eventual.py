import sys
import xml.etree.ElementTree as et

def main():
    
    if len(sys.argv) != 3:
        print "usage: python parse_result_eventual.py <ILP result> <output file name>"
        exit(1)

	fout = open(sys.argv[2],'w')

	tree = et.parse(sys.argv[1])
	root = tree.getroot()
	for child in root:
		if child.tag == 'variables':
			break

	for line in child:
		if int(float(line.attrib['value'])+0.5) > 0:
			items = line.attrib['name'].split('_')
			for i in range(len(items)):
				if i == 0:
					fout.write(items[i])
				else:
					fout.write(' '+items[i])
			if items[0] == 'F':
				fout.write(' '+str(int(float(line.attrib['value'])+0.5)))
			fout.write('\n')

	fout.close()

if __name__ == '__main__':
	main()	
