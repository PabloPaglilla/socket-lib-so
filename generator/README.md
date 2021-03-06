# Generador de protocolo C

Este módulo de Python 3 genera un protocolo de comunicación para lenguaje C a partir de su definición en un archivo xml.

Los paquetes poseen la siguiente estructura:

* El primer byte contiene la longitud en bytes del mensaje, sin contar este byte.
* El segundo byte contiene el id del mensaje. El id de cada mensaje es definido por el usuario en el archivo xml.
* El resto del paquete contiene el cuerpo del mensaje. Se utiliza el id del mensaje para saber su tipo y así poder castear los datos al `struct` correspondiente.

## Archivos generados

La herramienta genera dos archivos:

* Un header que contiene:
	* La definición de las enumeraciones del protocolo.
	* La definición de un `struct` por cada mensaje.
	* La definición de 3 constantes de preprocesador que representan el nombre del mensaje, tu identificador y su tamaño.
	* Las declaraciones de las funciones implementadas en el fuente.
* Un archivo fuente que define:
	* Funciones para crear, codificar a network byte order, decodificar, empaquetar y enviar cada mensaje.
	* Una función para decodificar un mensaje cualquiera.
	* Una función para empaquetar cualquier mensaje, la cual
	es usada por todas las funciones que empaquetan un mensaje particular.
	* Una función para recibir un mensaje cualquiera.

## Mensajes

Cada mensaje está representado por un struct que contiene los campos definidos por el usuario. 

Los tipos soportados para los campos son `int8_t`, `uint8_t`, `int16_t`, `uint16_t`, `int32_t`, `uint32_t` y `char`. Cada campo puede ser un único elemento o un array de cualquiera de los tipos soportados.

**Al utilizar un byte para especificar el tamaño del mensaje junto con el identificador, los mensajes no pueden superar 254 bytes de tamaño.**

## Definición del protocolo

La definición del protocolo se realiza en un archivo xml con el siguiente formato:

``` xml
<nombre-del-protocolo>
	<enums>
		<enum name="nombre-de-la-enumeración">
			<entry>nombre-del-campo-de-la-enumeración</entry>
			...
		</enum>
		...
	</enums>
	<messages>
		<message id="id-del-mensaje" name="nombre-del-mensaje">
			<!-- Para elementos únicos -->
			<field type="tipo">nombre-del-campo</field>
			<!-- Para arrays -->
			<field type="tipo[]" len="cantidad-de-elementos">nombre-del-campo</field>
			...
		</message>
		...
	</messages>
</nombre-del-protocolo>
```

* Dentro del tag `enums` se definen las enumeraciones del protocolo. 
	* Cada `enum` lleva un atributo `name` con su nombre y dentro de ella se definen sus entradas en cada tag `entry`.
	* Cada `entry` lleva su nombre definido entre el tag de apertura y el tag de cierre.
* Dentro del tag `messages` se definen los mensajes.
	* Cada `message` lleva un atributo `id`, un número entre 0 y 255 que será su identificador, y un atributo `name` con su nombre. Dentro del mensaje se definen sus campos con los tags `field`.
	* Cada `field` puede ser un campo de elemento único o un array. En caso de ser un elemento único, su atributo `type` lleva su tipo. En caso de ser un array; el atributo `type` lleva su tipo seguido de "[]" y debe agregarse el atributo `len`, que contiene la cantidad de elementos del array. En ambos casos, entre el tag de apertura y el tag de cierre figura el nombre del campo.
* **Todos los nombres deben seguir las reglas léxicas de identificadores de C.**

## Uso del generador

El uso del módulo es el siguiente:

``` bash
python generator.py [-h] [-o OUTPUT] xml_source
```

Donde: 

* xml_source es el archivo xml donde se encuentra definido el protocolo
* El flag "-o" permite especificar el directorio y/o nombre de los archivos de salida. Su uso es similar al del mismo flag en `gcc`.
	* De no especificarse, los archivos se colocarán en el directorio actual con el nombre del protocolo.
	* De especificarse un directorio, los archivos se colocarán allí con el nombre del protocolo.

## Uso del protocolo generado

### Errores

El protocolo define una enumeración de errores, la cual contiene:

* SOCKET_ERROR: retornado cuando se produjo un error relacionado a la comunicación por sockets. Errno se encontrará seteada al error correspondiente.
* UNKOWN_ID: retornada al intentar decodificar un mensaje cuyo identificador no pertenece al de ninguno definido.
* BUFFER_TOO_SMALL: retornado al intentar recibir un mensaje pero brindando un buffer que puede no tener el tamaño suficiente. Este debe tener al menos el tamaño del mensaje más grande.
* MESSAGE_TOO_BIG: retornado al intentar empaquetar un mensaje cuyo tamaño supera el permitido.
* CONN_CLOSED: retornado al intentar recibir un mensaje cuando la conexión fue cerrada por la otra parte.

### API

El protocolo define las siguientes funciones:

``` C
// Recibe el buffer data con un mensaje empaquetado.
// Determina el tipo de mensaje, lo decodifica, escribe
// la estructura correspondiente al mensaje al buffer buff
// y retorna el id del mensaje.
// Retorna UNKOWN_ID si no se reconoció el identificador del mensaje.
int decode(void *data, void *buff);

// Toma el id del mensaje, su tamaño, un buffer conteniendo la
// estructura correspondiente cargada y un buffer. Empaqueta el
// mensaje y lo escribe en el buffer. Retorna la cantidad
// de bytes escritos. El buffer debe tener al menos body_size + 2
// de memoria disponible.
// Retorna MESSAGE_TOO_BIG si el tamaño del cuerpo del mensaje supera 254.
int pack_msg(uint8_t msg_id, uint8_t body_size, void *msg_body, uint8_t *buff);

// Toma un socket, un buffer y el tamaño máximo de este.
// Recibe un mensaje del protocolo del socket, lo decodifica
// y lo almacena en el buffer. Retorna el identificador del
// mensaje recibido.
// Si el buffer no alcanza el tamaño del mensaje más grande del
// protocolo, retorna BUFFER_TOO_SMALL.
// Si la conexión del socket fue cerrada por la otra parte,
// retorna CONN_CLOSED.
// Si se produce un error de comunicación, retorna SOCKET_ERROR
// y errno se encontrará seteada de forma acorde.
// Si no se reconoce el id del mensaje al intentar decodificarlo,
// retorna UNKOWN_ID.
int recv_msg(int socket_fd, void* buffer, int max_size);
```

Luego, por cada mensaje, el protocolo expone las siguientes funciones:

``` C
// Toma como parámetro los campos del mensaje y devuelve una
// estructura correspondiente cargada con los valores.
struct nombre_mensaje create_nombre_mensaje(campos);

// Toma como parámetro un puntero a una estructura del mensaje
// y codifica sus campos a network byte order según corresponda.
void encode_nombre_mensaje(struct nombre_mensaje* mensaje);

// Toma un buffer como un puntero a void que contenga una 
// estructura del mensaje y decodifica sus campos a host
// byte order según corresponda.
void decode_nombre_mensaje(void* buff);

// Recibe los campos de un mensaje y un buffer. Crea el mensaje,
// lo codifica a network byte order y luego lo empaqueta con la
// función pack_msg dentro del buffer. El buffer debe tener
// disponible al menos suficiente memoria para alojar el mensaje
// más dos bytes (el identificador y el largo del mensaje).
// Al igual que pack_msg(), retorna la cantidad de bytes escritos
// en el buffer o MESSAGE_TOO_BIG si el cuerpo del mensaje supera los
// 254 bytes.
int pack_nombre_mensaje(campos, uint8_t* buff);

// Recibe los campos del mensaje y un socket por parámetros.
// Crea el mensaje, lo codifica, lo empaqueta y luego lo
// envía por el socket, asegurandose de que se envie completo.
// Retorna la cantidad de bytes enviados en caso de éxito.
// En caso de un error en la comunicación, retorna SOCKET_ERROR
// y errno estará seteada acorde.
int send_nombre_mensaje(campos, int socket_fd);
```

## Ejemplo

Dado el siguiente archivo de definición: 

``` xml
<protocol>
	<enums></enums>
	<messages>
		<message id="0" name="test_msg">
			<field type="uint8_t">x</field>
			<field type="int32_t[]" len="5">y</field>
		</message>
	</messages>
</protocol>
```

``` C
#include <stdio.h>
#include <stdint.h>
#include "protocol.h"

int main() {
	uint8_t buff[TEST_MSG_SIZE + 2], decoded[TEST_MSG_SIZE];
	uint8_t x = 123;
	int32_t y[5] = {1, 2, 3, 4, 5};

	// Una forma de empaquetar
	struct test_msg msg = create_test_msg(x, y);
	encode_test_msg(&msg);
	if(pack_msg(TEST_MSG_ID, sizeof(msg), &msg, buff) == MESSAGE_TOO_BIG) {
		printf("Error");
		exit(1);
	}

	// Otra forma de empaquetar
	if(pack_test_msg(x, y, buff) == MESSAGE_TOO_BIG) {
		printf("Error");
		exit(1);
	}

	// Enviar el mensaje directamente por un socket sin empaquetar a mano
	int socket_fd; // Asumimos que es un socket válido al que se puede escribir
	if(send_test_msg(x, y, socket_fd) == SOCKET_ERROR) {
		printf("Error");
		exit(1);
	}

	// Recibir un mensaje del socket
	int msg_id; 
	if((msg_id = recv_msg(socket_fd, buff, TEST_MSG_SIZE + 2)) < 0){
		printf("Error");
		exit(1);
	}

	// Decodificar
	int msg_id = decode(buff, decoded);
	struct test_msg *decoded_msg = (struct test_msg*)decoded;
}
```