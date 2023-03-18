import datetime
import json
import os
from dataclasses import dataclass
from pathlib import Path

from blacksheep import Application, Response, Request, Content

import redis.asyncio as redis
from haikunator import Haikunator


app = Application()
RCLIENT = redis.Redis.from_url(os.environ.get('REDIS_URL', 'redis://localhost:6379/0'))

homepage = Path(__file__).parent / 'home.html'
with homepage.open('rb') as fh:
  HOME_CONTENT = fh.read()


@app.router.get("/")
async def home():
  return Response(200, content=Content(b"text/html", HOME_CONTENT))


@app.router.post("/")
async def transfer(request: Request):
  data = await request.form()

  status_code = 200
  ret = {
    "action": data['action'],
    "status": None,
  }

  if data['action'] == 'store':
    haikunator = Haikunator()
    key = haikunator.haikunate()

    secs = 15 * 60
    await RCLIENT.setex(key, secs, data.get("file", ""))
    expiration = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=secs)

    await RCLIENT.setex(key + '-salt', secs, data.get("salt", ""))

    ret['key'] = key
    ret['status'] = 'stored'
    ret['expiration'] = expiration.isoformat()

  elif data['action'] == 'get':
    key = data.get('key')
    if key:
      value = await RCLIENT.get(key)
      salt = await RCLIENT.get(key + '-salt')
      if value and salt:
        ret['status'] = 'available'
        ret['salt'] = salt.decode()
        ret['file'] = value.decode()
        await RCLIENT.delete(key)

      else:
        ret['status'] = 'expired key'
        status_code = 400

    else:
      ret['status'] = 'key required'
      status_code = 400

  else:
    ret['status'] = 'Unknown Action'
    status_code = 400

  return Response(status_code, content=Content(b"application/json", json.dumps(ret).encode()))
