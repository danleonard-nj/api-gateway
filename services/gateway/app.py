from dotenv import load_dotenv
from framework.abstractions.abstract_request import RequestContextProvider
from framework.di.static_provider import InternalProvider
from framework.logger.providers import get_logger
from framework.serialization.serializer import configure_serializer
from framework.swagger.quart.swagger import Swagger
from httpx2 import AsyncClient
from quart import Quart

from routes.health import health_bp
from services.gateway import ApiGateway
from utilities.provider import ContainerProvider

load_dotenv()

app = Quart(__name__)
logger = get_logger(__name__)

provider = ContainerProvider.get_service_provider()
proxy = ApiGateway(app, provider).build_maps()

app.register_blueprint(health_bp)

swagger = Swagger(
    app=app,
    title='Gateway')

swagger.configure()


@app.before_serving
async def startup():
    RequestContextProvider.initialize_provider(
        app=app)


@app.after_serving
async def shutdown():
    http_client = provider.resolve(AsyncClient)
    await http_client.aclose()


configure_serializer(app)


if __name__ == '__main__':
    app.run(debug=True, port='5051')
