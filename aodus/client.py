import aiohttp, asyncio, inspect, functools, os, aiofiles, string

from types import TracebackType
from typing import Optional, IO, AsyncGenerator, Union, Callable, Tuple, Type
from aiohttp import ClientTimeout, ClientResponse
from aiohttp.hdrs import ACCEPT_ENCODING, CONTENT_TYPE, USER_AGENT, HOST, AUTHORIZATION
from aiofiles.threadpool.binary import AsyncBufferedIOBase

from concurrent.futures.thread import ThreadPoolExecutor

from aodus.utils import generate_token
from aodus.s3 import request_upload
from aodus.scaffold import Scaffold

class Client(Scaffold):
    def __init__(
        self,
        version: str = Scaffold.DEFAULT_TODUS_VERSION,
        version_code: str = Scaffold.DEFAULT_TODUS_VERSION_CODE,
        workers: int = Scaffold.WORKERS,
        timeout: Optional[int] = None,
        chunk_size: Optional[int] = None
    ) -> None:
        self.version = version
        self.version_code = version_code
        self.timeout = timeout or 300
        self.chunk_size = chunk_size or 65536
        self.workers = workers
        self.loop = asyncio.get_event_loop()
        self.chunk_size = chunk_size or 65536

        self.executor = ThreadPoolExecutor(self.workers, thread_name_prefix="Handler")

        self.session = aiohttp.ClientSession(
            loop=self.loop,
            timeout=ClientTimeout(total=self.timeout),
            headers={
                ACCEPT_ENCODING: "gzip",
            }
        )

    async def request_code(self, phone_number: str) -> None:
        """Request server to send verification SMS code."""
        headers = {
            USER_AGENT: f"ToDus {self.version} Auth",
            CONTENT_TYPE: "application/x-protobuf"
        }

        data = f"\n\n{phone_number}\x12\x96\x01{generate_token(150)}".encode("raw_unicode_escape")
        url = Scaffold.URL_BASE.format("auth", "v2/auth/users.reserve")

        async with self.session.post(url, data=data, headers=headers) as r:
            r.raise_for_status()

    async def validate_code(self, phone_number: str, code: str) -> str:
        """
        Validate phone number with received SMS code.
        Returns the account password.
        """
        headers = {
            USER_AGENT: f"ToDus {self.version} Auth",
            CONTENT_TYPE: "application/x-protobuf"
        }
        data = f"\n\n{phone_number}\x12\x96\x01{generate_token(150)}\x1a\x06{code}".encode("raw_unicode_escape")
        url = Scaffold.URL_BASE.format("auth", "v2/auth/users.register")

        async with self.session.post(url, data=data, headers=headers) as r:
            r.raise_for_status()
            content = await r.read()
            if b"`" in content:
                index = content.index(b"`") + 1
                return content[index : index + 96].decode()
            else:
                return content[5:166].decode()

    async def login(self, phone_number: str, password: str) -> str:
        """
        Login with phone number and password to get an access token.
        """

        headers = {
            USER_AGENT: f"ToDus {self.version} Auth",
            CONTENT_TYPE: "application/x-protobuf"
        }

        data = f"\n\n{phone_number}\x12\x96\x01{generate_token(150)}\x12\x60{password}\x1a\x05{self.version_code}".encode(
            "raw_unicode_escape")
        url = Scaffold.URL_BASE.format("auth", "v2/auth/token")
        
        async with self.session.post(url, data=data, headers=headers) as r:
            r.raise_for_status()
            content = await r.read()
            token = "".join([chr(c) for c in content if c >= 0 and c <= 0x10ffff and chr(c) in string.printable])
            return token

    async def upload(
        self,
        token: str,
        buffer: Union[IO, AsyncGenerator[bytes, None]],
        buffer_size: Optional[int] = None,
        retry: Optional[int] = 1,
        retry_callback: Optional[Callable] = None,
        progress: Optional[Callable[[int, int, Tuple], None]] = None,
        progress_args: Optional[Tuple] = ()
    ) -> str:
        """"
        Upload to todus s3 server the buffer of byte specified
        """

        timeout = max(buffer_size / 1024 / 1024 * 20, self.timeout)

        bulk, share_url = await request_upload(self.loop, token, buffer_size)
        headers = {
            USER_AGENT: f"ToDus {self.version} HTTP-Upload",
            AUTHORIZATION: f"Bearer {token}",
        }

        if callable(progress) and not inspect.iscoroutinefunction(buffer):
            async def file_sender():
                offset = 0

                while offset < buffer_size:
                    chunk = await buffer.read(self.chunk_size) if inspect.iscoroutinefunction(buffer.read) or \
                            isinstance(buffer, AsyncBufferedIOBase) else buffer.read(self.chunk_size)
                    if not chunk:
                        break

                    offset += len(chunk)

                    # Execute progress function
                    if progress:
                        func = functools.partial(
                            progress,
                            min(offset, buffer_size)
                            if buffer_size != 0
                            else offset,
                            buffer_size,
                            *progress_args
                        )

                        if inspect.iscoroutinefunction(progress):
                            await func()
                        else:
                            await self.loop.run_in_executor(self.executor, func)

                    yield chunk
            obj = file_sender()
        else:
            obj = buffer

        while True:
            try:
                async with self.session.put(bulk, data=obj, headers=headers, timeout=timeout) as r:
                    r.raise_for_status()
                    break
            except Exception as e:
                retry -= 1
                if retry <= 0:
                    raise e
                if callable(retry_callback):
                    retry_callback()

        return share_url

    async def upload_file(
        self,
        token: str,
        path: Union[str, "os.PathLike[str]"],
        progress: Optional[Callable[[int, int, Tuple], None]] = None,
        progress_args: Optional[Tuple] = ()
    ) -> str:
        async with aiofiles.open(path, 'rb') as file:
            size = os.path.getsize(path)
            return await self.upload(token=token, buffer=file, buffer_size=size,
                    progress=progress, progress_args=progress_args)

    def __enter__(self) -> None:
        raise TypeError("Use async with instead")

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        """
        Unable to call because you must use async with statement
        """
        pass

    async def __aenter__(self) -> "Client":
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        await self.close()

    async def close(self) -> None:
        if self.session:
            await self.session.close()
