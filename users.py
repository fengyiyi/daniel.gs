from flask import g
from util import cached_property

APP_KEY = '63m0ul0ffca32lv'
APP_SECRET = 't6l6rueu43fw3l4'
ACCESS_TYPE = 'app_folder'

def _create_dropbox_session():
	from dropbox import session

	dropbox_session = session.DropboxSession(APP_KEY, APP_SECRET, ACCESS_TYPE)
	if dropbox_session is None:
		raise Exception('Failed to create a Dropbox session.')		

	return dropbox_session

def _create_dropbox_client(dropbox_session):
	dropbox_client = None

	from dbx import dbx_client
	dropbox_client = dbx_client(dropbox_session)

	if dropbox_client is None:		
		raise Exception('Failed to create a Dropbox client.')

	return dropbox_client

class _dbx_token(object):
	def __init__(self, key=None, secret=None):
		self.key = key
		self.secret = secret

	@classmethod
	def store(cls, storage, key, token):
		storage.set(key, token.key+'|'+token.secret)

	@classmethod
	def restore(cls, storage, key):
		val = storage.get(key, None)
		if val:
			vals = val.split('|')
			if len(vals) == 2:
				return _dbx_token(vals[0], vals[1])
		return None

	@classmethod
	def remove(cls, storage, key):
		storage.remove(key)

class user(object):
	def __init__(self, access_token):
		self.dropbox_session = _create_dropbox_session()
		self.dropbox_session.set_token(access_token.key, access_token.secret)
		self.dropbox_client = _create_dropbox_client(self.dropbox_session)		

	@cached_property
	def uid(self):
		if not hasattr(self, '_account_info'):
			self._account_info = self.dropbox_client.account_info()

		return self._account_info['uid']

	@cached_property
	def name(self):
		if not hasattr(self, '_account_info'):
			self._account_info = self.dropbox_client.account_info()

		return self._account_info['display_name']

	@cached_property
	def is_author(self):
		return self.uid == g.author_uid

def get_current_user():
	try:
		access_token = _dbx_token.restore(g.client_store, 'ACCESS_TOKEN')
		if access_token:
			return user(access_token)
	except: pass
	return None

def get_author():
	try:
		access_token = _dbx_token.restore(g.server_store, 'ACCESS_TOKEN@'+str(g.author_uid))
		if access_token:
			return user(access_token)
	except: pass
	return None

def create_login_url(callback_url):
	ds = _create_dropbox_session()

	req_token = ds.obtain_request_token()
	_dbx_token.store(g.client_store, 'REQUEST_TOKEN', req_token)

	return ds.build_authorize_url(req_token, oauth_callback=callback_url)

def login(auth_key):
	# get last stored request key from session
	request_token = _dbx_token.restore(g.client_store, 'REQUEST_TOKEN')
	if request_token is None:
		g.logger.debug('Request token was not created.')
		return False

	if auth_key != request_token.key:
		g.logger.debug('Incorrect request key.')
		return False

	ds = _create_dropbox_session()
	access_token = ds.obtain_access_token(request_token)
	_dbx_token.store(g.client_store, 'ACCESS_TOKEN', access_token)

	return True

def logout():
	_dbx_token.remove(g.client_store, 'ACCESS_TOKEN')

def is_current_user_author():
	user = get_current_user()
	if user and user.uid == g.author_uid:
		return True
	return False

def update_author_token():
	if not is_current_user_author():
		raise Exception('Not authornized action.')

	access_token = _dbx_token.restore(g.client_store, 'ACCESS_TOKEN')
	if access_token is None:
		raise Exception('User was not authornized.')

	_dbx_token.store(g.server_store, 'ACCESS_TOKEN@'+str(g.author_uid), access_token)
