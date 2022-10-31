from flask import Blueprint

health_bp = Blueprint('health_bp', __name__)


@health_bp.route('/api/health/alive')
def alive(container):
    return {'status': 'ok'}, 200


@health_bp.route('/api/health/ready')
def ready(container):
    return {'status': 'ok'}, 200
