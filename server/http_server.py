import asyncio
import base64
import credentials
import hashlib
import hmac
import logging
import os
import time
import ssl
import aiohttp
from aiohttp import web
import aiohttp_jinja2
import jinja2


ROLE = '1'
USER_NAME = 'Human Expert'


logger = logging.getLogger(__name__)


@aiohttp_jinja2.template('zoom.html')
async def zoom(request):
    meeting_number = credentials.MEETING_NUMBER
    key = credentials.WEB_KEY
    secret = credentials.WEB_SECRET
    signature = get_signature(meeting_number, key, ROLE, secret)
    return {
        'meeting_number': meeting_number,
        'api_key': key,
        'signature': signature,
        'password': credentials.MEETING_PASSWORD,
        'user_name': USER_NAME
    }


def get_signature(meeting_number, key, role, secret):
    ts = str(int(round(time.time() * 1000)) - 30000)
    message = key + meeting_number + ts + role
    message = base64.b64encode(bytes(message, 'utf-8'))
    secret = bytes(secret, 'utf-8')
    hash = hmac.new(secret, message, hashlib.sha256)
    hash = base64.b64encode(hash.digest())
    hash = hash.decode('utf-8')
    raw_signature = '{}.{}.{}.{}.{}'.format(key, meeting_number, ts, role, hash)
    signature = base64.b64encode(bytes(raw_signature, 'utf-8'))
    signature = signature.decode('utf-8')
    return signature.rstrip('=')


async def favicon(request):
    return web.FileResponse('favicon.ico')


class ServerState:
    def __init__(self):
        self._state = None
        self._user_connected = False

    def create_websocket_handler(self, conn):
        async def websocket_handler(request):
            ws = web.WebSocketResponse()
            await ws.prepare(request)
            if self._user_connected:
                logger.info('ignoring additional websocket connection')
                return ws

            self._user_connected = True
            logger.info('websocket connection opened')

            def engine_reader():
                from_engine = conn.recv()
                asyncio.ensure_future(ws.send_json(from_engine))
                if from_engine.get('zoom_action') == 'start':
                    self._state = from_engine.get('state')
                elif from_engine.get('zoom_action') == 'stop':
                    logger.info('Zoom call ended on state: %s', self._state)
                    conn.send({ 'state': self._state })

            asyncio.get_event_loop().add_reader(
                conn.fileno(), engine_reader)

            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    self._state = msg.json().get('state')
                    logger.info('Web user set state: %s', self._state)
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    logger.error('ws connection closed with exception %s',
                                 ws.exception())

            self._user_connected = False
            logger.info('websocket connection closed')

            return ws
        return websocket_handler

    def get_user_connected(self):
        return self._user_connected


def start_http_server(conn):
    app = web.Application()
    aiohttp_jinja2.setup(
        app, loader=jinja2.FileSystemLoader('templates'))

    server_state = ServerState()
    websocket_handler = server_state.create_websocket_handler(conn)

    @aiohttp_jinja2.template('index.html')
    async def index(request):
        return { 'duplicate_connection': server_state.get_user_connected() }

    app.add_routes([
        web.get('/', index),
        web.get('/zoom', zoom),
        web.get('/favicon.ico', favicon),
        web.static('/static', 'static'),
        web.static('/images', 'images'),
        web.get('/ws', websocket_handler),
    ])

    context = ssl.SSLContext()
    context.load_cert_chain(credentials.CERTFILE, credentials.KEYFILE)
    logger.info("Starting HTTP Server")
    web.run_app(app, ssl_context=context)
