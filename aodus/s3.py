import ssl, asyncio
from typing import Tuple

from lxml import etree
from urllib.parse import unquote

from aodus.utils import parse_token, generate_token
from aodus.exceptions import AuthenticationException, ConnectionTimeoutException, EndOfStreamException, NegotiationException

BUFFER_SIZE = 1024 * 1024

async def create_connection(loop: asyncio.AbstractEventLoop):
    sslContext = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
    reader, writer = await asyncio.open_connection(host="im.todus.cu", port=1756, loop=loop, ssl=sslContext)

    return reader, writer

class AsyncStreamWriter(object):
    def __init__(self, base: asyncio.StreamWriter) -> None:
        self.base = base

    async def write(self, data: bytes):
        self.base.write(data)
        await self.base.drain()

async def request_upload(loop: asyncio.AbstractEventLoop, token: str, filesize: int) -> Tuple[str, str]:
    phone, auth = parse_token(token)
    sid = generate_token(5)
    reader, writer = await create_connection(loop=loop)
    parser = etree.XMLPullParser(recover=True)

    try:
        # Start stream negotiation (RFC 6120)
        async with etree.xmlfile(AsyncStreamWriter(writer), close=False) as xf:
            async with xf.element("{x1}stream",
                                  o='im.todus.cu',
                                  v='1.0',
                                  nsmap={
                                      None: 'jc',
                                      'stream': 'x1'
                                  }):
                await xf.flush()

                while True:
                    response = await reader.read(BUFFER_SIZE)
                    parser.feed(response.removeprefix(b"<?xml version='1.0'?>"))

                    # Only support
                    # TODO: support for b1

                    for _, e in parser.read_events():
                        if e.tag == "{x1}features":
                            if e.find("{x2}es") != None:
                                # Do authentication
                                async with xf.element("{ah:ns}ah",
                                                    e='PLAIN',
                                                    nsmap={None: "ah:ns"}):
                                    await xf.write(auth)
                            elif e.find("{x4}b1") != None:
                                async with xf.element("iq", i=f'{sid}-1', t='set'):
                                    await xf.write(
                                        etree.Element("{x4}b1",
                                                      nsmap={None: "x4"}))
                            else:
                                raise NegotiationException()

                            await xf.flush()
                            continue

                        if e.tag == "{x2}ok":
                            # WARNING: hack this XD
                            # raise NegotiationException()
                            writer.write(b"<stream:stream xmlns='jc' o='im.todus.cu' xmlns:stream='x1' v='1.0'>")
                            await writer.drain()

                            continue

                        if e.tag == "{jc}not-authorized":
                            raise AuthenticationException()

                        if e.tag == "{jc}connection-timeout":
                            raise ConnectionTimeoutException()

                        if e.tag == "{jc}ed":
                            await xf.write(etree.Element('p', i=f"{sid}-4"))
                            await xf.flush()

                            continue

                        if e.tag == '{jc}iq' and e.attrib.get('t', None) == 'result' and \
                             e.attrib.get('i', None) == f'{sid}-1':
                            await xf.write(
                                etree.Element("{x7}en",
                                              u='true',
                                              max='300',
                                              nsmap={None: 'x7'}))

                            async with xf.element("iq", i=f"{sid}-3", t='get'):
                                await xf.write(
                                    etree.Element("{todus:purl}query",
                                                  type='1',
                                                  persistent='false',
                                                  size=str(filesize),
                                                  room='',
                                                  nsmap={None: 'todus:purl'}))
                            await xf.flush()
                            continue

                        if e.tag == '{jc}iq' and e.attrib.get('t', None) == 'result' and \
                            e.attrib.get('i', None) == f'{sid}-3' and \
                            e.attrib.get('o', None).startswith(f'{phone}@im.todus.cu'):
                            # Verify if to our device
                            q = e.find(".//{todus:purl}query")
                            upload = unquote(q.attrib.get('put'))
                            download = unquote(q.attrib.get('get'))

                            return (upload, download)

    finally:
        writer.close()
        # reader.close()
        parser.close()