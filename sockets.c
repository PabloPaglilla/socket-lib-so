#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <unistd.h>
#include <sys/socket.h>
#include <netdb.h>
#include <sys/epoll.h>
#include <pthread.h>

#include "sockets.h"

#define MAX_EPOLL_EVENTS 10
#define EPOLL_TIMEOUT 1000

int get_local_addrinfo(const char* port, struct addrinfo* hints, struct addrinfo** server_info) {

	// Wrapper para getaddrinfo cuando se busca la addrinfo propia

	int ret;
	if((ret = getaddrinfo(NULL, port, hints, server_info)) != 0) {
		fprintf(stderr, "At getaddrinfo():\n\t%s\n", gai_strerror(ret));
		return -1;
	}
	return 0;
}

int get_socket(const struct addrinfo* addr) {

	// Recibe un addrinfo y retorna el file descriptor de un socket
	// asociado a ella

	int socket_fd = socket(addr->ai_family,
		addr->ai_socktype,
		addr->ai_protocol);
	if (socket_fd == -1) {
		fprintf(stderr, "Error at socket(). Errno: %d", errno);
	}
	return socket_fd;
}

int get_binded_socket(const struct addrinfo* possible_addrinfo) {

	// Recibe un addr info e intenta crear un socket asociado
	// a ella y después bindearlo

	int socket_fd;

	if((socket_fd = get_socket(possible_addrinfo)) == -1) {
		return -1;
	}

	if(bind(socket_fd, possible_addrinfo->ai_addr,
			possible_addrinfo->ai_addrlen) == -1) {
		close(socket_fd);
		fprintf(stderr, "Error at bind(). Errno: %d", errno);
		return -1;
	}

	return socket_fd;
}

int get_connected_socket(const struct addrinfo* possible_addrinfo) {

	// Recibe un addrinfo e intenta crear un socket asociado
	// a ella y después conectarlo

	int socket_fd;

	if((socket_fd = get_socket(possible_addrinfo)) == -1) {
		return -1;
	}

	if(connect(socket_fd, 
			possible_addrinfo->ai_addr, 
			possible_addrinfo->ai_addrlen) == -1) {
		close(socket_fd);
		fprintf(stderr, "Error at connect(). Errno: %d", errno);
		return -1;
	}

	return socket_fd;
}

int loop_addrinfo_list(struct addrinfo* linked_list,
		int (*get_socket) (const struct addrinfo*)) {

	// Recibe una lista enlazada resultado de getaddrinfo y un puntero 
	// a una función. La función debe tomar un addrinfo y devolver
	// un socket o -1 si hubo un error.
	// Retorna el primer socket que pueda obtenerse sin error
	// a partir de un addrinfo de la lista enlazada. Si 
	// no puede obtenerse ningun socket, informa el error y retorna -1.

	struct addrinfo* p;
	int socket_fd;

	for(p = linked_list; p != NULL; p = p->ai_next) {
		if((socket_fd = get_socket(p)) != -1) {
			return socket_fd;
		}
	}

	fprintf(stderr, "Couldn't find valid address for host.");
	return -1;
}

int create_socket_server(const char* port, int backlog) {

	// Recibe un puerto y un backlog. Crea y devuelve el file descriptor
	// de un socket TCP que escucha en ese puerto con dicho backlog. Retorna
	// -1 en caso de error.

	int socket_fd;
	struct addrinfo hints, *server_info;

	memset(&hints, 0, sizeof hints);
	hints.ai_family = AF_UNSPEC;
	hints.ai_socktype = SOCK_STREAM;
	hints.ai_flags = AI_PASSIVE;

	if(get_local_addrinfo(port, &hints, &server_info) != 0){
		return -1;
	}

	if((socket_fd = loop_addrinfo_list(server_info, &get_binded_socket)) == -1) {
		return -1;
	}

	freeaddrinfo(server_info);

	if(listen(socket_fd, backlog) == -1) {
		fprintf(stderr, "Error at listen(). Errno: %d", errno);
		return -1;
	}

	return socket_fd;
}

int create_socket_client(const char* host, const char* port) {

	// Recibe un host y un puerto. Retorna un socket TCP conectado
	// a la direccion host:puerto o -1 en caso de error.

	int socket_fd;
	struct addrinfo hints, *server_info;
	int ret;

	memset(&hints, 0, sizeof hints);
	hints.ai_family = AF_UNSPEC;
	hints.ai_socktype = SOCK_STREAM;

	if((ret = getaddrinfo(host, port, &hints, &server_info)) != 0) {
		fprintf(stderr, "At getaddrinfo():\n\t%s\n", gai_strerror(ret));
		return -1;		
	}

	if((socket_fd = loop_addrinfo_list(server_info, &get_connected_socket)) == -1) {
		return -1;
	}

	freeaddrinfo(server_info);

	return socket_fd;
}

int run_handler(handler_t handler, int socket_fd) {
	if(handler != NULL) {
		return handler(socket_fd);
	}
	return -1;
}

void init_server_input(struct server_input* input,
		int server_fd, struct handler_set handlers) {
	pthread_mutex_init(&input->lock, NULL);
	input->should_stop = 0;
	input->server_fd = server_fd;
	input->handlers = handlers;
}

int thread_should_stop(struct server_input* input) {
	pthread_mutex_lock(&input->lock);
	int stop = input->should_stop;
	pthread_mutex_unlock(&input->lock);
	printf("Should stop: %d\n", stop);
	return stop;
}

struct clients_storage {
	int* clients;
	int numClients;
	int maxClients;
};

struct clients_storage init_clients_storage() {
	struct clients_storage storage;
	storage.clients = NULL;
	storage.numClients = 0;
	storage.maxClients = 0;
	return storage;
}

int add_client(struct clients_storage* storage, int client) {
	if(!(storage->numClients < storage->maxClients)) {
		int* new_buf = realloc(storage->clients, storage->maxClients * 2);
		if (new_buf == NULL) {
			return -1;
		}
		storage->clients = new_buf;
		storage->maxClients *= 2;
	}
	storage->clients[storage->numClients] = client;
	storage->numClients++;
	return 0;
}

void remove_client(struct clients_storage* storage, int client) {
	for(int i = 0; i < storage->numClients; i++) {
		if(client == storage->clients[i]) {
			for(int j = i + 1; j < storage->numClients; j++) {
				storage->clients[j - 1] = storage->clients[j];
			}
			break;
		}
	}
	storage->numClients--;
}

void clear_clients(struct clients_storage storage) {
	for(int i = 0; i < storage.numClients; i++) {
		close(storage.clients[i]);
	}
	free(storage.clients);
}

int add_epoll_fd(int epoll_fd, int socket_fd) {
	struct epoll_event event;
	event.events = EPOLLIN;
	event.data.fd = socket_fd;
	if(epoll_ctl(epoll_fd, EPOLL_CTL_ADD, socket_fd, &event) == -1) {
		fprintf(stderr, "Couldn't add file descriptor to epoll. Errno: %d\n", errno);
		return -1;
	}
	return 0;
}

void accept_new_client(int server_fd, int epoll_fd, 
		struct clients_storage* storage, struct handler_set handlers) {

	struct sockaddr_storage client_addr;
	socklen_t sin_size = sizeof client_addr;
	int new_client;

	if((new_client = accept(server_fd, (struct sockaddr*) &client_addr, &sin_size)) == -1) {
		fprintf(stderr, "Error accepting client. Errno: %d\n", errno);
		return;
	}

	switch(run_handler(handlers.on_new_client, new_client)) {
		case CLOSE_CLIENT:
			close(new_client);
			break;
		default:
			if(add_epoll_fd(epoll_fd, new_client) == -1) {
				// Si no se puede registrar el cliente en epoll,
				// se cierra la conección
				close(new_client);
			} else {
				add_client(storage, new_client);	
			}
	}
}

void handle_data_from_client(int client_fd, 
		struct clients_storage* storage, struct handler_set handlers) {

	switch(run_handler(handlers.on_can_read, client_fd)) {
		case CLOSE_CLIENT:
			remove_client(storage, client_fd);
			// Cerrar el file descriptor lo remueve automáticamente
			// de los descriptors registrados de epoll, no es necesario
			// removerlos a mano.
			close(client_fd);
			break;
	}
}

void* run_server(void * input) {

	struct server_input* data = (struct server_input*) input;
	int server_fd = data->server_fd;
	struct handler_set handlers = data->handlers;
	struct epoll_event events[MAX_EPOLL_EVENTS];
	struct clients_storage storage = init_clients_storage();
	int epoll_event_count, epoll_fd = epoll_create1(0);

	if(epoll_fd == -1) {
		fprintf(stderr, "Couldn't get epoll file descriptor. Errno: %d\n", errno);
	}

	if(add_epoll_fd(epoll_fd, server_fd) == -1) {
		close(epoll_fd);
		return NULL;
	}

	while(!thread_should_stop(data)) {
		epoll_event_count = epoll_wait(epoll_fd, events, 
			MAX_EPOLL_EVENTS, EPOLL_TIMEOUT);
		for(int i = 0; i < epoll_event_count; i++) { 
			int socket_fd = events[i].data.fd;
			if(socket_fd == server_fd) {
				accept_new_client(server_fd, epoll_fd, &storage, handlers);
			} else {
				handle_data_from_client(socket_fd, &storage, handlers);
			}
		}
	}

	clear_clients(storage);
	close(epoll_fd);
}