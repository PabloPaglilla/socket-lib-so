#include <stdio.h>
#include <unistd.h>
#include <netdb.h>

#include "sockets.h"

#define BACKLOG 10

int main(int argc, char *argv[]) {

    if(argc < 2) {
        printf("Uso: ./simple-server puerto\n");
        return -1;
    }

    int server_fd, client_fd;
    int bytes_read;
    char* port = argv[1];
    char* message = "Hello World!\n";
    char buffer[15];
    struct sockaddr_storage client_addr;
	socklen_t sin_size = sizeof client_addr;

    if((server_fd = create_socket_server(port, BACKLOG)) == -1) {
        printf("Fallo al crear el socket servidor\n");
        return -1;
    }

    if((client_fd = accept(server_fd, (struct sockaddr*) &client_addr, &sin_size)) == -1) {
        printf("Fallo al aceptar al cliente\n");
        close(server_fd);
        return -1;
    }

    printf("Conexión establecida, enviando...\n");

    if((send(client_fd, message, 14, 0)) != 14) {
        // Entrar en este if significa que, o el mensaje no se pudo enviar completo de una y
        // hay que encargarse de mandar lo que falta, o directamente no se pudo enviar nada.
        // No manejamos los problemas en el ejemplo, PERO EN EL TP HAY QUE HACERLO SIEMPRE.
        printf("No se envió el mensaje correctamente\n");
    }

    printf("Recibiendo\n");

    if((bytes_read = recv(client_fd, buffer, 14, 0)) < 1) {
        printf("El cliente cerró la conexión o hubo un error\n");
    } else {
        printf("Recibido: %s\n", buffer);
    }

    close(client_fd);
    close(server_fd);
    return 0;
}