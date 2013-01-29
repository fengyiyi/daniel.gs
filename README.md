# daniel.gs

## Dropbox as a Web Server

My [Dropbox][1] storage acts like a Web Server. If I sync any files in my Dropbox storage, they can be accessed through corresponding URLs. 

For example, see these files:

- [/sample/image1.jpg](/sample/image1.jpg)
- [/sample/markdown1.md](/sample/markdown1.md) - makrdown files (*.md or *.markdown) are automatically converted into HTML rendering.
- [/sample/template1.html](/sample/template1.html) - template files (*.html) are rendered using [Jinja 2][3].

All these files are located in the corresponding path under my [Dropbox][1] storage.

## Applications

Currently the following types of services can be created:

- Personal/commercial web-sites
- Blogs
- Web photo albums
- Web documentation pages
- And, many other applications

All you need to create these services are just your [Dropbox][1] account.

## Back-end Technologies

### Storage

All contents shown in this web-site are stored and retrieved directly from my personal [Dropbox][1] storage. When I modify any files from my iPhone, laptop, or, my desktop PC, those are automatically updated in this web-site.

### Web Servers

I'm using [Flask][2] to generate the web-pages and contents. And, based on [Jinja 2][3], all contents are dynamically composed and re-organized. All services are running upon [nginx][5] w/ [uWSGI][6] application container, hosted by [Amazon EC2][4] which is low-cost and easily scalable.

### Scriptability

I also created a set of supporting APIs (attributes or functions) that can be used in [Jinja 2][3] template files. This includes:

- Direct access to another files
- Rendering file contents
- Thunmbnailing images
- Direct streaming from Dropbox files
- Enumerating sorted sub-files inside a directory

Each directory can define its properties in dirinfo.json file such as default template page. 

### Content Caching

Contents are cached using [Redis][7] database to minimize latency and uncessary network waste against Dropbox servers.

## Future Plans

Web-service that supports multiple Dropbox user accounts is coming on the way.

[1]: http://www.dropbox.com/ "Dropbox"
[2]: http://flask.pocoo.org/ "Flask"
[3]: http://jinja.pocoo.org/ "Jinja 2"
[4]: http://aws.amazon.com/ec2/ "Amazon EC2"
[5]: http://nginx.org/ "nginx"
[6]: http://projects.unbit.it/uwsgi/ "uWSGI"
[7]: http://redis.io "Redis"
