import aodus
import sys, asyncio, os
from pathlib import Path

class Scaffold(object):
    URL_BASE = "https://{}.todus.cu/{}"
    DEFAULT_TODUS_VERSION = "0.38.34"
    DEFAULT_TODUS_VERSION_CODE = "21805"

    PARENT_DIR = Path(sys.argv[0]).parent
    WORKERS = min(32, os.cpu_count() + 4)
    WORKDIR = PARENT_DIR

    def __init__(self):
        try:
            asyncio.get_event_loop()
        except RuntimeError:
            asyncio.set_event_loop(aodus.main_event_loop)

        self.version = None
        self.version_code = None
        self.timeout = None
        self.chunk_size = None
        self.workers = None
        self.loop = None
        self.executor = None
        self.session = None
        self.chunk_size = None

    async def request_code(self, *args, **kwargs):
        pass

    async def validate_code(self, *args, **kwargs):
        pass

    async def login(self, *args, **kwargs):
        pass

    async def upload(self, *args, **kwargs):
        pass  

    async def download(self, *args, **kwargs):
        pass  
    
    async def upload_file(self, *args, **kwargs):
        pass

    async def download_file(self, *args, **kwargs):
        pass
