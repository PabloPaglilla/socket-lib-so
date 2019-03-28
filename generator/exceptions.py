import xml.etree.ElementTree as ET

def element_to_xml_string(element):
	bytes_obj = ET.tostring(element, encoding='utf-8', method='xml')
	return bytes_obj.decode('utf-8').strip('\t').strip('\n')

class GeneratorException(Exception):
	pass

class MissingAttributeException(GeneratorException):

	def __init__(self, attribute, element, message=None):
		self.attribute = attribute
		self.element = element
		if message is None:
			message = 'Missing {attr} attribute at {element}'.format(
				attr=attribute, 
				element=element_to_xml_string(element))
		self.message = message
		super(MissingAttributeException, self).__init__(message)

class InvalidFieldTypeException(GeneratorException):

	def __init__(self, element_type, element, message=None):
		self.element_type = element_type
		self.element = element
		if message is None:
			message = 'Invalid type {element_type} at {element}'.format(
				element_type=element_type, element=element_to_xml_string(element))
		self.message = message	
		super(InvalidFieldTypeException, self).__init__(message)