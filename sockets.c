#include <stdio.h>
#include <string.h>
#include <errno.h>
#include <unistd.h>
#include <sys/socket.h>
#include <netdb.h>

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