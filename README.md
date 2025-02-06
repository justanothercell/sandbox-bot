# Discord bot for programming language sandbox clients

> [!WARNING]  
> This bot is currently not enavled on the r/ProgrammingLanguage discord.
> It should however be fairly easy to adapt the bot to your usecase

Connect your local language sandbox to the bot and evaluate code snippets on discord!

## Quickstart
The server was tested with python 3.12
### Command usage
- `/client_key <language_name> <short_name?>` get a key for your language bot. This only works if you have the `@Lang Cannel Owner` role on the [r/ProgrammingLanguages](https://www.reddit.com/r/ProgrammingLanguages/) discord. The response ot this message is not visible to others.
- `/eval <language> <expression> <display?>` evaluate an expression
- `run` (message rightclick command) run the code snippet and return an ephemeral response
- `run_view` (message rightclick command) run the code snippet and return a visible response
`run` and`run_view` figure out which language the snippet is in two ways:
````
```mylang
// code...
``` 
````
However since this is often used to set the syntax highlighting and some languages use a different langauge's highlighting with similar grammar, this can be overridden by:
````
`lang:mylang` ```rust
// code...
``` 
````
### Server
- configure the server via [server/config.py](server/config.py)
- create `server/.env` and put secrets like `BOT_TOKEN` there (see [server/config.py](server/config.py))
- install python modules `python -m pip install -r requirements.txt`
- `cd server` and run `python main.py`

### Example Client
Note that this example implementation does only a minimum of error handling and should be coded more soundly in production.
- create `server/.env` and create the item `CLIENT_KEY=<key obtained by /client_key>`
- `cd client` and run `python example_client.py`

## Protocol
```
+---------+                    +--------------+
| Discord | <--[bot events]--> | Bot (Server) |
+---------+                    +--------------+
                                    ^    ^
                                    |    |
                                 [WS protocol]
        +-----------------+         |    |
        | Client (python) | <-------+    |
        +-----------------+              |
                                         |
        +-----------------+              |
        | Client (lua)    | <------------+
        +-----------------+
```
### Message sequences
#### Registration:
```
Register (Client) --> Invalid (Server)
    |
    v
Server Ok (Server)
```
#### Evaluation:
```
Evaluate (Server) --> Error (Client) 
    |
    |----[delay]----> Timeout (Server)
    v
Result (Client)
```
Any Client message can be followed by an Invalid (Server) message even if the conevrsation has technically ended. This is purely for debugging and the client is not required to act upon this information.

### Messge format

A client can connect to the server via the websocket protocol using JSON messages.

Check [protocol.py](protocol.py) for python implementation.

Note that JSON strings might need backslash escapes for special characters, i.e. `\"`. Information about what needs escaping and the json protocol can be found [here](https://www.json.org/json-en.html).
Most JSON libraries will perform this for you.

#### Common fields (Client and Server)

Every message has the following fields:

| key     | value  | optional | description                                                                            |
|---------|--------|----------|----------------------------------------------------------------------------------------|
| id      | UUIDv4 | false    | Conversation id. Use same id when answering and a new UUIDv4 when initiating a request |
| kind    | str    | false    | The kind of message sent. Constants for specific messages below                        |
| side    | str    | false    | Either `CLIENT` or `SERVER` depending on the origin of the message                     |
| version | int    | false    | Protocol version                                                                       |

Latest `version = 0`.

There is no guarantee for compatability with older versions.

#### Common fields (Client)

Every client message additionally has the following field:

| key | value  | optional | description                                            |
|-----|--------|----------|--------------------------------------------------------|
| key | base64 | false    | Base64 encoded authentication key obtained via the bot |

#### SessionRegister (Client)

`kind = "REGISTER"`

Register the client for this session. This is the first thing a client should do after starting up.

The server will respond with [Server Ok](#serverok-server) or [Invalid Message](#invalid-message-server) if the key is invalid.

_This message has no additional fields_

#### Client Ok (Client)

`kind = "CLIENTOK"`

A confirmation of success.

_This message has no additional fields_

#### Server Ok (Server)

`kind = "SERVEROK"`

A confirmation of success.

_This message has no additional fields_

#### Invalid message (Server)

`kind = "INVALID"`

The client's last message corresponding to this `id` was invalid.
This could be an invalid `key`, unknown message `id` or missing/mistyped fields.
This message also signals the end of the conversation with this `id`.

If the server failed to parse the client message, `id` is an empty string

If this happens during a bot command then the bot will send an ephemeral message signaling that there was a client communication error.

This message can be sent even if the conversaion is already done.This is purely for debugging and the client is not required to act upon this information.

| key   | value  | optional | description                                           |
|-------|--------|----------|-------------------------------------------------------|
| error | str    | true     | Optional error message on why the message was invalid |

#### Error (Client)

`kind = "ERROR"`

The client could not process the request. If a client fails to compile code, use [Result](#result-client) with appropiate fields instead.
This should ONLY be used if something unexpected or unrecoverable happened, i.e. interpreter not found, out of memory, etc.
This message also signals the end of the conversation with this `id`.

If this happens during a bot command then the bot will send an ephemeral message signaling that there was a client error.

| key   | value  | optional | description                                           |
|-------|--------|----------|-------------------------------------------------------|
| error | str    | true     | Optional error message on why the message was invalid |

#### Evaluate (Server)

`kind = "EVAL"`

Request evaluation of a code snippet.

| key  | value  | optional | description                  |
|------|--------|----------|------------------------------|
| code | str    | false    | The code snippet to evaluate |

#### Timeout (Server)

`kind = "TIMEOUT"`

Timeout while waiting on [Result](#result-client) or [Error](#error-client).
This message also signals the end of the conversation with this `id`.

_This message has no additional fields_

#### Result (Client)

`kind = "RESULT"`

Evaluation result.
This should be used even if the code fails to compile.
Choose whichever optional fields apply to your langauge.
This message also signals the end of the conversation with this `id`.

###### `success == true`:
- `exit_code`, `stdout` and `stderr` will be displayed if present.
###### `success == false`:
- `error` will be displayed if present, aswell as a message indication a compiler error.

Consider not sending fields which won"t be displayed anyways.

| key       | value | optional | description                |
|-----------|-------|----------|----------------------------|
| success   | bool  | false    | Signals successful compilation. Should be true even if there were runtime errors or if there is no separate compilation step |
| error     | str   | true     | compiler error message     |
| exit_code | int   | true     | exit code of the execution |
| stdout    | str   | true     | Stdout of the execution    |
| stderr    | str   | true     | Stderr of the execution    |