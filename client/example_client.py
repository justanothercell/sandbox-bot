import sys
import os
# make protocol.py importable
currentdir = os.path.dirname(os.path.abspath(__file__))
parentdir = os.path.dirname(currentdir)
sys.path.insert(0, parentdir) 

import asyncio
from websockets.asyncio.client import connect
import json
from dotenv import load_dotenv
load_dotenv()

import protocol

CLIENT_KEY = os.getenv('CLIENT_KEY')

def evaluate(code: str):
    return f'The length of the code is {len(code)}.'

# Note that this example implementation does only a minimum of error handling and should be coded more soundly in production
async def client():
    async with connect("ws://localhost:1717") as socket:
        print('registring...')
        # register
        m = protocol.SessionRegisterMessage(protocol.new_id(), CLIENT_KEY)
        await socket.send(json.dumps(m.to_dict()))
        # wait for ServerOk
        print('waiting for ok...')
        r = await socket.recv()
        m: protocol.ServerMessage = protocol.Message.from_dict(json.loads(r))
        if m.kind == protocol.InvalidMessage.kind:
            print('Invalid key')
            return
        assert m.kind == protocol.ServerOkMessage.kind, f'Invalid message of kind {m.kind}:\n{m.to_dict()}'
        print('registered!')

        # evaluation loop
        while True:
            print('waiting for server message...')
            r = await socket.recv()
            m: protocol.EvaluateMessage = protocol.Message.from_dict(json.loads(r))
            assert m.kind == protocol.EvaluateMessage.kind, f'Invalid message of kind {m.kind}:\n{m.to_dict()}'
            print('received code to evaluate')
            conversation_id = m.id
            # we only care about stdout
            result = evaluate(m.code)
            print('evaluated, sendign response...')
            m = protocol.ResultMessage(conversation_id, CLIENT_KEY, True, stdout=result)
            await socket.send(json.dumps(m.to_dict()))
            print('sent!')

if __name__ == "__main__":
    asyncio.run(client())
