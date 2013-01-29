import os
from flask import g

class storage(object):

	# storage types
	ST_MEMORY = 0 		# based on 'dict' structure
	ST_MEMCACHE = 1		# based on 'memcached'
	ST_FILE = 2			# based on local files
	ST_REDIS = 3		# based on 'Redis' database
	ST_HTTP_SESSION = 4	# based on HTTP session storage

	def __init__(self, storage_type):
		self.storage_type = storage_type

		if storage_type == self.ST_MEMORY:
			self._storage = dict()
		elif storage_type == self.ST_MEMCACHE:
			import memcache
			self._storage = memcache.Client()
		elif storage_type == self.ST_FILE:
			self.cache_dir = 'cache'
			if not os.path.exists(self.cache_dir):
				os.makedirs(self.cache_dir)
		elif storage_type == self.ST_REDIS:
			import redis
			self._storage = redis.StrictRedis(
				host=g.app.config.get('REDIS_HOST', 'localhost'),
				port=g.app.config.get('REDIS_PORT', 6379),
				db=g.app.config.get('REDIS_DB', 0))
			# test connection
			self._storage.get('foobar')
		elif storage_type == self.ST_HTTP_SESSION:
			from flask import session
			session.permanent = True
			self._storage = session
		else:
			raise Exception('Unsupported storage type: '+str(storage_type))

	def get(self, key, default_value=None):
		if self.storage_type == self.ST_REDIS:
			v = self._storage.get(key)
			return v if v is not None else default_value
		elif self.storage_type == self.ST_FILE:
			path = os.path.join(self.cache_dir, key)
			if os.path.exists(path):
				with open(path, 'rb') as f:										
					return f.read()
			return default_value
		else:
			return self._storage.get(key, default_value)

	def set(self, key, value):
		if self.storage_type == self.ST_FILE:
			try:
				path = os.path.join(self.cache_dir, key)
				f = open(path, 'wb')
				f.write(value)
				return True
			except:
				return False
		elif self.storage_type in [self.ST_REDIS, self.ST_MEMCACHE]:
			self._storage.set(key, value)
			return True
		else:
			self._storage[key] = value
			return True

	def remove(self, key):
		if self.storage_type in [self.ST_MEMORY, self.ST_HTTP_SESSION]:
			try:
				del self._storage[key]
				return True
			except KeyError:
				return False
		elif self.storage_type == self.ST_FILE:
			try:
				os.remove(os.path.join(self.cache_dir, key))
				return True
			except:
				return False
		else:
			return self._storage.delete(key)