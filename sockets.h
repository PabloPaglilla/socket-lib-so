#ifndef SOCKETS_H_INCLUDED
#define SOCKETS_H_INCLUDED

typedef int (*handler_t)(int);

enum handler_return { CLOSE_CLIENT = 10 };

struct handler_set {
	handler_t on_new_client;
	handler_t on_can_read;
};

struct server_input {
	pthread_mutex_t lock;
	int should_stop;
	int server_fd;
	struct handler_set handlers;
};

int create_socket_server(const char*, int);

int create_socket_client(const char*, const char *);

void init_server_input(struct server_input*, int, struct handler_set);

void* run_server(void*);

#endif