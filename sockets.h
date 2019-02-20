#ifndef SOCKETS_H_INCLUDED
#define SOCKETS_H_INCLUDED

int create_socket_server(const char*, int);

int create_socket_client(const char*, const char *);

#endif