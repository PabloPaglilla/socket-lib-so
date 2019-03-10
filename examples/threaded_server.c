#include <stdio.h>
#include <unistd.h>
#include <pthread.h>
#include <netdb.h>

#include "sockets.h"

#define BACKLOG 10

char* message = "Hello World!\n";
int msg_len = 14;

int new_client(int client_fd, void* shared_data) {
    send(client_fd, message, 14, 0);
    return 0;
}

int handle_data(int client_fd, void* shared_data) {
    int bytes_recv;
    char buffer[msg_len];

    if((bytes_recv = recv(client_fd, buffer, msg_len, 0)) == 0) {
        // Leer readme para saber el por qué de este return
        return CLOSE_CLIENT;
    }

    printf("Recibido del socket %d\n\t %s", client_fd, buffer);
    return 0;
}

int main(int argc, char* argv[]){

    if(argc < 2) {
        printf("Uso: ./threaded_server puerto\n");
        return -1;
    }

    char* port = argv[1];
    pthread_t server_thread;

    int server_fd = create_socket_server(port, BACKLOG);

    struct handler_set handlers;
    handlers.on_new_client = &new_client;
    handlers.on_can_read = &handle_data;

    struct server_input input;
    init_server_input(&input, server_fd, handlers, NULL);

    printf("Inicializando el servidor\n");
    start_server(&server_thread, &input);
    sleep(10);
    stop_server_and_join(server_thread, &input);
    printf("Servidor finalizado\n");

    close(server_fd);
    return 0;

}