import hashlib, urllib, pickle
from datetime import datetime, timedelta
from dropbox import rest
from flask import g
from storage import storage
from util import datetime_from_dropbox

def _md5(input):
    if isinstance(input, unicode):
        input = input.encode('utf-8')

    return hashlib.md5(input).hexdigest()

class server_store(object):
    def __init__(self):
        try:
            self.storage = storage(storage.ST_REDIS)
        except:
            if not g.debug:
                g.logger.error('Failed to create a connection to Redis: Use file-based storage instead.')
            self.storage = storage(storage.ST_FILE)    

    def get(self, key, default_value=None):
        return self.storage.get(key, default_value)

    def set(self, key, value):
        return self.storage.set(key, value)

    def remove(self, key):
        return self.storage.remove(key)

    def get_file_content(self, dbx_file):
        hash_key = 'content@'+str(g.author_uid)+'@'+_md5(dbx_file.path)+'@'+dbx_file.rev

        content = self.storage.get(hash_key)
        if not content:
            content = g.author.dropbox_client.get_file(dbx_file.path, rev=dbx_file.rev)
            self.storage.set(hash_key, content)
       
        return content

    def get_direct_link(self, dbx_file):
        hash_key = 'direct_link@'+str(g.author_uid)+'@'+_md5(dbx_file.path)+'@'+dbx_file.rev
        
        content = self.storage.get(hash_key)
        if content:
            # if cached link exist and it expires after 1 hour: re-use it.
            tokens = content.split('|')
            expires = datetime_from_dropbox(tokens[1])

            td =  expires - datetime.utcnow()
            total_seconds = (td.seconds + td.days * 24 * 3600)
            if total_seconds > 3600:
                return tokens[0]

        media = g.author.dropbox_client.media(dbx_file.path)
        url = urllib.unquote(media['url'])
        expires = media['expires']

        self.storage.set(hash_key, url+'|'+expires)

        return url

    def get_image_thumbnail(self, dbx_file, thumbnail_size):
        hash_key = 'thumbmail-'+str(thumbnail_size)+'@'+str(g.author_uid)+'@'+_md5(dbx_file.path)+'@'+dbx_file.rev

        content = self.storage.get(hash_key)
        if not content:
            content = g.author.dropbox_client.thumbnail(dbx_file.path, size=thumbnail_size).read()
            self.storage.set(hash_key, content)

        return content

    def get_dir_metadata(self, md_no_contents):
        # note that, root directory (/) does not contain 'rev' field.
        hash_key = 'dir_metadata@'+str(g.author_uid)+'@'+_md5(md_no_contents['path'])+'@'+md_no_contents.get('rev', 'root')

        cached_md = self.storage.get(hash_key)        
        if cached_md:
            cached_md = pickle.loads(cached_md)

            try:
                md = g.author.dropbox_client.metadata(cached_md['path'], list=True, include_deleted=False, hash=cached_md['hash'])
            except rest.ErrorResponse as er:
                if er.status == 304:
                    # the cache is still valid: use it
                    return cached_md
                elif er.status == 404:
                    return None
                else:
                    raise        
                    
        try:
            content = g.author.dropbox_client.metadata(md_no_contents['path'], list=True, include_deleted=False)
            self.storage.set(hash_key, pickle.dumps(content))
        except rest.ErrorResponse as er:
            if er.status == 404:
                return None
            else:
                raise

        return content
