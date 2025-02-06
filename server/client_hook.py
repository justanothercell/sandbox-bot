from websockets.asyncio.server import serve, ServerConnection
from websockets.exceptions import ConnectionClosedError
import asyncio
import json

import config
import protocol
from store import Store

class Client:
    def __init__(self, key: str, socket: ServerConnection):
        self.key = key
        self.socket = socket
        self.lock = asyncio.Lock()
        self.conversations: dict[str, asyncio.Queue] = {}

class Conversation:
    def __init__(self, server: 'ClientHookServer', client: Client):
        self.server = server
        self.client = client
        self.id: str|None = None
        self.queue: asyncio.Queue|None = None

    async def __aenter__(self) -> 'Conversation':
        self.id = protocol.new_id()
        self.queue = asyncio.Queue()
        async with self.client.lock:
            self.client.conversations[self.id] = self.queue
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self.id = None
        self.queue = None
        async with self.client.lock:
            if self.id in self.client.conversations:
                del self.client.conversations[self.id]

    async def send(self, message: protocol.Message):
        assert self.id is not None, 'Must call Conversation.send inside with block'
        data = message.to_dict()
        raw = json.dumps(data)
        await self.client.socket.send(raw)

    async def receive(self) -> protocol.Message:
        return await self.queue.get()

class ClientHookServer:
    def __init__(self, store: Store):
        self.address = config.WS_HOST
        self.port = config.WS_PORT
        self.store = store
        self.clients_lock = asyncio.Lock()
        self.clients: dict[str, Client] = {}

    async def run(self):
        print(f'ClientHookServer started')
        async with serve(self.handle_client, self.address, self.port) as server:
            await server.serve_forever()
        print(f'ClientHookServer stopped')

    async def handle_client(self, socket: ServerConnection):
        print(f'{socket.remote_address} connected')
        client: Client = None
        try:
            async for raw_message in socket:
                try:
                    data = json.loads(raw_message)
                    message: protocol.ClientMessage = protocol.Message.from_dict(data)
                    if message.side != 'CLIENT':
                        await socket.send(json.dumps(protocol.InvalidMessage(message.id, f'Expected CLIENT side message, got {message.side}').to_dict()))
                        continue
                except json.JSONDecodeError as e:
                    await socket.send(json.dumps(protocol.InvalidMessage('', str(e)).to_dict()))
                except ValueError as e:
                    await socket.send(json.dumps(protocol.InvalidMessage('', str(e)).to_dict()))
                    continue
                if message.kind == protocol.SessionRegisterMessage.kind:
                    if client is not None:
                        await socket.send(json.dumps(protocol.InvalidMessage(message.id, 'Already registered').to_dict()))
                        continue
                    if not await self.store.validate_key(message.key):
                        await socket.send(json.dumps(protocol.InvalidMessage(message.id, 'Invalid key. Request a new one with `/client_key`').to_dict()))
                        continue
                    async with self.clients_lock:
                        if message.key in self.clients:
                            await socket.send(json.dumps(protocol.InvalidMessage(message.id, 'Client already logged in. Request a new key with `/client_key` to invalidate that session').to_dict()))
                            continue
                        client = Client(message.key, socket)
                        self.clients[client.key] = client
                    await socket.send(json.dumps(protocol.ServerOkMessage(message.id).to_dict()))
                    print(f'{socket.remote_address} registered')
                elif client is not None:
                    async with client.lock:
                        if message.id in client.conversations:
                            await client.conversations[message.id].put(message)
                        else:
                            await socket.send(json.dumps(protocol.InvalidMessage(message.id, 'No active conversation with that id').to_dict()))
                else:
                    await socket.send(json.dumps(protocol.InvalidMessage(message.id, 'Client needs to be registered first').to_dict()))
        except ConnectionClosedError:
            print(f'{socket.remote_address} aborted connection')
        else:
            print(f'{socket.remote_address} disconnected')
        finally:
            if client is not None:
                async with self.clients_lock:
                    del self.clients[client.key]

    async def conversation(self, key: str) -> Conversation|None:
        async with self.clients_lock:
            if key in self.clients:
                return Conversation(self, self.clients[key])
            return None
        
    async def kill_client_conn(self, key: str):
        async with self.clients_lock:
            if key in self.clients:
                self.clients[key].socket.abort_pings()
                self.clients[key].socket.close()
