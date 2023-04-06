import os
import json
import logging
import hvac
from flask import Flask, jsonify, request, abort

basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.logger.setLevel(logging.INFO)

basepath = os.path.dirname(__file__)

envVars = ['VAULT_ADDR', 'VAULT_SECRETS_PREFIX', 'VAULT_ROLE']

for ii in envVars:
  if ii not in os.environ:
    app.logger.error("Required environment variable %s isn't set. Exiting...", ii)
    exit(1)

try:
  client = hvac.Client(
      url=os.environ.get("VAULT_URL"))

  role = os.environ.get("VAULT_ROLE")
  with open('/var/run/secrets/kubernetes.io/serviceaccount/token', 'r', encoding="utf-8") as file_object:
    jwt = file_object.read()
  hvac.api.auth_methods.Kubernetes(client.adapter).login(role=role, jwt=jwt)
except:
  app.logger.error("Failed to connect to Vault")
else:
  app.logger.info("Successfully connected to Vault")


def return_ok(data):
  response = jsonify(data)
  response.content_type = 'application/json'
  response.status_code = 200

  app.logger.info('Sent response - Content-Type: %s, Status-code: %s, Data: %s ',
                  response.content_type, response.status_code, json.dumps(data))

  return response


@app.before_request
def save_request():
  request_data = request.get_json(silent=True)
  app.logger.info('Received request - Client: %s, Path: %s, Method: %s, Content-Type: %s, Data: %s',
    request.remote_addr, request.path, request.method, request.content_type, json.dumps(request_data))


@app.errorhandler(400)
def bad_request(error):
  if 'message' in error.description:
    data = {'message': error.description['message']}
  else:
    data = {"message": "Error"}

  response = jsonify(data)
  response.content_type = 'application/json'
  response.status_code = 400

  app.logger.error('Sent response - Content-Type: %s, Status-code: %s, Data: %s ',
    response.content_type, response.status_code, json.dumps(data))

  return response


@app.errorhandler(404)
def resource_not_found(error):
  if 'message' in error.description:
    data = {'message': error.description['message']}
  else:
    data = {"message": "Error"}

  response = jsonify(data)
  response.content_type = 'application/json'
  response.status_code = 404

  app.logger.error('Sent response - Content-Type: %s, Status-code: %s, Data: %s ',
                  response.content_type, response.status_code, json.dumps(data))

  return response


@app.errorhandler(500)
def server_error(error):
  if 'message' in error.description:
    data = {'message': error.description['message']}
  else:
    data = {"message": "Error"}

  response = jsonify(data)
  response.content_type = 'application/json'
  response.status_code = 500

  app.logger.error('Sent response - Content-Type: %s, Status-code: %s, Data: %s ',
                  response.content_type, response.status_code, json.dumps(data))

  return response


@app.route('/health', methods=['GET'])
def get_health():
  try:
    client.secrets.kv.v2.update_metadata(
      path = os.environ.get("VAULT_SECRETS_PREFIX") + '/_ping',
      max_versions = 1
    )
    client.secrets.kv.v2.create_or_update_secret(
      path = os.environ.get("VAULT_SECRETS_PREFIX") + '/_ping',
      secret = {"data": 'ping'}
    )
  except:
    message = 'Something is wrong with Vault connection'
    app.logger.error(message)
    abort(500, {'message': message})
  else:
    message = 'Vault connection is ok'
    data = {'message': message}
    return return_ok(data)


@app.route('/sync', methods=['POST'])
def post_sync():
  request_data = request.get_json(silent=True)
  return_data = {
            "apiVersion": "admission.k8s.io/v1",
            "kind": "AdmissionReview",
            "response": {
              "uid": request_data['request']['uid'],
              "allowed": True
            }
          }
  secret_namespace = request_data['request']['namespace']
  secret_name = request_data['request']['name']
  secret_data = request_data['request']['object']['data']
  secret_path = os.environ.get("VAULT_SECRETS_PREFIX") + '/' + secret_namespace + '/' + secret_name
  secret_labels = request_data['request']['object']['metadata']['labels']
  sync_secret = False

  label_selector = {}

  if os.environ.get('SECRETS_LABEL_SELECTOR') not in os.environ:
    sync_secret = True
  else:
    label_selector_list = os.environ.get('SECRETS_LABEL_SELECTOR').split(',')
    for i in label_selector_list:
      label_selector[i.split('=')[0]] = i.split('=')[1]

    for key, value in list(label_selector.items()):
      if key in secret_labels.keys():
        if value != secret_labels[key]:
          sync_secret = False
          break
      else:
        sync_secret = False
        break
      sync_secret = True

  if sync_secret:
    try:
      client.secrets.kv.v2.update_metadata(
          path = secret_path,
          max_versions = 3,
      )
      client.secrets.kv.v2.create_or_update_secret(
        path = secret_path,
        secret = {'data': secret_data}
      )
    except:
      app.logger.error("Failed to write to Vault. Path: %s", secret_path)
    else:
      app.logger.info("Successfuly wrote to Vault. Path: %s", secret_path)
  return return_ok(return_data)


if __name__ == '__main__':
    app.run()
