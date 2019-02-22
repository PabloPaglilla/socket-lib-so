# Socket-lib-so
Librería de sockets TCP para Sistemas Operativos 2019. UTN-FRBA.

## Funcionalidad

La librería posee dos funcionalidades principales:

* Crear un socket TCP, sea un servidor ya escuchando o un cliente ya conectado, mediante las funciones `create_socket_server()` y 
`create_socket_client()`.
* Instanciar un servidor concurrente en un nuevo thread a partir de un socket obtenido con `create_socket_server()` mediante la función 
`start_server()`, brindando funciones para manejar nuevos clientes y datos entrantes.

## Uso

### Crear un servidor con `create_socket_server()`

``` C
int create_socket_server(const char* port, int backlog);
```

La función recibe como parámetros el puerto al cual se quiere bindear el servidor y el backlog. Retorna un file descriptor
asociado a un socket TCP que se encuentra escuchando en el puerto especificado o -1 en caso de error.

#### Ejemplo

``` C
#define PORT "9000"
#define BACKLOG 10

int server_fd;

if((server_fd = create_socket_server(PORT, BACKLOG)) == -1) {
  fprintf(stderr, "Socket error\n");
  return -1;
}
```

### Crear un cliente con `create_socket_client()`

``` C
int create_socket_client(const char* host, const char* port);
```

La función recibe como parámetros el host y el puerto al cual conectarse. Retorna el file descriptor asociado a un socket TCP
que se encuentra conectado a la dirección `host:port` o -1 en caso de error.

#### Ejemplo

``` C
#define HOST "127.0.0.1"
#define PORT "9000"

int socket_fd;

if((socket_fd = create_socket_client(HOST, PORT)) == -1) {
  fprintf(stderr, "Socket error\n");
  return -1;
}
```
### Crear un servidor concurrente

#### Concepto previo: el tipo `handler_t`

``` C
typedef int (*handler_t)(int, void*);
```

El tipo `handler_t` es un puntero a una función que recibe un `int` y un `void*` y retorna un `int`.

De este tipo son las funciones que se le brindarán al servidor para que ejecute cada vez que se conecta un cliente nuevo
o ha llegado información de alguno de estos. El primer parámetro que recibirán será el file descriptor del cliente en cuestión,
mientras que el segundo será un puntero a cualquier dato compartido con el servidor que se haya definido (más info más adelante).

Estás funciones pueden retornar un elemento de la siguiente enumeración:

``` C
enum handler_return { CLOSE_CLIENT = 10, STOP_SERVER};
```

* Al retornar `CLOSE_CLIENT`, el servidor cerrará la conexión con el cliente en cuestión luego de la ejecución del handler_t.
* Al retornar `STOP_SERVER`, el thread del servidor finalizará luego de manejar los eventos de clientes pendientes.

#### Concepto previo: la estructura `handler_set`

``` C
struct handler_set {
  handler_t on_new_client;
  handler_t on_can_read;
}
```

Esta estructura es uno de los datos que recibirá el servidor. Contiene los dos handlers a utilizar. El servidor ejecutará
`on_new_client()` cuando llegue un nuevo clientes y `on_can_read()` cuando hayan datos que leer de un cliente.

**Nota**

Cuando un cliente cierre la conexión se registrará que está listo para lectura, pero `recv()` retornará 0. Si bien
esto indica que el cliente cerró la conexión, el servidor no maneja automáticamente la situación y cierra el socket.
Es por eso que `on_can_read()` debe retornar `CLOSE_CIENT` cuando esto sucede.

#### Concepto previo: la estructura `server_input`

``` C
struct server_input {
  pthread_mutex_t lock;
  int should_stop;
  int server_fd;
  struct handler_set handlers;
  void* shared_data;
}
```

Ésta estructura será, como indica el nombre, la entrada del servidor. Sus campos son:

* `pthread_mutex_t lock`: lock que se utiliza para sincronizar el acceso al resto de campos de la estructura.
* `int should_stop`: flag que señaliza cuando el servidor debe cerrar todas las conexiones y finalizar.
* `int server_fd`: file descriptor del socket servidor, resultado de una llamada exitosa a `create_socket_server()`.
* `struct handler_set handlers`: estructura que contiene los handlers que utilizará el servidor.
* `void* shared_data`: datos compartidos entre el thread que instancia el servidor y los handlers del mismo.

La estructura debe ser inicializada mediante la siguiente función:

``` C
void init_server_input(struct server_input* input, int server_fd, struct handler_set handlers, void* shared_data);
```

La misma recibe un puntero a una instancia de la estructura y todos sus campos salvo `lock` y `should_stop`. Asigna
los parámetros recibidos a los campos correspondientes, inicializa `should_stop` a `false` (0) e inicializa `lock` con
`pthread_mutex_init(&lock, NULL)`.

**Nota**

Luego de instanciado el servidor, si bien se utliza el flag `should_stop` para finalizarlo y los datos compartidos pueden
ser modificados tanto por los handlers como por otro thread, este no registrará cambios en `server_fd` ni en `handlers`.

#### Los datos compartidos

La estructura `server_input`, como ya explicado, contiene un void* de datos compartidos. Estos serán pasados como
segundo parámetro a los handlers, permitiendo así compartir estado entre los handlers y el thread que instanció
el servidor sin tener que utilizar estado estático.

En caso de no necesitar estado compartido, el `void*` puede setearse a `NULL` de forma segura.

#### Notas de sincronización

El acceso a los campos del `server_input` luego de haberse instanciado el servidor debe protegerse bloqueando el `lock` antes y 
desbloqueandolo después del acceso. El servidor y el resto de funciones de esta librería sigue dicha practica internamente 
siempre que vayan a acceder a campos del `server_input`.

El acceso a los datos compartidos en los handlers puede hacerse de forma segura directamente. El `lock` del servidor es bloqueado
por el mismo antes de la ejecución de cualquier handler y es desbloqueado luego de esta.

#### Instanciar el servidor

Basta de conceptos previos :smile:.

El servidor se instancia usando:

``` C
int start_server(pthread_t* server_thread, struct server_input* input);
```

Recibe como paremetros un `pthread_t*`, que apunta al que será el thread del servidor, y un `struct server_input*`, que apunta
a la estructura que se usará de entrada al servidor. Intenta ejecutar un servidor en el thread, retorna 0 en caso de éxito y -1
en caso de error. A partir de una llamada exitosa a esta función, el servidor ya se está ejecutando.

#### Detener el servidor

Existen dos funciones que facilitan el detener un servidor:

``` C
void stop_server(struct server_input* input);
```

Esta función recibe un puntero a la estructura que se le dió de entrada al servidor y setea el campo `should_stop` de la misma a 
`true` (1), indicandole al servidor que debe cerrar sus conexiones y finalizar.

``` C
void stop_server_and_join(pthread_t server_thread, struct server_input* input);
```

Esta otra función recibe como parámetros el `pthread_t` con el que se instanció el servidor y el puntero a su estructura de entrada.
Ejecuta `stop_server()` y luego ejecuta `pthread_join(server_thread, NULL)`, esperando a que el thread finalice para retornar.

#### Ejemplo

``` C
#include <stdio.h>
#include <stdint.h>
#include <unistd.h>
#include <sys/socket.h>
#include <errno.h>

#include "sockets.h"

#define PORT "9000"
#define BACKLOG 10

int on_new_client(int socket, void* cantidad_de_handlers_ejecutados) {
  printf("Nuevo cliente: %d\n", socket);
  
  // Modificamos el estado compartido, puede hacerse de forma segura directamente porque
  // el servidor bloquea el mutex antes de ejecutar el handler
  *((int*) cantidad_de_handlers_ejecutados) = *((int*) cantidad_de_handlers_ejecutados) + 1;
  return 0;
}

int on_can_read(int socket, void* cantidad_de_handlers_ejecutados) {
  uint8_t buf[100];
  int num_bytes;
  
  *((int*) cantidad_de_handlers_ejecutados) = *((int*) cantidad_de_handlers_ejecutados) + 1;
  
  if((num_bytes = recv(socket, buf, 100 - 1, 0)) == -1) {
    printf("Error recv. Errno: %d\n", errno);
    return -1;
  }
  
  if(num_bytes == 0) {
    // El cliente cerró la conexión
    return CLOSE_CLIENT;
  }
  
  // Usar los datos recibidos
  
  return 0;
}

int main() {
  int server_fd;
  pthread_t server_thread;
  int cantidad_de_handlers_ejecutados = 0;
  struct handler_set handlers;
  struct server_input input;
  
  if((server_fd = create_socket_server(PORT, BACKLOG)) == -1) {
    printf("Socket error\n");
    return -1;
  }
  
  handlers.on_new_client = &on_new_client;
  handlers.on_can_read = &on_can_read;
  
  init_server_input(&input, server_fd, handlers, &cantidad_de_handlers_ejecutados);
  
  start_server(&server_thread, &input);
  
  sleep(10);
  
  stop_server_and_join(server_thread, &input);
  
  printf("Cantidad de handlers ejecutados mientras corría el servidor: %d\n", cantidad_de_handlers_ejecutados);
  
  return 0;
}
```

### Compilación

Al utilizar pthreads para manejar la concurrencia, la librería utiliza el header `pthread.h` y debe linkearse a la librería en momento
de compilación con el flag `-pthread`. Bajo `gcc`, por ejemplo:

``` bash
gcc *.c -o application -pthread
```
