import sys
import xml.etree.ElementTree as et

def main():

	fout = open(sys.argv[2],'w')

	tree = et.parse(sys.argv[1])
	root = tree.getroot()
	for child in root:
		if child.tag == 'variables':
			break

	for line in child:
		if int(line.attrib['value']) > 0:
			items = line.attrib['name'].split('_')
			for i in range(len(items)):
				if i == 0:
					fout.write(items[i])
				else:
					fout.write(' '+items[i])
			if items[0] == 'F':
				fout.write(' '+line.attrib['value'])
			fout.write('\n')

	fout.close()

if __name__ == '__main__':
	main()	
