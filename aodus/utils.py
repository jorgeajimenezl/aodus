import string, random, json
from base64 import b64decode, b64encode

def generate_token(length: int) -> str:
    chars = string.ascii_letters + string.digits
    return "".join(random.choices(chars, k=length))

def parse_token(token: str) -> tuple:
    phone = json.loads(b64decode(token.split(".")[1]).decode())["username"]
    auth = b64encode((chr(0) + phone + chr(0) + token).encode("utf-8"))
    return phone, auth