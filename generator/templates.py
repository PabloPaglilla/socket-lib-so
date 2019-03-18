
header_includes = """#include <stdint.h> 
"""

source_includes = """#include <stdint.h>
#include <string.h>
#include <netinet/in.h>
#include "{header_name}"
"""

header_defines = """
#ifndef PROTOCOL_H_INCLUDED
#define PROTOCOL_H_INCLUDED

"""

header_close = "\n#endif"

enum_definition = """enum {enum_name} {{ {values} }};
"""

msg_handling_functions_declarations = """
typedef void (*decoder_t)(void*);

int decode(void*, void*);

int pack_msg(uint8_t, uint8_t, void*, uint8_t*);"""

message_defines_template = """
#define {msg_name_upper}_ID 0
#define {msg_name_upper} "test_msg"
#define {msg_name_upper}_SIZE {msg_size}
"""

struct_declaration_template = """
struct {msg_name} {{
	{field_declarations}
}} __attribute__((packed));
"""

header_signatures = """
void decode_{msg_name} (void *);
void encode_{msg_name} (struct {msg_name} *);
struct {msg_name} create_{msg_name}({create_parameters});
int pack_{msg_name}({create_parameters}, uint8_t *buff);
"""

message_functions_template = """
void decode_{msg_name} (void *recv_data) {{
    struct {msg_name} *msg = (struct {msg_name} *)recv_data;
	{net_to_host_handling}
}}

void encode_{msg_name}(struct {msg_name}* msg) {{
	{host_to_net_handling}
}}

struct {msg_name} create_{msg_name}({create_parameters}) {{
	struct {msg_name} msg;
	{fields_assignment}
	return msg;
}}

int pack_{msg_name}({create_parameters}, uint8_t *buff) {{
	struct {msg_name} p = create_{msg_name}({parameter_pass});
	encode_{msg_name}(&p);
	return pack_msg({msg_name_upper}_ID, {msg_name_upper}_SIZE, &p, buff);
}}
"""

simple_field_assignment = "msg.{field_name} = {field_name};"

array_field_assignment = "memcpy(msg.{field_name}, {field_name}, {len} * sizeof({field_type}));"

array_field_converter = """for(int i = 0; i < {len}; i++) {{
		msg->{field_name}[i] = {convertion}(msg->{field_name}[i]);
	}}"""

simple_field_converter = "msg->{field_name} = {convertion}(msg->{field_name});"

uint16_ntoh = "ntohs"

uint16_hton = "htons"

uint32_ntoh = "ntohl"

uint32_hton = "htonl"

field_description_template = """
{field_type} {field_name} {array_def}
"""

msg_handling_functions = """
int decode(void *data, void *buff) {{

	uint8_t* byte_data = (uint8_t*) data;

	int msg_id = byte_data[1];
	uint8_t* msg_body = byte_data + 2;
	int body_size;

	// Puntero a la función que decodifica
	decoder_t decoder;

	switch(msg_id) {{{switch_cases}
		default:
			return -1;
	}}

	memcpy(buff, msg_body, body_size);

	decoder(buff);

	return msg_id;
}}

int pack_msg(uint8_t msg_id, uint8_t body_size, void *msg_body, uint8_t *buff) {{
	int msg_size = body_size + sizeof(msg_id);
	if(msg_size > 255) {{
		return -1;
	}}
	buff[0] = (uint8_t) msg_size;
	buff[1] = msg_id;
	memcpy(buff + 2, msg_body, body_size);
	return msg_size + 1;
}}
"""

decoder_switch_case = """
		case {msg_name_upper}_ID:
			decoder = &decode_{msg_name};
			body_size = {msg_name_upper}_SIZE;
			break;"""