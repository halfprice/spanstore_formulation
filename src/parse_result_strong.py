import sys
import xml.etree.ElementTree as et

def main():

    if len(sys.argv) != 3:
        print "usage: python parse_result_strong.py <ILP result> <output file name>"
        exit(1)

	fout = open(sys.argv[2],'w')

	tree = et.parse(sys.argv[1])
	root = tree.getroot()
	for child in root:
		if child.tag == 'variables':
			break

	for line in child:
		if float(line.attrib['value']) < 1.1 and float(line.attrib['value']) > 0.9:
			items = line.attrib['name'].split('_')
			for i in range(len(items)):
				if i == 0:
					fout.write(items[i])
				else:
					fout.write(' '+items[i])
			fout.write('\n')

	fout.close()

if __name__ == '__main__':
	main()	
