#!flask/bin/python

import string
import sys

from flask import Flask, jsonify, redirect, request
import pal.authentication.dummy_strategy as dummy_strategy
import pal.authentication.basic_strategy as basic_strategy
import pal.authorization.file_restrict as file_restrict
import pal.config.defaults as defaults
import pal.config.configure as configure
import pal.requests.client as client
import pal.requests.presigned as presigned
import pal.requests.symlink as symlink
from pal.requests.target import SymlinkTargetSpec

# Module variables
app = Flask(__name__)


@app.route('/')
def index():
    return "Index"

# Drew suggested we try to set ACLs. 
# Restrict access. 


@app.route('/<string:bucket_name>/<string:key_name>/restrict', methods=['POST'])
def restrict_object(bucket_name: string, key_name: string):
    print("Restricting object to  %s : %s" % (bucket_name, key_name))
    if 'username' in request.form:
        return file_restrict.add_restrict(request.form['username'], bucket_name, key_name)
    return "Stub"


@app.route('/<string:bucket_name>/<string:key_name>/release', methods=['POST'])
def release_object(bucket_name: string, key_name: string):
    print("Releasing object in  %s : %s" % (bucket_name, key_name))
    if 'username' in request.form:
        return file_restrict.remove_restrict(request.form['username'], bucket_name, key_name)
    return "Stub"


# Add new routes for default grabs


@app.route('/<string:bucket_name>/<string:key_name>', methods=['POST'])
def download_object(bucket_name: string, key_name: string):
    print("downloading object %s : %s" % (bucket_name, key_name))
    s3_client = __generate_client(request)
    presigned_download_url = presigned.get_presigned_download(
        s3_client,
        bucket_name,
        object_key=key_name
    )
    return redirect(location=presigned_download_url, code=303)

# Add new routes for presigned url requests, without direct download


@app.route('/<string:bucket_name>/<string:key_name>/presigned_post', methods=['POST'])
def get_presigned_post(bucket_name: string, key_name: string):
    print("presigned post: getting bucket:key %s : %s" % (bucket_name, key_name))
    s3_client = __generate_client(request)
    if __not_allowed_access(bucket_name, key_name, request):
        return "Sorry, you're not allowed."
    return presigned.get_presigned_upload(
        s3_client,
        bucket_name,
        object_key=key_name)


@app.route('/<string:bucket_name>/<string:key_name>/presigned_get', methods=['POST'])
def get_presigned_get(bucket_name: string, key_name: string):
    print("presigned url: getting bucket:key %s : %s" % (bucket_name, key_name))
    s3_client = __generate_client(request)
    if __not_allowed_access(bucket_name, key_name, request):
        return "Sorry, you're not allowed."
    return presigned.get_presigned_download(
        s3_client,
        bucket_name,
        object_key=key_name
    )


@app.route('/<string:bucket_name>/<string:key_name>/symlink', methods=['POST'])
def build_symlink(bucket_name: string, key_name: string):
    if 'target' not in request.form:
        return "Invalid request, need targetkey and targetbucket for symlink"
    s3_client = __generate_client(request)
    mount_point = None if 'mount_point' not in request.form else request.form['mount_point']
    symlink_target = SymlinkTargetSpec(request.form['target'], mount_point)
    symlink_built = symlink.build_symlink(s3_client, bucket_name, key_name, symlink_target)
    if not symlink_built:
        return "Symlink was not built"
    return (
        "Symlink created for target(%s) from source(%s)"
        % (request.form['target'], key_name)
    )

# These paths are for fall through routing when we don't have something defined.


@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def catch_all(path):
    return 'You want path: %s' % path


@app.route('/', defaults={'path': ''})
@app.route('/<path:path>', subdomain="<string:subdomain>")
def catch_all_subdomain(path, subdomain):
    return 'You want path: %s under subdomain: %s' % (path, subdomain)


def __generate_client(request):
    configs = configure.read_config()
    routing_endpoint = configs['routing_endpoint'] if 'routing_endpoint' in configs else defaults.S3_ENDPOINT

    if 'username' in request.form and 'password' in request.form:
        print("signing in user: %s: %s" % (request.form['username'], request.form['password']))
        return client.get_basic_client(request.form['username'], request.form['password'], routing_endpoint)
    else:
        return client.get_dummy_client(routing_endpoint)


def __not_allowed_access(request, bucket, key):
    if 'username' not in request.form:
        return False
    return file_restrict.can_access(request.form['bucket'], bucket, key)


def main(args):
    app.run(host='0.0.0.0')


def run():
    """Entry point for console_scripts
    """
    main(sys.argv[1:])


if __name__ == '__main__':
    run()
