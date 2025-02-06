from uuid import uuid4
from os import urandom
import base64

def new_id() -> str:
    return str(uuid4())

def new_key() -> str:
    return base64.b64encode(urandom(64)).decode()

def get_value(data: dict, name: str, ty: type, optional: bool):
    if name not in data:
        if optional:
            return None
        raise ValueError(f'Key {name} not defined')
    if type(data[name]) != ty:
        raise ValueError(f'Expected value of {name} to be of type {ty.__name__}, got {type(data[name]).__name__}')
    return data[name]

class Message:
    def __init__(self, id: str, kind: str, side: str):
        self.id = id
        self.version = 0
        self.kind = kind
        self.side = side

    def to_dict(self) -> dict:
        return { 
            'id': self.id, 
            'version': self.version, 
            'kind': self.kind, 
            'side': self.side
        }

    def from_dict(data: dict) -> 'Message':
        id = get_value(data, 'id', str, False)
        version = get_value(data, 'version', int, False)
        if version != 0:
            raise ValueError(f'Only version 0 is currently supported, got version {version}')
        kind = get_value(data, 'kind', str, False)
        side = get_value(data, 'side', str, False)
        match side:
            case 'SERVER':
                return ServerMessage.from_dict(data, id, kind)
            case 'CLIENT':
                return ClientMessage.from_dict(data, id, kind)
            case _:
                raise ValueError(f'Invalid side `{side}`')

class ClientMessage(Message):
    def __init__(self, id: str, kind: str, key: str):
        super().__init__(id, kind, 'CLIENT')
        self.key = key

    def to_dict(self) -> dict:
        return super().to_dict() | { 'key': self.key }
    
    def from_dict(data: dict, id: str, kind: str) -> 'Message':
        key = get_value(data, 'key', str, False)
        match kind:
            case SessionRegisterMessage.kind:
                return SessionRegisterMessage.from_dict(data, id, key)
            case ClientOkMessage.kind:
                return ClientOkMessage.from_dict(data, id, key)
            case ErrorMessage.kind:
                return ErrorMessage.from_dict(data, id, key)
            case ResultMessage.kind:
                return ResultMessage.from_dict(data, id, key)
            case _:
                raise ValueError(f'Invalid kind `{kind}` for ClientMessage')
            
class ServerMessage(Message):
    def __init__(self, id: str, kind: str):
        super().__init__(id, kind, 'SERVER')

    def to_dict(self) -> dict:
        return super().to_dict()

    def from_dict(data: dict, id: str, kind: str) -> 'Message':
        match kind:
            case ServerOkMessage.kind:
                return ServerOkMessage.from_dict(data, id)
            case InvalidMessage.kind:
                return InvalidMessage.from_dict(data, id)
            case EvaluateMessage.kind:
                return EvaluateMessage.from_dict(data, id)
            case TimeoutMessage.kind:
                return TimeoutMessage.from_dict(data, id)
            case _:
                raise ValueError(f'Invalid kind `{kind}` for ServerMessage')

class SessionRegisterMessage(ClientMessage):
    kind = 'REGISTER'
    def __init__(self, id: str, key: str):
        super().__init__(id, SessionRegisterMessage.kind, key)

    def to_dict(self):
        return super().to_dict()
    
    def from_dict(data, id: str, key: str):
        return SessionRegisterMessage(id, key)

class ClientOkMessage(ClientMessage):
    kind = 'CLIENTOK'
    def __init__(self, id: str, key: str):
        super().__init__(id, ClientOkMessage.kind, key)

    def to_dict(self):
        return super().to_dict()
    
    def from_dict(data, id: str, key: str):
        return ClientOkMessage(id, key)

class ServerOkMessage(ServerMessage):
    kind = 'SERVEROK'
    def __init__(self, id: str):
        super().__init__(id, ServerOkMessage.kind)

    def to_dict(self):
        return super().to_dict()
    
    def from_dict(data, id):
        return ServerOkMessage(id)

class InvalidMessage(ServerMessage):
    kind = 'INVALID'
    def __init__(self, id: str, error: str|None = None):
        super().__init__(id, InvalidMessage.kind)
        self.error = error

    def to_dict(self) -> dict:
        return super().to_dict() | { 'error': self.error }
    
    def from_dict(data: dict, id: str) -> 'Message':
        error = get_value(data, 'error', str, True)
        return InvalidMessage(id, error)
        
class ErrorMessage(ClientMessage):
    kind = 'Error'
    def __init__(self, id: str, key: str, error: str|None = None):
        super().__init__(id, ErrorMessage.kind, key)
        self.error = error

    def to_dict(self) -> dict:
        return super().to_dict() | { 'key': self.key }
    
    def from_dict(data: dict, id: str, key: str) -> 'Message':
        error = get_value(data, 'error', str, True)
        return ErrorMessage(id, key, error)

class EvaluateMessage(ServerMessage):
    kind = 'EVALUATE'
    def __init__(self, id: str, code: str):
        super().__init__(id, EvaluateMessage.kind)
        self.code = code

    def to_dict(self) -> dict:
        return super().to_dict() | { 'code': self.code }
    
    def from_dict(data: dict, id: str) -> 'Message':
        code = get_value(data, 'code', str, False)
        return EvaluateMessage(id, code)

class TimeoutMessage(ServerMessage):
    kind = 'TIMEOUT'
    def __init__(self, id: str):
        super().__init__(id, TimeoutMessage.kind)

    def to_dict(self) -> dict:
        return super().to_dict()
    
    def from_dict(data: dict, id: str) -> 'Message':
        return TimeoutMessage(id)

class ResultMessage(ClientMessage):
    kind = 'RESULT'
    def __init__(self, id: str, key: str, success: bool, error: str|None = None, exit_code: int|None = None, stdout: str|None = None, stderr: str|None = None):
        super().__init__(id, ResultMessage.kind, key)
        self.success = success
        self.error = error
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr

    def to_dict(self) -> dict:
        data = super().to_dict()
        if self.success:
            data['success'] = True
            if self.exit_code is not None:
                data['exit_code'] = self.exit_code
            if self.stdout is not None:
                data['stdout'] = self.stdout
            if self.stderr is not None:
                data['stderr'] = self.stderr
        else:
            data['success'] = False
            if self.error is not None:
                data['error'] = self.error
        return data

    def from_dict(data: dict, id: str, key: str) -> 'Message':
        if get_value(data, 'success', bool, False):
            return ResultMessage(id, key, True, None, get_value(data, 'exit_code', int, True), get_value(data, 'stdout', str, True), get_value(data, 'stderr', str, True))
        else:
            return ResultMessage(id, key, False, get_value(data, 'error', str, True), None, None, None)