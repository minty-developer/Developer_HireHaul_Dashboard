from . import bp


@bp.get("/")
def home():
    return """
    <html>
        <head>
            <meta charset="UTF-8">
            <title>Tech Blog Aggregator</title>
        </head>

        <body style="font-family: Arial; text-align: center; margin-top: 100px;">
            <h1>Tech Blog Aggregator API</h1>

            <p>
                국내 IT 기업 기술 블로그의 글을 모아 제공하는 서비스입니다.
            </p>
        </body>
    </html>
    """
