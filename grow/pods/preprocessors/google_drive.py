from googleapiclient import discovery
from googleapiclient import errors
from grow.common import oauth
from grow.common import utils
from grow.pods.preprocessors import base
from protorpc import messages
import bs4
import cStringIO
import csv
import html2text
import httplib2
import json
import logging
import os

OAUTH_SCOPE = 'https://www.googleapis.com/auth/drive'

# Silence extra logging from googleapiclient.
discovery.logger.setLevel(logging.WARNING)


class BaseGooglePreprocessor(base.BasePreprocessor):

  def _create_service(self):
    credentials = oauth.get_credentials(
        scope=OAUTH_SCOPE, storage_key='Grow SDK')
    http = httplib2.Http(ca_certs=utils.get_cacerts_path())
    http = credentials.authorize(http)
    return discovery.build('drive', 'v2', http=http)

  def run(self):
    try:
      self.download(self.config)
    except errors.HttpError as e:
      self.logger.error(str(e))


class GoogleDocsPreprocessor(BaseGooglePreprocessor):
  KIND = 'google_docs'

  class Config(messages.Message):
    path = messages.StringField(1)
    id = messages.StringField(2)
    convert = messages.BooleanField(3)

  def download(self, config):
    doc_id = config.id
    path = config.path
    ext = os.path.splitext(config.path)[1]
    convert_to_markdown = ext == '.md' and config.convert is not False
    service = self._create_service()
    resp = service.files().get(fileId=doc_id).execute()
    for mimetype, url in resp['exportLinks'].iteritems():
      if mimetype.endswith('html'):
        resp, content = service._http.request(url)
        if resp.status != 200:
          self.logger.error('Error downloading Google Doc: {}'.format(path))
          break
        soup = bs4.BeautifulSoup(content, 'html.parser')
        content = unicode(soup.body)
        if convert_to_markdown:
          h2t = html2text.HTML2Text()
          content = h2t.handle(content)
        content = content.encode('utf-8')
        self.pod.write_file(path, content)
        self.logger.info('Downloaded Google Doc -> {}'.format(path))


class GoogleSheetsPreprocessor(BaseGooglePreprocessor):
  KIND = 'google_sheets'

  class Config(messages.Message):
    path = messages.StringField(1)
    id = messages.StringField(2)
    gid = messages.IntegerField(3)

  def download(self, config):
    path = config.path
    sheet_id = config.id
    sheet_gid = config.gid
    service = self._create_service()
    resp = service.files().get(fileId=sheet_id).execute()
    ext = os.path.splitext(self.config.path)[1]
    convert_to = None
    if ext == '.json':
      ext = '.csv'
      convert_to = '.json'
    for mimetype, url in resp['exportLinks'].iteritems():
      if not mimetype.endswith(ext[1:]):
        continue
      if self.config.gid:
        url += '&gid={}'.format(self.config.gid)
      resp, content = service._http.request(url)
      if resp.status != 200:
        self.logger.error('Error downloading Google Sheet: {}'.format(path))
        break
      if convert_to == '.json':
        fp = cStringIO.StringIO()
        fp.write(content)
        fp.seek(0)
        reader = csv.DictReader(fp)
        content = json.dumps([row for row in reader])
      self.pod.write_file(path, content)
      self.logger.info('Downloaded Google Sheet -> {}'.format(path))
