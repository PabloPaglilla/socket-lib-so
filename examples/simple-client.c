#include <stdio.h>
#include <unistd.h>
#include <netdb.h>

#include "sockets.h"


int main(int argc, char *argv[]) {

    if(argc < 3) {
        printf("Uso: ./simple-server host puerto\n");
        return -1;
    }

    int socket_fd;
    int bytes_read;
    char* host = argv[1];
    char* port = argv[2];
    char* message = "Hello World!\n";
    char buffer[15];
    struct sockaddr_storage client_addr;
	socklen_t sin_size = sizeof client_addr;

    if((socket_fd = create_socket_client(host, port)) == -1) {
        printf("Fallo al crear el socket cliente\n");
        return -1;
    }

    printf("Conexión establecida, recibiendo...\n");

    if((bytes_read = recv(socket_fd, buffer, 14, 0)) < 1) {
        printf("El servidor cerró la conexión o hubo un error\n");
    } else {
        printf("Recibido: %s\n", buffer);
    }

    printf("Enviando\n");

    if((send(socket_fd, message, 14, 0)) != 14) {
        // Entrar en este if significa que, o el mensaje no se pudo enviar completo de una y
        // hay que encargarse de mandar lo que falta, o directamente no se pudo enviar nada.
        // No manejamos los problemas en el ejemplo, PERO EN EL TP HAY QUE HACERLO SIEMPRE.
        printf("No se envió el mensaje correctamente\n");
    }

    close(socket_fd);
    return 0;
}