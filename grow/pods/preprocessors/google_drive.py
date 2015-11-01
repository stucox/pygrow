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

  def run(self, resp=None):
    try:
      self.download(self.config, resp=resp)
    except errors.HttpError as e:
      self.logger.error(str(e))


class GoogleDocsPreprocessor(BaseGooglePreprocessor):
  KIND = 'google_docs'

  class Config(messages.Message):
    path = messages.StringField(1)
    id = messages.StringField(2)
    convert = messages.BooleanField(3)

  def download(self, config, resp=None):
    doc_id = config.id
    path = config.path
    ext = os.path.splitext(config.path)[1]
    convert_to_markdown = ext == '.md' and config.convert is not False
    service = self._create_service()
    resp = resp or service.files().get(fileId=doc_id).execute()
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

  def download(self, config, resp=None):
    path = config.path
    sheet_id = config.id
    sheet_gid = config.gid
    service = self._create_service()
    resp = resp or service.files().get(fileId=sheet_id).execute()
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


class GoogleDriveFolderPreprocessor(BaseGooglePreprocessor):
  KIND = 'google_drive_folder'

  class Config(messages.Message):
    path = messages.StringField(1)
    id = messages.StringField(2)

  def run_google_sheets(self, id):
    config = GoogleSheetsPreprocessor.Config(
      path=os.path.join(self.config.path, id + '.csv'),
      id=id,
    )
    preprocessor = GoogleSheetsPreprocessor(pod=self.pod, config=config)
    preprocessor.run()

  def run_google_docs(self, id):
    config = GoogleDocsPreprocessor.Config(
      path=os.path.join(self.config.path, id + '.md'),
      id=id,
    )
    preprocessor = GoogleDocsPreprocessor(pod=self.pod, config=config)
    preprocessor.run()

  def download(self, config, resp=None):
    service = self._create_service()
    page_token = None
    folder_id = config.id
    while True:
      try:
        param = {}
        if page_token:
          param['pageToken'] = page_token
        children = service.children().list(
            folderId=folder_id, **param).execute()
        for child in children.get('items', []):
          file_id = child['id']
          resp = service.files().get(fileId=file_id).execute()
          print resp
          if resp['mimeType'] == 'application/vnd.google-apps.document':
            self.run_google_docs(file_id)
          elif resp['mimeType'] == 'application/vnd.google-apps.spreadsheet':
            self.run_google_sheets(file_id)
        page_token = children.get('nextPageToken')
        if not page_token:
          break
      except errors.HttpError, error:
        print 'An error occurred: %s' % error
        break
#    result = []
#    page_token = None
#    while True:
#      try:
#        param = {}
#        if page_token:
#          param['pageToken'] = page_token
#        files = service.files().list(**param).execute()
#        result.extend(files['items'])
#        page_token = files.get('nextPageToken')
#        if not page_token:
#          break
#      except errors.HttpError, error:
#        print 'An error occurred: %s' % error
#        break
#    return result
