from dotenv import load_dotenv
from framework.logger.providers import get_logger
from quart import Quart
from routes.health import health_bp
from utilities.provider import ContainerProvider
from framework.abstractions.abstract_request import RequestContextProvider
from framework.di.static_provider import InternalProvider
from framework.serialization.serializer import configure_serializer

from services.gateway import ApiGateway

load_dotenv()

app = Quart(__name__)
logger = get_logger(__name__)


ContainerProvider.initialize_provider()
InternalProvider.bind(ContainerProvider.get_service_provider())


container = ContainerProvider.get_service_provider()
proxy = ApiGateway(service_provider=container)

proxy.configure(app=app)
proxy.build_maps()

app.register_blueprint(health_bp)


@app.before_serving
async def startup():
    RequestContextProvider.initialize_provider(
        app=app)


@app.after_request
def after_request(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = '*'
    response.headers['Access-Control-Allow-Methods'] = '*'
    return response


configure_serializer(app)


if __name__ == '__main__':
    app.run(debug=True, port='5051')
