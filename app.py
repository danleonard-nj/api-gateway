from dotenv import load_dotenv
from framework.logger.providers import get_logger
from quart import Quart

from routes.health import health_bp
from services.gateway import ApiGateway
from utilities.provider import ContainerProvider, add_container_hook

load_dotenv()


app = Quart(__name__)
logger = get_logger(__name__)


container = ContainerProvider.get_container()
proxy = ApiGateway(
    container=container)

proxy.configure(
    app=app)
proxy.build_maps()

app.register_blueprint(health_bp)


@app.after_request
def after_request(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = '*'
    response.headers['Access-Control-Allow-Methods'] = '*'
    return response


add_container_hook(app)


if __name__ == '__main__':
    app.run(debug=True, port='5051')
