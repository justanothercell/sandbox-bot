import shelve
import asyncio

import config

class Language:
    def __init__(self, user_id: int, name: str, short: str, key: str):
        self.user_id = user_id
        self.name = name
        self.short = short
        self.key = key

class LanguageRegistrationException(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message

class Store:
    def __init__(self):
        self.lock = asyncio.Lock()
        self.clients: dict[str, Language] = shelve.open(config.CLIENTS_STORE)

    async def register_lang(self, language: Language) -> Language|None:
        async with self.lock:
            for _, lang in self.clients.items():
                if language.name == lang.name and lang.user_id != language.user_id:
                    raise LanguageRegistrationException(f'A language with name {language.name} is alredy registered')
                if language.short == lang.short and lang.user_id != language.user_id:
                    raise LanguageRegistrationException(f'A language with name {language.short} is alredy registered')
            old = None
            if str(language.user_id) in self.clients:
                old = self.clients[str(language.user_id)]
            self.clients[str(language.user_id)] = language
            self.clients.sync()
            return old
    
    async def find_lang(self, name: str) -> Language|None:
        async with self.lock:
            for _, lang in self.clients.items():
                if name == lang.name or name == lang.short:
                    return lang
        return None
    
    async def validate_key(self, key: str) -> bool:
        async with self.lock:
            for _, lang in self.clients.items():
                if lang.key == key:
                    return True
        return False