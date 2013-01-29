import mimetypes

def init_mime():
	mimetypes.add_type('text/x-markdown', '.md')
	mimetypes.add_type('text/x-markdown', '.markdown')

def get_mime_type(url):
	mime_type, mime_encoding = mimetypes.guess_type(url)
	return mime_type