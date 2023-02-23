import json
from dataclasses import dataclass
from pathlib import Path

from blacksheep import Application, Response, Request, Content


app = Application()

homepage = Path(__file__).parent / 'home.html'
with homepage.open('rb') as fh:
  HOME_CONTENT = fh.read()


@app.router.get("/")
async def home():
  return Response(200, content=Content(b"text/html", HOME_CONTENT))


@app.router.post("/")
async def transfer(request: Request):
  files = await request.files()
  data = await request.form()

  status_code = 200
  ret = {
    "action": data['action'],
    "status": None,
  }

  if data['action'] == 'store':
    pass

  else:
    ret['status'] = 'Unknown Action'
    status_code = 400

  return Response(status_code, content=Content(b"application/json", json.dumps(ret).encode()))
