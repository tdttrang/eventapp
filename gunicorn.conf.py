disable_sendfile = True

def post_fork(server, worker):
    from gevent import monkey
    monkey.patch_all()