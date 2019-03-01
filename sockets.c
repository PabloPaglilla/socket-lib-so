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
		fprintf(stderr, "Error at socket(). Errno: %d\n", errno);
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
		fprintf(stderr, "Error at bind(). Errno: %d\n", errno);
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
		fprintf(stderr, "Error at connect(). Errno: %d\n", errno);
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

	fprintf(stderr, "Couldn't find valid address for host.\n");
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
		close(socket_fd);
		fprintf(stderr, "Error at listen(). Errno: %d\n", errno);
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

int run_handler(handler_t handler, int socket_fd, void* shared_data) {

	// Toma un handler_t y sus parámetros. Si el handler no es nulo,
	// lo ejecuta y retorna el resultado. De ser nulo, retorna 0;

	if(handler != NULL) {
		return handler(socket_fd, shared_data);
	}
	return 0;
}

void init_server_input(struct server_input* input,
		int server_fd, struct handler_set handlers,
		void* shared_data) {

	// Inicializa una estructura server_input. Toma un puntero a una
	// instancia de esta y sus campos server_fd, handlers y shared_data.
	// Asigna lo recibido a los campos correspondientes de input e 
	// inicializa el mutex junto con el flag de paro.

	pthread_mutex_init(&input->lock, NULL);
	input->should_stop = 0;
	input->server_fd = server_fd;
	input->handlers = handlers;
	input->shared_data = shared_data;
}

int thread_should_stop(struct server_input* input) {

	// Toma un puntero a una estructura server_input y retorna
	// si el servidor asociado debe finalizar o no.

	pthread_mutex_lock(&input->lock);
	int stop = input->should_stop;
	pthread_mutex_unlock(&input->lock);
	return stop;
}

void stop_server(struct server_input* input) {
	pthread_mutex_lock(&input->lock);
	input->should_stop = 1;
	pthread_mutex_unlock(&input->lock);
}

struct clients_storage {

	// Estructura para almacenar dinámicamente los clientes
	// del servidor.

	int* clients_buff;
	int num_clients;
	int max_clients;
};

struct clients_storage init_clients_storage() {

	// Inicializa y retorna una estructura clients_storage

	struct clients_storage clients;
	clients.clients_buff = malloc((sizeof(int)) * 2);
	clients.num_clients = 0;
	clients.max_clients = 2;
	return clients;
}

int add_client(struct clients_storage* clients, int client) {

	// Agrega el cliente client a la estructura clients_storate clients.
	// De ser necesario, aumenta el tamaño del buffer de la estructura.

	if(!(clients->num_clients < clients->max_clients)) {
		int* new_buf = realloc(clients->clients_buff, clients->max_clients * 2);
		if (new_buf == NULL) {
			fprintf(stderr, "Couldn't allocate memory for clients.\n");
			return -1;
		}
		clients->clients_buff = new_buf;
		clients->max_clients *= 2;
	}
	clients->clients_buff[clients->num_clients] = client;
	clients->num_clients++;
	return 0;
}

void remove_client(struct clients_storage* clients, int client) {

	// Remueve el cliente client a la estructura clients_storate clients.

	for(int i = 0; i < clients->num_clients; i++) {
		if(client == clients->clients_buff[i]) {
			for(int j = i + 1; j < clients->num_clients; j++) {
				clients->clients_buff[j - 1] = clients->clients_buff[j];
			}
			clients->num_clients--;
			break;
		}
	}
}

void clear_clients(struct clients_storage cliets) {

	// Recibe una estructura clients_storage. Cierra todas sus conexiones
	// y libera el buffer de clientes.

	for(int i = 0; i < cliets.num_clients; i++) {
		close(cliets.clients_buff[i]);
	}
	free(cliets.clients_buff);
}

int add_epoll_fd(int epoll_fd, int socket_fd) {

	// Recibe un file descriptor asociado a una instancia de epoll y 
	// otro file descriptor asociado a un socket. Registra el socket
	// en la instancia de epoll. Retorna 0 en caso de exito, -1 en
	// caso contrario.

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
		struct clients_storage* clients, struct server_input* input) {

	// Acepta a un nuevo cliente. Recibe el file descriptor del servidor,
	// el de la instancia de epoll, un puntero a la estructura de clientes
	// y un puntero a la estructura input del servidor.
	// Acepta la conexión y ejecuta el handler correspondiente de estar
	// definido. Luego:
	//				- Si el handler le indico retornando CLOSE_CLIENT,
	// cierra la conexión del cliente.
	//				- Si el handler retorna STOP_SERVER, se finalizará
	// el thread del servidor.
	//				- Si el handler retorna otra cosa, intenta
	// agregar el cliente tanto a los clientes como al registro de
	// epoll. En caso de error, cierra la conexión. 

	struct sockaddr_storage client_addr;
	socklen_t sin_size = sizeof client_addr;
	int new_client, ret;

	if((new_client = accept(server_fd, (struct sockaddr*) &client_addr, &sin_size)) == -1) {
		fprintf(stderr, "Error accepting client. Errno: %d\n", errno);
		return;
	}

	pthread_mutex_lock(&input->lock);
	ret = run_handler(input->handlers.on_new_client, new_client, input->shared_data);
	pthread_mutex_unlock(&input->lock);

	switch(ret) {
		case CLOSE_CLIENT:
			close(new_client);
			break;
		case STOP_SERVER:
			close(new_client);
			stop_server(input);
			break;
		default:
			// Si hay algun error al intentar agregar el cliente
			// a la lista de clientes o al registrar el file 
			// descriptor a epoll, cerramos la conexión.
			if(add_client(clients, new_client) == -1) {
				close(new_client);
				return;
			}
			if(add_epoll_fd(epoll_fd, new_client) == -1) {
				close(new_client);
				remove_client(clients, new_client);
				return;
			}
	}
}

void handle_data_from_client(int client_fd, 
		struct clients_storage* cliets, struct server_input* input) {

	// Se ejecuta cuando un file descriptor está listo para leer.
	// Recibe dicho file descriptor, los clientes y el input del
	// servidor. Ejecuta el handler correspondiente de existir y;
	// si este lo indica retornando CLOSE_CLIENT, cierra la conexión
	// y remueve al cliente de los registros; si retorna STOP_SERVER,
	// se finalizará el thread del servidor.

	pthread_mutex_lock(&input->lock);
	int ret = run_handler(input->handlers.on_can_read, client_fd, input->shared_data);
	pthread_mutex_unlock(&input->lock);

	switch(ret) {
		case CLOSE_CLIENT:
			remove_client(cliets, client_fd);
			// Cerrar el file descriptor lo remueve automáticamente
			// de los descriptors registrados de epoll, no es necesario
			// removerlos a mano.
			close(client_fd);
			break;
		case STOP_SERVER:
			stop_server(input);
			break;
	}
}

void* run_server(void * data) {

	// Corre un servidor. Debe ejecutarse en un thread nuevo, recibiendo
	// como parámetro un puntero a una estructura server_input.
	// Utiliza epoll para multiplexar la entrada. Maneja los nuevos clientes
	// y aquellos listos para la lectura manteniendo un registro de ellos
	// y llamando a los handlers correspondientes provistos por medio del
	// server_input.

	// Cuando el servidor es señalizado que tiene que finalizar a través
	// de su server_input; cierra todas las conexiones, al igual que el
	// file descriptor asociado a la instancia de epoll, y retorna. 

	struct server_input* input = (struct server_input*) data;

	pthread_mutex_lock(&input->lock);
	int server_fd = input->server_fd;;
	pthread_mutex_unlock(&input->lock);

	struct epoll_event events[MAX_EPOLL_EVENTS];
	struct clients_storage cliets = init_clients_storage();
	int epoll_event_count, epoll_fd = epoll_create1(0);

	if(epoll_fd == -1) {
		fprintf(stderr, "Couldn't get epoll file descriptor. Errno: %d\n", errno);
	}

	if(add_epoll_fd(epoll_fd, server_fd) == -1) {
		close(epoll_fd);
		return NULL;
	}

	while(!thread_should_stop(input)) {
		epoll_event_count = epoll_wait(epoll_fd, events, 
			MAX_EPOLL_EVENTS, EPOLL_TIMEOUT);
		for(int i = 0; i < epoll_event_count; i++) { 
			int socket_fd = events[i].data.fd;
			if(socket_fd == server_fd) {
				accept_new_client(server_fd, epoll_fd, &cliets, input);
			} else {
				handle_data_from_client(socket_fd, &cliets, input);
			}
		}
	}

	clear_clients(cliets);
	close(epoll_fd);
}

int start_server(pthread_t* thread, struct server_input* input) {

	// Recibe un punteros a un pthread_t y a una estructura server_input.
	// Iniacializa el thread para correr la función run_server con la entrada
	// provista. Retorna -1 en caso de error, 0 en caso de éxito.

	int ret;
	if((ret = pthread_create(thread, NULL, &run_server, input)) != 0) {
		fprintf(stderr, "Couldn't start server thread, error at pthread_create(). Error code: %d\n", ret);
		return -1;
	}
	return 0;
}

void stop_server_and_join(pthread_t server_thread, struct server_input* input) {

	// Recibe un thread inicializado con start_server() y el input del servidor
	// asociado. Finaliza el servidor y ejecuta pthread_join() en el thread.

	stop_server(input);
	pthread_join(server_thread, NULL);
}