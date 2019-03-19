
header_includes = """#include <stdint.h> 
"""

source_includes = """#include <stdint.h>
#include <string.h>
#include <netinet/in.h>
#include <sys/socket.h>
#include "{header_name}"
"""

header_defines = """
#ifndef PROTOCOL_H_INCLUDED
#define PROTOCOL_H_INCLUDED

"""

header_close = """
#define MAX_MSG_SIZE {max_msg_size}

#endif"""

errors_enum = """enum errors { SOCKET_ERROR = -1, UNKNOWN_ID = -10, 
	BUFFER_TOO_SMALL, MESSAGE_TOO_BIG, CONN_CLOSED };
"""

enum_definition = """enum {enum_name} {{ {values} }};
"""

msg_handling_functions_declarations = """
typedef void (*decoder_t)(void*);

int decode(void*, void*);

int pack_msg(uint8_t, uint8_t, void*, uint8_t*);

int recv_msg(int, void*, int);

int send_full_msg(int, uint8_t*, int);"""

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
int send_{msg_name}({create_parameters}, int socket_fd);
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

int send_{msg_name}({create_parameters}, int socket_fd) {{
	uint8_t local_buffer[{msg_name_upper}_SIZE + 2];
	int bytes_to_send = pack_{msg_name}({parameter_pass}, local_buffer);
	return send_full_msg(socket_fd, local_buffer, bytes_to_send);
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

	int msg_id = byte_data[0];
	uint8_t* msg_body = byte_data + 1;
	int body_size;

	// Puntero a la función que decodifica
	decoder_t decoder;

	switch(msg_id) {{{switch_cases}
		default:
			return UNKNOWN_ID;
	}}

	memcpy(buff, msg_body, body_size);

	decoder(buff);

	return msg_id;
}}

int pack_msg(uint8_t msg_id, uint8_t body_size, void *msg_body, uint8_t *buff) {{
	int msg_size = body_size + sizeof(msg_id);
	if(msg_size > 255) {{
		return MESSAGE_TOO_BIG;
	}}
	buff[0] = (uint8_t) msg_size;
	buff[1] = msg_id;
	memcpy(buff + 2, msg_body, body_size);
	return msg_size + 1;
}}

int recv_msg(int socket_fd, void* buffer, int max_size) {{
	if(max_size < MAX_MSG_SIZE) {{
		return BUFFER_TOO_SMALL;
	}}
	uint8_t* byte_buffer = (uint8_t *)buffer;
	int bytes_rcvd = 0, num_bytes, msg_size;

	num_bytes = recv(socket_fd, byte_buffer, 1, 0);
	if(num_bytes == 0) {{
		return CONN_CLOSED;
	}} else if(num_bytes == -1) {{
		return SOCKET_ERROR;
	}}
	msg_size = byte_buffer[0];

	uint8_t local_buffer[msg_size];
	while(bytes_rcvd < msg_size) {{
		num_bytes = recv(socket_fd, local_buffer + bytes_rcvd, msg_size - bytes_rcvd, 0);
		if(num_bytes == 0) {{
			return CONN_CLOSED;
		}} else if(num_bytes == -1) {{
			return SOCKET_ERROR;
		}}
		bytes_rcvd += num_bytes;
	}}

	return decode(local_buffer, byte_buffer);
}}

int send_full_msg(int socket_fd, uint8_t* buffer, int bytes_to_send) {{
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
"""

decoder_switch_case = """
		case {msg_name_upper}_ID:
			decoder = &decode_{msg_name};
			body_size = {msg_name_upper}_SIZE;
			break;"""