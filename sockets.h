#ifndef SOCKETS_H_INCLUDED
#define SOCKETS_H_INCLUDED

#include <pthread.h>

// Puntero a una función que se utilizará para manejar eventos
// específicos que ocurran en un servidor.
typedef int (*handler_t)(int, void*);

// Retornos de los handlers, los cuales serán interpretados por el
// servidor.
enum handler_return { CLOSE_CLIENT = 10 };

// Estructura que define los handlers que utilizará un servidor.
// on_new_client será llamada cuando se produzca una nueva conexión,
// recibiendo el file descriptor del nuevo cliente y los datos compartidos
// del servidor.
// on_can_read será llamada cuando pueda leerse de un cliente. Recibirá
// el file descriptor del cliente y los datos compartidos del servidor.
// Deberá retornar CLOSE_CLIENT si el cliente cerró la conexión.
struct handler_set {
	handler_t on_new_client;
	handler_t on_can_read;
};

// Estructura de entrada para un servidor. Contiene un mutex,
// el flag should_stop para señalizar al servidor que debe
// finalizar, el file descriptor del servidor (resultado de
// create_socket_server()), una estructura handler_set 
// (que contiene los handlers asociados al servidor) y un void*
// con cualquier información que quiera compartirse con los handlers.
struct server_input {
	pthread_mutex_t lock;
	int should_stop;
	int server_fd;
	struct handler_set handlers;
	void* shared_data;
};

int create_socket_server(const char*, int);

int create_socket_client(const char*, const char *);

void init_server_input(struct server_input*, int, struct handler_set, void*);

int start_server(pthread_t*, struct server_input*);

void stop_server_and_join(pthread_t, struct server_input*);

#endif