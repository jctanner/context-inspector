"""External-Uvicorn fixture used because the installed TestClient hangs."""

from src.server.app import create_app
from src.server.config import Settings


app = create_app(settings=Settings.from_environment())
