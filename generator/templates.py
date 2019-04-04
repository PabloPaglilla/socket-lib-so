
header_includes = """#include <stdint.h> 
"""

source_includes = """#include <stdint.h>
#include <string.h>
#include <stdlib.h>
#include <netinet/in.h>
#include <sys/socket.h>
#include "{header_name}"

int _send_full_msg(int, uint8_t*, int);
int get_max_msg_size();
"""

header_defines = """
#ifndef PROTOCOL_H_INCLUDED
#define PROTOCOL_H_INCLUDED

"""

header_close = """
#endif"""

errors_enum = """enum errors { UNKNOWN_ID = -20, BAD_DATA,
	ALLOC_ERROR, BUFFER_TOO_SMALL, PTR_FIELD_TOO_LONG,
	CONN_CLOSED, SOCKET_ERROR = -1 };
"""

enum_definition = """enum {enum_name} {{ {values} }};
"""

msg_handling_functions_declarations = """
int decode(void*, void*, int);
int destroy(void*);
int bytes_needed_to_pack(void*);
int send_msg(int, void*);
int struct_size_from_id(uint8_t);

int pack_msg(uint16_t, void*, uint8_t*);

int recv_msg(int, void*, int);"""

message_defines_template = """
#define {msg_name_upper}_ID {msg_id}
#define {msg_name_upper}_SIZE sizeof(struct {msg_name})
"""

struct_declaration_template = """
struct {msg_name} {{
	uint8_t id;
	{field_declarations}
}};
"""

header_signatures = """
int decode_{msg_name}(void*, void*, int);
int encode_{msg_name}(void*, uint8_t*, int);
int init_{msg_name}({create_parameters} struct {msg_name}*);
void destroy_{msg_name}(void*);
int pack_{msg_name}({create_parameters} uint8_t *, int);
int send_{msg_name}({create_parameters} int);
"""

message_functions_template = """
int encoded_{msg_name}_size(void* data) {{
	struct {msg_name}* msg = (struct {msg_name}*) data;
	int encoded_size = 1;
	{add_field_sizes}
	return encoded_size;
}}

int decode_{msg_name} (void *recv_data, void* decoded_data, int max_decoded_size) {{
    
	if(max_decoded_size < sizeof(struct {msg_name})) {{
		return BUFFER_TOO_SMALL;
	}}

	uint8_t* byte_data = (uint8_t*) recv_data;
	int current = 0;
	struct {msg_name} msg;
	msg.id = byte_data[current++];
	{decode_fields}
	{network_to_host}
	memcpy(decoded_data, &msg, sizeof(struct {msg_name}));
	return 0;
}}

int encode_{msg_name}(void* msg_buffer, uint8_t* buff, int max_size) {{
	
	int encoded_size = 0;
	struct {msg_name} msg = *((struct {msg_name}*) msg_buffer);

	if((encoded_size = encoded_{msg_name}_size(&msg)) < 0) {{
		return encoded_size;
	}}
	if(encoded_size > max_size) {{
		return BUFFER_TOO_SMALL;
	}}

	{host_to_network}

	int current = 0;
	buff[current++] = msg.id;
	{encode_fields}
	{network_to_host}
	return encoded_size;
}}

int init_{msg_name}({create_parameters} struct {msg_name}* msg) {{
	msg->id = {msg_name_upper}_ID;
	{init_fields}
	return 0;
}}

void destroy_{msg_name}(void* buffer) {{
	struct {msg_name}* msg = (struct {msg_name}*) buffer;
	{destroy_fields}
}}

int pack_{msg_name}({create_parameters} uint8_t *buff, int max_size) {{
	uint8_t local_buffer[max_size - 2];
	struct {msg_name} msg;
	int error, encoded_size;
	if((error = init_{msg_name}({parameter_pass} &msg)) < 0) {{
		return error;
	}}
	if((encoded_size = encode_{msg_name}(&msg, local_buffer, max_size - 1)) < 0) {{
		destroy_{msg_name}(&msg);
		return encoded_size;
	}}
	destroy_{msg_name}(&msg);
	return pack_msg(encoded_size, local_buffer, buff);
}}

int send_{msg_name}({create_parameters} int socket_fd) {{

	int bytes_to_send, ret;
	int current_buffer_size = sizeof(struct {msg_name});
	uint8_t* local_buffer = malloc(current_buffer_size);
	if(local_buffer == NULL) {{
		return ALLOC_ERROR;
	}}

	while((bytes_to_send = pack_{msg_name}({parameter_pass} local_buffer, current_buffer_size)) == BUFFER_TOO_SMALL) {{
		current_buffer_size *= 2;
		local_buffer = realloc(local_buffer, current_buffer_size);
		if(local_buffer == NULL) {{
			return ALLOC_ERROR;
		}}
	}}

	if(bytes_to_send < 0) {{
		return bytes_to_send;
	}}

	ret = _send_full_msg(socket_fd, local_buffer, bytes_to_send);
	free(local_buffer);
	return ret;
}}
"""

add_simple_field_size = "\tencoded_size += sizeof({type});"
add_array_field_size = "\tencoded_size += sizeof({type}) * {length};"
add_string_field_size = """
	if(msg->{field_name} == NULL) {{
		return BAD_DATA;
	}}
	encoded_size += 1;
	encoded_size += strlen(msg->{field_name});
"""
add_pointer_field_size = """
	if(msg->{field_name} == NULL) {{
		return BAD_DATA;
	}}
	encoded_size += 1;
	encoded_size += msg->{field_name}_len * sizeof({type});
"""

decode_simple_field = """
	msg.{field_name} = *(({type}*) (byte_data + current));
	current += sizeof({type});"""
decode_array_field = """
	memcpy(msg.{field_name}, byte_data + current, {length} * sizeof({type}));
	current += {length} * sizeof({type});"""
decode_string_field = """
	int {field_name}_len = byte_data[current++];
	msg.{field_name} = malloc({field_name}_len + 1);
	if(msg.{field_name} == NULL){{
		{free_resources}
		return ALLOC_ERROR;
	}}
	memcpy(msg.{field_name}, byte_data + current, {field_name}_len);
	msg.{field_name}[{field_name}_len] = '\\0';
	current += {field_name}_len;"""
decode_pointer_field = """
	msg.{field_name}_len = byte_data[current++];
	msg.{field_name} = malloc(msg.{field_name}_len * sizeof({type}));
	if(msg.{field_name} == NULL) {{
		{free_resources}
		return ALLOC_ERROR;
	}}
	memcpy(msg.{field_name}, byte_data + current, msg.{field_name}_len * sizeof({type}));
	current += msg.{field_name}_len * sizeof({type});
"""
free_decode_pointer = "free(msg.{field_name});"

encode_simple_field = """
	*(({type}*)(buff + current)) = msg.{field_name};
	current += sizeof({type});"""
encode_array_field = """
	memcpy(buff + current, msg.{field_name}, {length} * sizeof({type}));
	current += {length} * sizeof({type});"""
encode_string_field = """
	int {field_name}_len = strlen(msg.{field_name});
	if({field_name}_len > 255) {{
		return PTR_FIELD_TOO_LONG;
	}}
	buff[current++] = {field_name}_len;
	memcpy(buff + current, msg.{field_name}, {field_name}_len);
	current += {field_name}_len;"""
encode_pointer_field = """
	buff[current++] = msg.{field_name}_len;
	memcpy(buff + current, msg.{field_name}, msg.{field_name}_len * sizeof({type}));
	current += msg.{field_name}_len * sizeof({type});"""

init_simple_field = "msg->{field_name} = {field_name};"
init_array_field = "\tmemcpy(msg->{field_name}, {field_name}, {length} * sizeof({type}));"
init_string_field = """
	if({field_name} == NULL) {{
		{free_resources}
		return BAD_DATA;
	}}
	msg->{field_name} = malloc(strlen({field_name}) + 1);
	if(msg->{field_name} == NULL) {{
		{free_resources}
		return ALLOC_ERROR; 
	}}
	strcpy(msg->{field_name}, {field_name});
"""
init_pointer_field = """
	if({field_name} == NULL) {{
		{free_resources}
		return BAD_DATA;
	}}
	msg->{field_name}_len = {field_name}_len;
	msg->{field_name} = malloc({field_name}_len * sizeof({type}));
	if(msg->{field_name} == NULL) {{
		{free_resources}
		return BAD_DATA;
	}}
	memcpy(msg->{field_name}, {field_name}, {field_name}_len * sizeof({type}));"""

destroy_field = "free(msg->{field_name});"

simple_field_assignment = "msg.{field_name} = {field_name};"

array_field_assignment = "memcpy(msg.{field_name}, {field_name}, {len} * sizeof({field_type}));"

array_field_converter = """for(int i = 0; i < {len}; i++) {{
		msg.{field_name}[i] = {convertion}(msg.{field_name}[i]);
	}}"""
pointer_field_converter = """for(int i = 0; i < msg.{field_name}_len; i++) {{
		msg.{field_name}[i] = {convertion}(msg.{field_name}[i]);
	}}"""

simple_field_converter = "msg.{field_name} = {convertion}(msg.{field_name});"

uint16_ntoh = "ntohs"

uint16_hton = "htons"

uint32_ntoh = "ntohl"

uint32_hton = "htonl"

field_description_template = """
{field_type} {field_name} {array_def}
"""

pointer_create_parameter = "uint8_t {field_name}_len, {field_description}"
pointer_create_parameter_pass = "{field_name}_len, {field_name}"

msg_handling_functions = """
typedef int (*decoder_t)(void*, void*, int);
typedef void (*destroyer_t)(void*);
typedef int (*encoder_t)(void*, uint8_t*, int);
typedef int (*encoded_size_getter_t)(void*);

int decode(void *data, void *buff, int max_size) {{

	uint8_t* byte_data = (uint8_t*) data;

	int msg_id = byte_data[0];
	int body_size;

	// Puntero a la función que decodifica
	decoder_t decoder;

	switch(msg_id) {{{decode_switch_cases}
		default:
			return UNKNOWN_ID;
	}}

	if(max_size < body_size) {{
		return BUFFER_TOO_SMALL;
	}}

	decoder(data, buff, body_size);

	return msg_id;
}}

int destroy(void* buffer) {{
	
	uint8_t* byte_data = (uint8_t*) buffer;
	int msg_id = byte_data[0];
	destroyer_t destroyer;

	switch(msg_id){{{destroy_switch_cases}
		default:
			return UNKNOWN_ID;
	}}

	destroyer(buffer);
	return 0;
}}

int bytes_needed_to_pack(void* buffer) {{
	
	uint8_t* byte_data = (uint8_t*) buffer;
	int msg_id = byte_data[0];
	encoded_size_getter_t size_getter;

	switch(msg_id){{{bytes_needed_switch_cases}
		default:
			return UNKNOWN_ID;
	}}

	return size_getter(buffer) + 2;
}}

int send_msg(int socket_fd, void* buffer) {{
	
	uint8_t* byte_data = (uint8_t*) buffer;
	int msg_id = byte_data[0];
	encoder_t encoder;

	switch(msg_id) {{{send_switch_cases}
		default:
			return UNKNOWN_ID;
	}}

	int packed_bytes = bytes_needed_to_pack(buffer);
	int encoded_bytes = packed_bytes - 2;
	int error;
	uint8_t encoded[encoded_bytes];
	uint8_t packed[packed_bytes];
	if((error = encoder(buffer, encoded, encoded_bytes)) < 0) {{
		return error;
	}}
	pack_msg(encoded_bytes, encoded, packed);
	return _send_full_msg(socket_fd, packed, packed_bytes);
}}

int struct_size_from_id(uint8_t msg_id) {{
	int size = 0;
	switch(msg_id){{{struct_size_switch_cases}
		default:
			return UNKNOWN_ID;
	}}
	return size;
}}

int pack_msg(uint16_t body_size, void *msg_body, uint8_t *buff) {{
	*((uint16_t*)buff) = htons(body_size);
	memcpy(buff + 2, msg_body, body_size);
	return body_size + 2;
}}

int recv_n_bytes(int socket_fd, void* buffer, int bytes_to_read) {{
	uint8_t* byte_buffer = (uint8_t*) buffer;
	int bytes_rcvd = 0;
	int num_bytes = 0;
	while(bytes_rcvd < bytes_to_read) {{
		num_bytes = recv(socket_fd, byte_buffer + bytes_rcvd, bytes_to_read - bytes_rcvd, 0);
		if(num_bytes == 0) {{
			return CONN_CLOSED;
		}} else if(num_bytes == -1) {{
			return SOCKET_ERROR;
		}}
		bytes_rcvd += num_bytes;
	}}
}}

uint16_t recv_header(int socket_fd) {{
	uint16_t header = 0;
	int error = 0;
	if((error = recv_n_bytes(socket_fd, &header, 2)) < 0) {{
		return error;
	}}
	return ntohs(header);
}}

int recv_msg(int socket_fd, void* buffer, int max_size) {{

	if(max_size < get_max_msg_size()) {{
		return BUFFER_TOO_SMALL;
	}}
	
	uint16_t msg_size = 0;
	uint8_t msg_id = 0;
	int error;
	
	if((msg_size = recv_header(socket_fd)) < 0) {{
		return msg_size;
	}}

	uint8_t local_buffer[msg_size];

	if((error = recv_n_bytes(socket_fd, local_buffer, msg_size)) < 0) {{
		return error;
	}}

	return decode(local_buffer, buffer, max_size);
}}

int _send_full_msg(int socket_fd, uint8_t* buffer, int bytes_to_send) {{
	int num_bytes, bytes_sent = 0;
	while(bytes_to_send > bytes_sent) {{
		num_bytes = send(socket_fd, buffer + bytes_sent, bytes_to_send - bytes_sent, 0);
		if(num_bytes < 1) {{
			return SOCKET_ERROR;
		}}
		bytes_sent += num_bytes;
	}}
	return bytes_sent;
}}

int get_max_msg_size() {{
	int sizes[{number_of_messages}] = {{ {struct_sizes} }};
	int max = -1;
	for(int i = 0; i < {number_of_messages}; i++) {{
		if(sizes[i] > max) {{
			max = sizes[i];
		}}
	}}
	return max;
}}
"""

struct_size = "sizeof(struct {msg_name})"

decode_switch_case = """
		case {msg_name_upper}_ID:
			decoder = &decode_{msg_name};
			body_size = sizeof(struct {msg_name});
			break;"""

destroy_switch_case = """
		case {msg_name_upper}_ID:
			destroyer = &destroy_{msg_name};
			break;"""

bytes_needed_switch_case = """
		case {msg_name_upper}_ID:
			size_getter = &encoded_{msg_name}_size;
			break;"""

send_switch_cases = """
		case {msg_name_upper}_ID:
			encoder = &encode_{msg_name};
			break;"""

struct_size_switch_case = """
		case {msg_name_upper}_ID:
			size = sizeof(struct {msg_name});
			break;"""

# Utilities

arrow_operator = "{first}->{second}"
dot_operator = "{first}.{second}"