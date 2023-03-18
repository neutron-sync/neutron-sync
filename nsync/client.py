import base64
import json
import os
from pathlib import Path

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

import httpx


class ApiClient:
  def __init__(self, server_url):
    self.server_url = server_url

  def transfer_files(self, password, *files):
    salt = os.urandom(16)
    salty = base64.urlsafe_b64encode(salt).decode()
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=480000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
    f = Fernet(key)

    data = {}
    for file in files:
      key = file.name
      with file.open('rb') as fh:
        data[key] = base64.urlsafe_b64encode(fh.read()).decode()

    token = f.encrypt(json.dumps(data).encode()).decode()

    response = httpx.post(self.server_url, data={'file': token, 'action': 'store', 'salt': salty})
    try:
      rdata = response.json()

    except:
      raise Exception(f'API Error: {response.status_code}\n{response.text}')

    if response.status_code != 200:
      raise Exception(f'API Error: {rdata}')

    self.last_data = rdata
    return rdata

  def download(self, password, storage_key):
    response = httpx.post(self.server_url, data={'action': 'get', 'key': storage_key})
    try:
      rdata = response.json()

    except:
      raise Exception(f'API Error: {response.status_code}\n{response.text}')

    if response.status_code != 200:
      raise Exception(f'API Error: {rdata}')

    self.last_data = rdata
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=base64.urlsafe_b64decode(rdata['salt']),
        iterations=480000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
    f = Fernet(key)
    files = f.decrypt(rdata['file'].encode())
    files = json.loads(files.decode())

    basedir = Path(f'ntransfer-{storage_key}')
    if not basedir.exists():
      basedir.mkdir()

    for name, content in files.items():
      filepath = basedir / name
      with filepath.open('wb') as fh:
        fh.write(base64.urlsafe_b64decode(content))

      print(f'Wrote: {filepath}')

    return rdata
