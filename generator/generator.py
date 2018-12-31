import argparse
import xml.etree.ElementTree as ET

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
	tree = ET.parse(xml_source)
	root = tree.getroot()
	header_path, source_path = get_file_paths(root, provided_path)
	generate_header(root, header_path)
	generate_source(root, source_path)

def get_file_paths(root, provided_path):
	if provided_path.endswith('/') or provided_path == '':
		base_path = provided_path + root.tag
	else:
		base_path = provided_path
	return base_path + '.h', base_path + '.c'

def _get_element_attribute(element, attribute):
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
	element_type = _get_element_attribute(element, 'type')
	if not _is_valid_type(element_type):
		raise exceptions.InvalidFieldTypeException(element_type, element)
	return element_type

def generate_header(root, header_path):
	header = open(header_path, 'w')
	header.write(templates.header_includes)
	header.write(templates.header_defines)
	generate_enum_definitions(header, root)
	for message in root.iter('message'):
		generate_msg_defines(header, message)
		generate_struct(header, message)
		generate_signatures(header, message)
	header.write(templates.msg_handling_functions_declarations)
	header.write(templates.header_close)
	header.close()

def generate_enum_definitions(file, root):
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
	msg_name = get_name(message)
	s = templates.message_defines_template.format(
		msg_name_upper=msg_name.upper(),
		msg_size = get_message_size(message))
	file.write(s)

def get_message_size(message):
	sizes = list(map(get_field_size, message.iter('field')))
	return sum(sizes)

def get_field_size(field):
	field_type = get_type(field)
	if is_array_type(field):
		type_name = field_type[0:-2]
		type_size = type_sizes[type_name]
		amount = int(get_len(field))
		return type_size * amount
	return type_sizes[field_type]

def generate_struct(file, message):
	msg_name = get_name(message)
	field_declarations = list(map(field_declaration, message.iter('field')))
	field_declarations = "\n\t".join(field_declarations)
	s = templates.struct_declaration_template.format(
		msg_name=msg_name, field_declarations=field_declarations)
	file.write(s)

def field_declaration(field):
	return field_description(field) + ';'

def field_description(field):
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
	msg_name = get_name(message)
	create_params = create_parameters(message)
	s = templates.header_signatures.format(
		msg_name=msg_name, create_parameters=create_params)
	file.write(s)

def create_parameters(message):
	params = list(map(field_description, message.iter('field')))
	return ", ".join(params)

def create_parameters_passing(message):
	params = list(map(lambda x: x.text, message.iter('field')))
	return ", ".join(params)

def is_array_type(field):
	return type_contains(field, '[]')

def generate_source(root, source_path):
	source = open(source_path, "w")
	source.write(templates.source_includes)
	for message in root.iter('message'):
		generate_functions(source, message)
	generate_handling_functions(source, root)

def generate_functions(file, message):
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

def net_to_host_handling(message):
	return convert(message, get_ntoh_converter)

def host_to_net_handling(message):
	return convert(message, get_hton_converter)

def convert(message, convert_getter):
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
	lng = get_len(field)
	return templates.array_field_converter.format(
					field_name=field_name, len=lng,
					convertion=convertion)

def simple_field_convertion(field_name, convertion):
	return templates.simple_field_converter.format(
				field_name=field_name, convertion=convertion
			)

def should_be_converted(field):
	return is_uint16(field) or is_uint32(field)

def is_uint16(field):
	return type_contains(field, '16')

def is_uint32(field):
	return type_contains(field, '32')

def type_contains(field, str):
	return str in field.attrib['type']

def get_ntoh_converter(field):
	if is_uint16(field):
		return templates.uint16_ntoh
	elif is_uint32(field):
		return templates.uint32_ntoh

def get_hton_converter(field):
	if is_uint16(field):
		return templates.uint16_hton
	elif is_uint32(field):
		return templates.uint32_hton

def fields_assignment(message):
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
	lng = get_len(field)
	field_type = get_type(field)[0:-2]
	return templates.array_field_assignment.format(
		field_name=field_name, len=lng,
		field_type=field_type)

def simple_field_assignment(field_name):
	return templates.simple_field_assignment.format(
		field_name=field_name)

def generate_handling_functions(file, root):
	switch_cases = decoder_switch_cases(root)
	s = templates.msg_handling_functions.format(
		switch_cases=switch_cases)
	file.write(s)

def decoder_switch_cases(root):
	ret = ''
	template = templates.decoder_switch_case
	for message in root.iter('message'):
		msg_name = get_name(message)
		ret += '\n\t' + template.format(
			msg_name=msg_name,
			msg_name_upper=msg_name.upper())
	return ret

def parse_cli_arguments():
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