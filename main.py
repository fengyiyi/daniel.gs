import os, datetime
from flask import Flask, abort, url_for, g, redirect, request, flash, Response
from render import render, render_string
from users import *
from mime import *
from util import cached_property
from server_store import server_store
from dropbox import rest

app = Flask(__name__)

def init_process():
    import sys
    if '-debug' in sys.argv[1:]:    
        app.debug = True

    if '-timemetric' in sys.argv[1:]:
        app.config['timemetric'] = True

    # load the config file if exists
    app.config.from_pyfile('app.config', silent=True)

    from util import get_file_log_handler, get_email_log_handler
    app.logger.addHandler(get_file_log_handler(app.debug))
    #if not app.debug:
    #    app.logger.addHandler(get_email_log_handler())

    app.before_request(init_connection)
    app.after_request(cleanup_connection)

    init_mime()

def init_connection():
    uid_map = {
        'daniel': 75535935
    }

    g.connection_start = datetime.datetime.now()

    # fundamental components
    g.app = app    
    g.logger = app.logger
    g.debug = app.debug
    g.args = request.args

    # set uid of author account
    g.author_uid = uid_map['daniel']

    # set up client-side and server-side storage
    from storage import storage
    # server-side storage: files or REDIS
    g.server_store = server_store()
    # client-side storage: HTTP session
    g.client_store = storage(storage.ST_HTTP_SESSION)

    # Dropbox file metadata cache
    from dbx import dbx_open
    g.open = dbx_open

    # user and author account
    g.user = None
    g.author = None
    if not request.path.startswith('/!user'):
        # user account
        g.user = get_current_user()

        # author account
        g.author = get_author()
        # if author account is not connected:
        if g.author is None:            
            if g.user is None:                
                # make the current user to login
                return redirect(url_for('user_login'))
            else:                   
                if is_current_user_author():
                    # if the current user is author:
                    # update the author's access token to server-storage
                    update_author_token()
                    g.author = get_author()
                    if g.author is None:
                        g.logger.error('Failed to connect author account.')
                        return 'Failed to connect author account.', 500
                else:
                    # if the current user is not author: just fail
                    g.logger.error('Failed to connect author account.')
                    return 'Author account was not connected.', 500

def cleanup_connection(res):
    if g.app.config.get('timemetric', False):
        print 'Connection time: '+str(datetime.datetime.now()-g.connection_start)

    return res

@app.route('/')
@app.route('/<path:path>')
def view(path=''):
    if app.debug and request.args.get('md', None) == '1':
        md = g.author.dropbox_client.metadata(path, list=True, include_deleted=False)
        return Response(str(md), mimetype='application/json')

    g.file = g.open(path)

    # file staring with '!' is author-access only
    if g.file and not is_current_user_author():
        for t in g.file.path.split('/'):
            if t.startswith('!'):
                return abort(401)


    if g.file is None and not 'edit' in request.args:
        # File Not Found error
        return abort(404)    

    # handle directory path
    if g.file and g.file.is_dir:
        df = g.file.get_file(g.file.dirinfo.default_file)
        if df and not 'browse' in request.args:
            return view(df.path)
        else:
            return render('browse.html')

    # deleting a file
    if g.file and 'delete' in request.args:
        # only author account can delete files
        if not is_current_user_author():
            return abort(401)        

        prev_url = request.args.get('purl', '/')

        g.author.dropbox_client.file_delete(g.file.path)

        return redirect(prev_url)


    # editing file content
    if not g.file or (g.file.is_editable and 'edit' in request.args):
        # only author account can edit the contents
        if not is_current_user_author():
            return abort(401)

        prev_url = request.args.get('purl', '/')
        title = g.file.file_name if g.file else os.path.basename(request.path)
        title += ' - edit' if g.file else ' - create'
        mime_type = request.args.get('mime', None)
        if not mime_type:
            mime_type = g.file.mime_type if g.file else get_mime_type(request.path)
        content = g.file.content if g.file else ''

        return render('edit.html', prev_url=prev_url, title=title, mime_type=mime_type, content=content)

    # image files
    if g.file.is_image:
        tn_size = request.args.get('tn', None)
        if tn_size:
            # stream thumbnail data
            return Response(g.file.thumbnail(size=tn_size), mimetype='image/jpeg')
        else:
            # redirect to Dropbox direct link
            return redirect(g.file.direct_link)

    # CSS/JavaScript files
    if g.file.mime_type in ['text/css', 'application/x-javascript', 'text/javascript']:
        # redirect to Dropbox direct link
        return redirect(g.file.direct_link)    

    # unknown type files
    if g.file.is_renderable:
        # if the content is renderable: render the contents
        return Response(g.file.rendered_content, mimetype='text/html')
    
    # by default, just stream the un-altered content
    return Response(g.file.content, mimetype=g.file.mime_type)

@app.route('/<path:path>', methods=['POST'])
def update(path):
    if not is_current_user_author():
        return abort(401)

    prev_url = request.form.get('prev_url', '/')

    g.file = g.open(path)
    content = request.form['value']
    if g.file:
        g.file.write(content)
        flash('The file was successfully updated: '+path)
    else:
        g.author.dropbox_client.put_file(path, content, overwrite=True)

    return redirect(prev_url)

@app.route('/!user/login')
def user_login():
    # returning url
    prev_url = request.args.get('purl', '/')

    current_user = get_current_user()
    if not current_user:
        return redirect(create_login_url(url_for('user_login_callback', _external=True, purl=prev_url)))
    else:
        return redirect(prev_url)

@app.route('/!user/login_cb')
def user_login_callback():
    if login(request.args.get('oauth_token', None)):
        # redirect to previous url
        return redirect(request.args.get('purl', '/'))
    else:
        # failed to authenticate the user
        return 'Failed to authorize user.', 500

@app.route('/!user/logout')
def user_logout():
    # returning url
    prev_url = request.args.get('purl', '/')

    logout()

    return redirect(prev_url)

@app.errorhandler(rest.ErrorResponse)
def error(err):
    if err.status == 503:        
        return 'API rate limit exceeded. Please try later.', 500
    else:
        if not g.debug:
            return 'Internal Error (Dropbox)', 500
        else:
            return app.handle_exception(err)

@app.errorhandler(Exception)
@app.errorhandler(500)
def error(err):
    if not g.debug:
        import traceback
        g.logger.error(traceback.format_exc(err))
        return 'Internal Error', 500
    else:
        return app.handle_exception(err)

@app.context_processor
def register_cp():

    def _enumerate(patterns, index=0, count=5, sort_key='modified', sort_reverse=True, excludes=[]):
        df = g.file if g.file.is_dir else g.file.parent
        if not df:
            raise Exception('Failed to locate the parent directory: '+g.file.path)
        return df.get_files(patterns=patterns, index=int(index), count=int(count), sort_key=sort_key, sort_reverse=sort_reverse, excludes=excludes)

    def _render(file_path):
        if not file_path.startswith('/'):
            # make it a full-path
            if g.file.is_dir:        
                file_path = os.path.join(g.file.path, file_path)
            else:
                file_path = os.path.join(os.path.dirname(g.file.path), file_path)

        df = g.open(file_path)
        if not df:
            return 'File not found: '+file_path if g.debug else ''    

        return df.rendered_content

    def _create_edit_url(file_path):
        if not file_path.startswith('/'):
            # make it a full-path
            if g.file.is_dir:        
                file_path = os.path.join(g.file.path, file_path)
            else:
                file_path = os.path.join(os.path.dirname(g.file.path), file_path)

        return file_path+'?edit&purl='+request.path
    
    return dict(
        enumerate=_enumerate,
        render=_render,
        create_edit_url=_create_edit_url,
    )
    

init_process()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)    
