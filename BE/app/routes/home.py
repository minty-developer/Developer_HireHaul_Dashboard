from . import bp


@bp.get("/")
def home():
    return """
    <html>
        <head>
            <meta charset="UTF-8">
            <title>HireHaul Dashboard</title>
        </head>

        <body style="font-family: Arial; text-align: center; margin-top: 100px;">
            <h1>HireHaul 채용공고 대시보드</h1>

            <p>
                현재 개발 중인 개인 프로젝트입니다.
            </p>

            <p>
                채용공고 API를 활용하여 채용정보를 수집하고 제공할 예정입니다.
            </p>
        </body>
    </html>
    """