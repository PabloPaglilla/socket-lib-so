import argparse
import xml.etree.ElementTree as ET
from sys import stderr
from os import path, remove

import templates, exceptions

type_sizes = {
	'int8_t': 1,
	'uint8_t': 1,
	'int16_t': 2,
	'uint16_t': 2,
	'int32_t': 4,
	'uint32_t': 4,
	'char': 1
}

def generate(xml_source, provided_path):

	"""Genera los archivos
	   Parametros:
	   	-xml_source: dirección del archivo xml fuente dada
	   		por el usuario.
	   	-provided_path: dirección dada por el usuario con 
			el flag '-o'."""

	tree = ET.parse(xml_source)
	root = tree.getroot()
	header_path, source_path = get_file_paths(root, provided_path)
	header_name = header_path.split('/')[-1]
	header = source = None
	try:
		header = open(header_path, 'w')
		source = open(source_path, 'w')
	except OSError as error:
		err = "Could not open or create file {path}".format(
			path=error.filename)
		stderr.write(err)
		if header and not header.closed:
			# If the header was succesfully opened and what failed
			# was the source, we close and delete the header
			header.close()
			remove_file(header_path)
		return
	try:
		generate_header(root, header)
		generate_source(root, source, header_name)
	except exceptions.GeneratorException as error:
		stderr.write(error.message + '\n')
		remove_file(header_path)
		remove_file(source_path)
	finally:
		header.close()
		source.close()

def remove_file(file_path):
	if path.isfile(file_path):
		try:
			remove(file_path)
		except OSError:
			pass

def get_file_paths(root, provided_path):

	"""Devuelve las direcciones de los archivos a generar
	   Parametros:
		-root: elemento root del archivo xml
		-provided_path: dirección dada por el usuario con 
			el flag '-o'."""

	if provided_path.endswith('/') or provided_path == '':
		base_path = provided_path + root.tag
	else:
		base_path = provided_path
	return base_path + '.h', base_path + '.c'

def _get_element_attribute(element, attribute):

	"""Retorna un atributo de un elemento xml. Si el elemento
	no posee el atributo, se tira la excepcion correspondiente.
	Parametros:
	 -element: el elemento xml
	 -attribute: el nombre del atributo"""

	if not attribute in element.attrib:
		raise exceptions.MissingAttributeException(attribute, element)
	return element.attrib[attribute]

def get_name(element):
	return _get_element_attribute(element, 'name')

def get_len(element):
	return _get_element_attribute(element, 'len')

def _is_valid_type(element_type):
	return element_type in type_sizes or element_type[0:-2] in type_sizes

def get_type(element):

	"""Retorna el atributo 'type' de un elemento. Si el tipo no es
	válido, tira la excepción correspondiente.
	Parametros:
	 -element: el elemento xml."""

	element_type = _get_element_attribute(element, 'type')
	if not _is_valid_type(element_type):
		raise exceptions.InvalidFieldTypeException(element_type, element)
	return element_type

def generate_header(root, header):

	"""Genera el header file.
	   Parametros:
		-root: el elemento root del archivo xml
		-header: el objeto archivo al que escribir"""

	header.write(templates.header_includes)
	header.write(templates.header_defines)
	generate_enum_definitions(header, root)
	for message in root.iter('message'):
		generate_msg_defines(header, message)
		generate_struct(header, message)
		generate_signatures(header, message)
	header.write(templates.msg_handling_functions_declarations)
	header.write(templates.header_close)

def generate_enum_definitions(file, root):

	"""Genera el código que define las enumeraciones del protocolo.
	   Parametros:
	   	-file: el archivo al que escribir
	   	-root: el elemento root xml"""

	template = templates.enum_definition
	for enum in root.iter('enum'):
		enum_name = get_name(enum)
		values = list(map(
			lambda x: x.text, 
			enum.iter('entry')))
		values = ', '.join(values)
		file.write(template.format(
			enum_name=enum_name,
			values=values))

def generate_msg_defines(file, message):

	"""Genera el código que define el nombre del mensaje, 
	su id y su tamaño.
	   Parametros:
	   	-file: el archivo al que escribir
	   	-message: el elemento xml del mensaje"""

	msg_name = get_name(message)
	s = templates.message_defines_template.format(
		msg_name_upper=msg_name.upper(),
		msg_size = get_message_size(message))
	file.write(s)

def get_message_size(message):

	"""Retorna el tamaño de un mensaje en bytes.
	   Parametros:
	   	-message: el elemento xml del mensaje"""

	sizes = list(map(get_field_size, message.iter('field')))
	return sum(sizes)

def get_field_size(field):

	"""Retorna el tamaño de un campo de un mensaje.
	   Parametros:
	   	-field: el elemento xml del campo"""

	field_type = get_type(field)
	if is_array_type(field):
		type_name = field_type[0:-2]
		type_size = type_sizes[type_name]
		amount = int(get_len(field))
		return type_size * amount
	return type_sizes[field_type]

def generate_struct(file, message):

	"""Genera el struct correspondiente al mensaje.
	   Parametros:
	   	-file: el archivo al que escribir
	   	-message: el elemento xml del mensaje"""

	msg_name = get_name(message)
	field_declarations = list(map(field_declaration, message.iter('field')))
	field_declarations = "\n\t".join(field_declarations)
	s = templates.struct_declaration_template.format(
		msg_name=msg_name, field_declarations=field_declarations)
	file.write(s)

def field_declaration(field):

	"""Retorna la declaración de un campo, el cual es su definición
	seguida de un ';'.
	   Parametros:
	   	-field: el elemento xml del campo"""

	return field_description(field) + ';'

def field_description(field):

	"""Retorna la definición de un campo. Por ejemplo 'int8_t x' o 
	'char str[10]'.
	   Parametros:
	   	-field: el elemento xml del campo"""

	field_type = get_type(field)
	field_name = field.text
	array_def = ''
	if is_array_type(field):
		field_type = field_type[0:-2]
		array_def = '[' + get_len(field) + ']'
	return templates.field_description_template.format(
		field_type=field_type, field_name=field_name,
		array_def=array_def).strip('\n ').strip(' ')

def generate_signatures(file, message):

	"""Genera las declaraciones de las funciones de un mensaje.
	   Parametros:
	   	-file: el archivo al que escribir.
	   	-message: el elemento xml del mensaje"""

	msg_name = get_name(message)
	create_params = create_parameters(message)
	s = templates.header_signatures.format(
		msg_name=msg_name, create_parameters=create_params)
	file.write(s)

def create_parameters(message):

	"""Retorna el string de parametros de la función create de un mensaje.
	Por ejemplo: 'uint8_t x, uint16_t y [10]'.
	   Parametros:
	   	-message: el elemento xml del mensaje"""

	params = list(map(field_description, message.iter('field')))
	return ", ".join(params)

def create_parameters_passing(message):

	"""Retorna el string utilizado para pasar todos los parametros
	de la función create a ella, habiendolos recibido en la función
	actual.
	Ejemplo: int pack(uint8_t x, uint16_t y[10]){
		struct msg mensaje = create(x, y);
	}

	   Parametros:
	   	-message: el elemento xml del mensaje"""

	params = list(map(lambda x: x.text, message.iter('field')))
	return ", ".join(params)

def type_contains(field, str):

	"""Retorna verdadero si el tipo de un campo contiene un
	string particular.
	   Parametros;
	   	-field: el elemento xml del campo
	   	-str: el string en cuestión"""

	return str in field.attrib['type']

def is_array_type(field):

	"""Retorna verdadero si el tipo de field es array.
	   Parametros:
	   	-field: el elemento xml del campo"""

	return type_contains(field, '[]')

def generate_source(root, source, header_name):

	"""Genera el source file.
	   Parametros:
		-root: el elemento root del archivo xml
		-header: el objeto archivo al que escribir"""

	source.write(templates.source_includes.format(
		header_name=header_name))
	for message in root.iter('message'):
		generate_functions(source, message)
	generate_handling_functions(source, root)

def generate_functions(file, message):

	"""Genera las funciones particulares de un mensaje.
	   Parametros:
	   	-file: archivo al que escribir
	   	-message: el elemento xml del mensaje"""

	msg_name = get_name(message)
	create_params = create_parameters(message)
	ntoh = net_to_host_handling(message)
	hton = host_to_net_handling(message)
	fields_assign = fields_assignment(message)
	params_passing = create_parameters_passing(message)
	s = templates.message_functions_template.format(
		msg_name=msg_name, msg_name_upper=msg_name.upper(),
		create_parameters=create_params,
		net_to_host_handling=ntoh,
		host_to_net_handling=hton,
		fields_assignment=fields_assign,
		parameter_pass=params_passing)
	file.write(s)

def get_ntoh_converter(field):

	"""Retorna la función de conversión a usar en el o los elementos
	de un campo para ir de network byte order a host byte order.
	   Parametros:
	   	-field: el elemento xml del campo"""

	if is_uint16(field):
		return templates.uint16_ntoh
	elif is_uint32(field):
		return templates.uint32_ntoh

def get_hton_converter(field):

	"""Retorna la función de conversión a usar en el o los elementos
	de un campo para ir de host byte order a network byte order.
	   Parametros:
	   	-field: el elemento xml del campo"""

	if is_uint16(field):
		return templates.uint16_hton
	elif is_uint32(field):
		return templates.uint32_hton

def net_to_host_handling(message):

	"""Retorna el string que convierte los campos de un mensaje
	de network byte order a host byte order.
	   Parametros:
	   	-message: el elemento xml del mensaje"""

	return convert(message, get_ntoh_converter)

def host_to_net_handling(message):

	"""Retorna el string que convierte los campos de un mensaje
	de host byte order a network byte order.
	   Parametros:
	   	-message: el elemento xml del mensaje"""

	return convert(message, get_hton_converter)

def convert(message, convert_getter):

	"""Construye y retorna el string que convierte los campos de un 
	mensaje de una representación a otra (host a network o network 
	a host). Hacia qué representación se realiza la conversión 
	depende del parametro 'convert_getter', que debe ser 
	'get_ntoh_converter' o 'get_hton_converter'.
	   Parametros:
	   	-message: el elemento xml del mensaje
	   	-convert_getter: función que toma el campo de un mensaje y
	   		devuelve 'htons', 'htonl', 'ntohs' o 'ntohl', según
	   		sea pertinente. Debe ser 'get_ntoh_converter' o 
	   		'get_hton_converter'."""

	ret = ''
	for field in message.iter('field'):
		if should_be_converted(field):
			convertion = convert_getter(field)
			field_name = field.text
			if is_array_type(field):
				s = array_convertion(field_name, convertion, field)
			else:
				s = simple_field_convertion(field_name, convertion)
			ret += '\n\t' + s
	return ret

def array_convertion(field_name, convertion, field):

	"""Retorna el bloque de código que aplica la función
	'convertion' a todos los elementos de un campo de tipo
	array.
	   Parametros:
	   	-field_name: nombre del campo
	   	-convertion: función a aplicar a cada elemento. Debe ser
	   	'htons', 'htonl', 'ntohs' o 'ntohl'
	   	-field: el elemento xml del campo"""

	lng = get_len(field)
	return templates.array_field_converter.format(
					field_name=field_name, len=lng,
					convertion=convertion)

def simple_field_convertion(field_name, convertion):

	"""Retorna la linea de código que aplica la función
	'convertion' a un campo que no sea de tipo array.
	   Parametros:
	   	-field_name: nombre del campo
	   	-convertion: función a aplicar al elemento. Debe ser
	   	'htons', 'htonl', 'ntohs' o 'ntohl'"""

	return templates.simple_field_converter.format(
				field_name=field_name, convertion=convertion
			)

def should_be_converted(field):

	"""Retorna si un campo necesita ser convertido antes de ser
	transmitido por la red o al ser recibido de la misma.
	   Parametros:
	   	-field: el elemento xml del campo"""

	return is_uint16(field) or is_uint32(field)

def is_uint16(field):

	"""Retorna si un campo es de tipo entero de 16 bits, sea
	signado, no signado, array de signados o array de no signados.
	   Parametros:
	   	-field: el elemento xml del campo"""

	return type_contains(field, '16')

def is_uint32(field):

	"""Retorna si un campo es de tipo entero de 32 bits, sea
	signado, no signado, array de signados o array de no signados.
	   Parametros:
	   	-field: el elemento xml del campo"""

	return type_contains(field, '32')

def fields_assignment(message):

	"""Retorna el código que asigna a los campos de un mensaje los
	valores recibidos por parámetro en la función create.
	   Parametros:
	   	-message: el elemento xml del mensaje"""

	ret = ''
	for field in message.iter('field'):
		field_name = field.text
		if is_array_type(field):
			s = array_field_assignment(field_name, field)
		else:
			s = simple_field_assignment(field_name)
		ret += '\n\t' + s
	return ret

def array_field_assignment(field_name, field):

	"""Retorna el código que asigna a un campo de un mensaje
	cuando el campo es de tipo array usando memcpy.
	   Parametros:
	   	-field_name: nombre del campo
	   	-field: elemento xml del campo"""

	lng = get_len(field)
	field_type = get_type(field)[0:-2]
	return templates.array_field_assignment.format(
		field_name=field_name, len=lng,
		field_type=field_type)

def simple_field_assignment(field_name):

	"""Retorna el código que asigna a un campo de un mensaje
	cuando el campo no es de tipo array.
	   Parametros:
	   	-field_name: nombre del campo"""

	return templates.simple_field_assignment.format(
		field_name=field_name)

def generate_handling_functions(file, root):

	"""Genera las funciones utilizadas para manipular mensajes,
	por ejemplo, decode.
	   Parametros:
	   	-file: archivo al que escribir
	   	-root: elemento root del archivo xml"""

	switch_cases = decoder_switch_cases(root)
	s = templates.msg_handling_functions.format(
		switch_cases=switch_cases)
	file.write(s)

def decoder_switch_cases(root):

	"""Retorna el string del switch que se utilizará en la
	función decode para reconocer el tipo del mensaje y
	actual acorde.
	   Parametros:
	   	-root: elemento root del archivo xml"""

	ret = ''
	template = templates.decoder_switch_case
	for message in root.iter('message'):
		msg_name = get_name(message)
		ret += '\n\t' + template.format(
			msg_name=msg_name,
			msg_name_upper=msg_name.upper())
	return ret

def parse_cli_arguments():

	"""Parsea los parametros de consola del script."""

	parser = argparse.ArgumentParser(
		description='C protocol generator.')
	parser.add_argument('xml_source',
		help='XML definition of the protocol')
	parser.add_argument('-o', '--output',
		help='Path for the generated .c and .h files.',
		default='')
	return parser.parse_args()

def main():
	arguments = parse_cli_arguments()
	generate(arguments.xml_source, arguments.output)

if __name__ == '__main__':
	main()