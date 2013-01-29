import os, markdown, json, hashlib
from fnmatch import fnmatch
import markdown
from datetime import datetime
from flask import g, Markup
from dropbox import rest
from util import datetime_from_dropbox, cached_property, get_file_name, get_file_ext
from render import render, render_string

_dirinfo_file_name = 'dirinfo.json'

# returns UTF-8 encoded string (str)
def _encode_str(s, encoding='utf-8'):
    if isinstance(s, unicode):
        return s.encode(encoding)
    elif isinstance(s, str):
        return s
    else:
        raise TypeError('Expected string or Unicode object, {0} found'.format(s.__class__.__name__))

# returns UTF-8 decoded unicode string (unicode)
def _decode_str(s, encoding='utf-8'):
    if isinstance(s, unicode):
        return s
    elif isinstance(s, str):
        return s.decode(encoding)
    else:
        raise TypeError('Expected string or Unicode object, {0} found'.format(s.__class__.__name__))

class _dirinfo:
    def __init__(self, data):
        self.default_file = data.get('default_file', 'index.html')

class dbx_file(object):
    def __init__(self, **entries):
        if entries.get('is_deleted', False):
            raise Exception('The path is deleted: '+entries['path'])

        # setup basic info
        self.path = entries['path']
        self.is_dir = entries.get('is_dir', False)
        self.rev = entries.get('rev', '0')
        self.hash = entries.get('hash', '') # hash value for directory
        self.bytes = entries.get('bytes', 0)
        self._modified = entries.get('modified', None)

        # self._files: internal container for metadata contents of sub-files
        self._files = dict()
        if self.is_dir:
            # setup sub-file dict
            for c in entries.get('contents', list()):
                if not c.get('is_deleted', False):
                    self._files[get_file_name(c['path']).lower()] = c

        # self._dbx_files: internal cache for dbx_file objects of sub-files
        self._dbx_files = dict()

    @cached_property
    def dirinfo(self):
        if not self.is_dir:
            raise Exception('The path is not a directory: '+self.path)

        df = self.get_file(_dirinfo_file_name)
        return _dirinfo(json.loads(df.content)) if df else _dirinfo(dict())

    @cached_property
    def modified(self):
        if self._modified:
            return datetime_from_dropbox(self._modified)
        else:
            return datetime.min

    @cached_property
    def mime_type(self):
        if self.is_dir:
            raise Exception('The path a directory: '+self.path)

        from mime import get_mime_type
        return get_mime_type(self.path)

    @cached_property
    def file_name(self):
        return get_file_name(self.path)

    @cached_property
    def ext(self):
        if self.is_dir:
            raise Exception('The path is a directory: '+self.path)

        return get_file_ext(self.path)

    @cached_property
    def file_name_without_ext(self):
        return os.path.splitext(self.file_name)[0]
    
    @cached_property
    def is_editable(self):
        if self.is_dir or not self.mime_type:
            return False

        if self.mime_type.startswith('text/'):
            return True
        if self.mime_type in ['application/json', 'application/x-javascript']:
            return True

        return False

    @cached_property
    def is_renderable(self):
        if self.is_dir:
            return False

        if self.mime_type is None:
            return False
        if self.mime_type.startswith('text/'):
            return True
        if self.mime_type.startswith('image/'):
            return True
        if self.mime_type in ['application/json']:
            return True
        return False

    @cached_property
    def is_image(self):
        if self.is_dir or not self.mime_type:
            return False

        return self.mime_type.startswith('image/')

    @cached_property
    def content(self):
        if self.is_dir:
            raise Exception('The path is a directory: '+self.path)
        
        return g.server_store.get_file_content(self)

    @cached_property
    def rendered_content(self):
        if self.is_dir:
            raise Exception('The path is a directory: '+self.path)

        if not self.mime_type:
            raise Exception('Cannot render the content: '+self.path)

        if self.mime_type == 'text/x-markdown':
            return render('view_md.html', file=self, content=Markup(markdown.markdown(self.content)))
        elif self.ext == '.html':
            return render_string(self.content)
        else:
            return self.content

    @cached_property
    def direct_link(self):
        if self.is_dir:
            raise Exception('The path is a directory: '+self.path)

        return g.server_store.get_direct_link(self)

    def thumbnail(self, size):
        if self.is_dir:
            raise Exception('The path is a directory: '+self.path)

        return g.server_store.get_image_thumbnail(self, size)

    def write(self, content):
        if self.is_dir:
            raise Exception('The path is a directory: '+self.path)

        g.author.dropbox_client.put_file(self.path, content, overwrite=True)

    def get_file(self, file_name):
        if not self.is_dir:
            raise Exception('The path is not a directory: '+self.path)

        file_name = file_name.lower()
        df = self._dbx_files.get(file_name, None)
        if df:
            return df

        f = self._files.get(file_name, None)
        if f and not f.get('is_dir', False):
            df = dbx_file(**f)
            self._dbx_files[file_name] = df
            return df

        return None

    def get_files(self, patterns='*', index=0, count=-1, sort_key=None, sort_reverse=False, excludes=[]):
        if not self.is_dir:
            raise Exception('The path is not a directory: '+self.path)

        if index < 0: index = 0
        if count < 0: count = 1

        if not isinstance(patterns, list):
            patterns = [patterns]

        if not isinstance(excludes, list):
            excludes = [excludes]

        # change all patterns to lower-case
        skip_pattern_test = False
        for i in xrange(len(patterns)):
            patterns[i] = patterns[i].lower()
            if patterns[i] == '*':
                skip_pattern_test = True
        for i in xrange(len(excludes)):
            excludes[i] = excludes[i].lower()

        # apply filter based on patterns
        files = []
        for f, c in self._files.items():
            # exclude dir entries
            if c.get('is_dir', False):
                continue

            # test against exclude patterns
            exc = False
            for e in excludes:
                if fnmatch(f, e):
                    exc = True
                    break
            if exc: 
                continue

            # test against patterns
            if skip_pattern_test:
                files.append(c)
            else:
                for p in patterns:
                    if fnmatch(f, p):
                        files.append(c)
                        break

        # sort files
        if sort_key == 'modified':
            # sorting by modified time
            files.sort(key=lambda x: datetime_from_dropbox(x[sort_key]), reverse=sort_reverse)
        elif sort_key:
            # sorting by other key
            files.sort(key=lambda x: x[sort_key].lower(), reverse=sort_reverse)

        # enumerate
        if len(files):
            # adjust 'index' and 'count'
            filtered_count = len(files)
            if index >= filtered_count: index = filtered_count - 1
            if index+count > filtered_count: count = filtered_count - index

            return [self.get_file(get_file_name(c['path'])) for c in files[index:index+count]]
        else:
            return []

    @cached_property
    def parent(self):
        return g.open(os.path.dirname(self.path))

    def __str__(self):
        return str(self.__dict__)

    def __repr__(self):
        return str(self.__dict__)

def dbx_open(path, file_name=None, include_deleted=False):
    # normalize path
    if file_name:
        path = os.path.join(path, file_name)
    if not path.startswith('/'):
        path = '/'+path

    # lower-case path name for cache look-uo
    path_l = path.lower()

    # connection file cache: cache for each connection
    if not hasattr(g, '_conn_file_cache'):
        g._conn_file_cache = dict()
    else:
        cache = g._conn_file_cache.get(path_l, None)
        if cache:
            return cache

    # author account must be connected.
    if not g.author or not g.author.dropbox_client:
        raise Exception('Author account was not connected.')

    # check if parent directory object exists
    # this test will just fail if the path is a directory because os.path.dirname() will return the same path.
    parent_path = os.path.dirname(path_l)
    parent_cache = g._conn_file_cache.get(parent_path, None)
    if parent_cache:
        # retrieve metadata from parent direct object (without connecting to Dropbox server)
        df = parent_cache.get_file(os.path.basename(path_l))
        if df:
            g._conn_file_cache[path_l] = df
            return df

    # retrieve metadata from Dropbox server without listing all sub-files
    try:
        md = g.author.dropbox_client.metadata(path, list=False, include_deleted=False)

        if md.get('is_deleted', False):
            g._conn_file_cache[path_l] = None
            return None

        if md.get('is_dir', False):
            # if this is a directory, try cached-data from server-store (for full metadata including sub-files)
            md = g.server_store.get_dir_metadata(md)
            if not md:
                # this must not fail
                raise Exception('Failed to get metadata with full-listing: '+path)
            
        # make dropbox file object and return it
        df = dbx_file(**md)
        g._conn_file_cache[path_l] = df
        return df
    except rest.ErrorResponse as er:
        if er.status == 404:
            g._conn_file_cache[path_l] = None
            return None
        else:
            raise

    try:
        md = g.author.dropbox_client.metadata(path, list=True, include_deleted=False)
        df = dbx_file(**md)
        g._conn_file_cache[path_l] = df
        return df
    except rest.ErrorResponse as er:
        if er.status == 404:
            g._conn_file_cache[path_l] = None
            return None
        else:
            raise

class dbx_client(object):   
    def __init__(self, session):
        from dropbox import client
        self._client = client.DropboxClient(session=session)

    def account_info(self):
        g.logger.debug('dbx_client.account_info()')
        
        return self._client.account_info()

    def file_delete(self, path):
        path = _encode_str(path)
        
        g.logger.debug('dbx_client.file_delete({0})'.format(path))
        
        return self._client.file_delete(path)

    # returns the content of the file
    def get_file(self, path, rev=None, encoding='utf-8'):
        path = _encode_str(path)
        
        g.logger.debug('dbx_client.get_file({0}, {1}, {2})'.format(path, rev, encoding))
        
        content = self._client.get_file(path, rev).read()
        if encoding:
            return _decode_str(content, encoding=encoding)
        else:
            return content

    def media(self, path):
        path = _encode_str(path)
        
        g.logger.debug('dbx_client.media({0})'.format(path))
        
        return self._client.media(path)

    def metadata(self, path, list=True, file_limit=25000, hash=None, rev=None, include_deleted=False):
        path = _encode_str(path)

        g.logger.debug('dbx_client.metadata({0}, list={1}, file_limit={2}, hash={3}, rev={4}, include_deleted={5})'.format(
            path, list, file_limit, hash, rev, include_deleted))
        
        return self._client.metadata(path, list=list, file_limit=file_limit, hash=hash, rev=rev, include_deleted=include_deleted)

    def put_file(self, path, file_obj, overwrite=False, parent_rev=None, encoding='utf-8'):
        path = _encode_str(path)

        g.logger.debug('dbx_client.put_file({0}, file_obj=({1}), overwrite={2}, parent_rev={3}, encoding={4})'.format(
            path, file_obj.__class__.__name__, overwrite, parent_rev, encoding))

        if isinstance(file_obj, file) or isinstance(file_obj, str):
            return self._client.put_file(path, file_obj=file_obj, overwrite=overwrite, parent_rev=parent_rev)
        elif isinstance(file_obj, unicode):
            # if provided file_obj is unicode string,convert it using specified encoding.
            # save converted content to the temporary file, and, upload it.
            import tempfile
            with tempfile.TemporaryFile() as tf:
                if encoding:
                    tf.write(_encode_str(file_obj, encoding))
                else:
                    tf.write(file_obj)

                tf.flush()
                tf.seek(0)

                return self._client.put_file(path, file_obj=tf, overwrite=overwrite, parent_rev=parent_rev)
        else:
            raise TypeError('Expected file, string, or Unicode object, {0} found.'.format(file_obj.__class__.__name__))

    def thumbnail(self, path, size='large', format='JPEG'):        
        path = _encode_str(path)

        g.logger.debug('dbx_client.thumbnail({0}, {1}, {2})'.format(path, size, format))
        
        return self._client.thumbnail(path, size=size, format=format)