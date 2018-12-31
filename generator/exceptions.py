import xml.etree.ElementTree as ET

def element_to_xml_string(element):
	bytes_obj = ET.tostring(element, encoding='utf-8', method='xml')
	return bytes_obj.decode('utf-8').strip('\t').strip('\n')

class MissingAttributeException(Exception):

	def __init__(self, attribute, element, message=None):
		self.attribute = attribute
		self.element = element
		if message is None:
			message = 'Missing {attr} attribute at {element}'.format(
				attr=attribute, 
				element=element_to_xml_string(element))
		super(MissingAttributeException, self).__init__(message)
