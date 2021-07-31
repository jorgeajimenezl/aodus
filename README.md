# Python Async Todus client

## Getting started
```python
from aodus import Client

async with Client() as todus:
    await todus.request_code("<phone-number>")
    code = int(input())
    
    password = await todus.validate_code("<phone-number>", code)

    token = await todus.login("<phone-number>", password)
    print(await todus.upload_file(token, "/path/to/file.mp4"))
```

## License
[MIT License](./LICENSE)