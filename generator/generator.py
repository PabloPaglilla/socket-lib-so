import argparse
import xml.etree.ElementTree as ET
from sys import stderr
from os import path, remove

import templates, exceptions

types = ['int8_t', 'uint8_t', 
		'int16_t', 'uint16_t',
		'int32_t', 'uint32_t',
		'char']

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

def get_id(element):
	return _get_element_attribute(element, 'id')

def _is_valid_type(element_type):
	return element_type in types or element_type[0:-2] in types or element_type[0:-1] in types

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

	max_msg_size = 0
	header.write(templates.header_includes)
	header.write(templates.header_defines)
	header.write(templates.errors_enum)
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
		msg_name=msg_name,
		msg_id=get_id(message))
	file.write(s)

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

def is_string_type(field):
	return type_contains(field, 'char*')

def is_pointer_type(field):
	return type_contains(field, '*')

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
	params_passing = create_parameters_passing(message)
	s = templates.message_functions_template.format(
		msg_name=msg_name, msg_name_upper=msg_name.upper(),
		create_parameters=create_params,
		network_to_host=ntoh,
		host_to_network=hton,
		parameter_pass=params_passing,
		add_field_sizes=add_field_sizes(message),
		decode_fields=decode_fields(message),
		encode_fields=encode_fields(message),
		destroy_fields=destroy_fields(message),
		init_fields=init_fields(message))
	file.write(s)

def add_field_sizes(message):
	return '\n'.join(list(map(add_field_size, message.iter('field'))))

def add_field_size(field):
	if is_array_type(field):
		return templates.add_array_field_size.format(
			type=get_type(field)[0:-2], length=get_len(field))
	elif is_string_type(field):
		return templates.add_string_field_size.format(
			field_name=field.text)
	else:
		return templates.add_simple_field_size.format(
			type=get_type(field))

def decode_fields(message):
	pointers_to_free_on_error = []
	field_decodes = []
	for field in message.iter('field'):
		field_decodes.append(decode_field(field, pointers_to_free_on_error))
	return ''.join(field_decodes)

def decode_field(field, pointers_to_free_on_error):
	if is_array_type(field):
		return templates.decode_array_field.format(
			field_name=field.text,
			type=get_type(field)[0:-2],
			length=get_len(field))
	elif is_string_type(field):
		ret = templates.decode_string_field.format(
			field_name=field.text,
			free_resources=free_decode_pointers(pointers_to_free_on_error))
		pointers_to_free_on_error.append(field.text)
		return ret
	else:
		return templates.decode_simple_field.format(
			field_name=field.text,
			type=get_type(field))

def free_decode_pointers(pointers_to_free_on_error):
	return '\n'.join(
		list(
			map(
				lambda x: templates.free_decode_pointer.format(field_name=x),
				pointers_to_free_on_error
			)
		)
	)

def encode_fields(message):
	return '\n'.join(list(map(encode_field, message.iter('field'))))

def encode_field(field):
	if is_array_type(field):
		return templates.encode_array_field.format(
			field_name=field.text,
			type=get_type(field)[0:-2],
			length=get_len(field),
			host_to_network='')
	elif is_string_type(field):
		return templates.encode_string_field.format(
			field_name=field.text)
	else:
		return templates.encode_simple_field.format(
			field_name=field.text,
			type=get_type(field),
			host_to_network='')

def init_fields(message):
	pointers_to_free_on_error = []
	field_inits = []
	for field in message.iter('field'):
		field_inits.append(init_field(field, pointers_to_free_on_error))
	return '\n'.join(field_inits)

def init_field(field, pointers_to_free_on_error):
	if is_array_type(field):
		return templates.init_array_field.format(
			field_name=field.text,
			type=get_type(field)[0:-2],
			length=get_len(field))
	elif is_string_type(field):
		ret = templates.init_string_field.format(
			field_name=field.text,
			free_resources=free_init_pointers(pointers_to_free_on_error))
		pointers_to_free_on_error.append(field.text)
		return ret
	else:
		return templates.init_simple_field.format(field_name=field.text)

def free_init_pointers(pointers_to_free_on_error):
	return '\n'.join(list(map(
				lambda x: templates.destroy_field.format(field_name=x),
				pointers_to_free_on_error
			)))	

def destroy_fields(message):
	l = []
	for field in message.iter('field'):
		if is_pointer_type(field):
			l.append(destroy_field(field))
	return '\n\t'.join(l)

def destroy_field(field):
	return templates.destroy_field.format(field_name=field.text)

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

def generate_handling_functions(file, root):

	"""Genera las funciones utilizadas para manipular mensajes,
	por ejemplo, decode.
	   Parametros:
	   	-file: archivo al que escribir
	   	-root: elemento root del archivo xml"""

	s = templates.msg_handling_functions.format(
		decode_switch_cases=decode_switch_cases(root),
		destroy_switch_cases=destroy_switch_cases(root),
		bytes_needed_switch_cases=bytes_needed_switch_cases(root),
		struct_size_switch_cases=struct_size_switch_cases(root),
		number_of_messages=len(list(root.iter('message'))),
		struct_sizes=(',\n' + '\t'*5).join(list(map(get_struct_sizeof, root.iter('message')))))
	file.write(s)

def decode_switch_cases(root):
	return switch_cases(root, templates.decode_switch_case)	

def destroy_switch_cases(root):
	return switch_cases(root, templates.destroy_switch_case)

def bytes_needed_switch_cases(root):
	return switch_cases(root, templates.bytes_needed_switch_case)

def struct_size_switch_cases(root):
	return switch_cases(root, templates.struct_size_switch_case)

def switch_cases(root, template):

	ret = ''
	for message in root.iter('message'):
		msg_name = get_name(message)
		ret += '\n\t' + template.format(
			msg_name=msg_name,
			msg_name_upper=msg_name.upper())
	return ret

def get_struct_sizeof(message):
	return templates.struct_size.format(msg_name=get_name(message))

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