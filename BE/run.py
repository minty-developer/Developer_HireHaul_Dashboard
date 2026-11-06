import os

from dotenv import load_dotenv

load_dotenv()

from app import create_app  # noqa: E402  (.env를 먼저 읽어야 설정에 반영된다)

app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "run:app",
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "5000")),
        reload=app.state.config["APP_ENV"] == "development",
    )
