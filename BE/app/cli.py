"""운영 명령. 사용법: python -m app.cli <command>"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import click

from .config import load_config
from .db import connect, init_db
from .discord_bot import register_commands
from .feed_collector import collect_all
from .logging_config import configure_logging, logger
from .maintenance import backup_database, prune_backups, restore_database, run_scheduler
from .seed_blogs import seed_default_blogs


@click.group()
@click.pass_context
def cli(ctx: click.Context) -> None:
    """Tech Blog Aggregator 운영 명령."""
    # 테스트에서는 obj로 설정을 넘긴다. 그 외에는 환경변수에서 읽고 DB를 준비한다.
    if not ctx.obj:
        config = load_config()
        Path(config["DATABASE_PATH"]).parent.mkdir(parents=True, exist_ok=True)
        init_db(config["DATABASE_PATH"])
        configure_logging(config)
        ctx.obj = config


pass_config = click.make_pass_decorator(dict)


@cli.command("seed-blogs")
@pass_config
def seed_blogs_command(config: dict) -> None:
    count = seed_default_blogs(config["DATABASE_PATH"])
    click.echo(f"기본 기술 블로그 {count}개를 등록했습니다.")


@cli.command("collect-feeds")
@click.option("--timeout", type=click.IntRange(1, 120), default=20, show_default=True)
@pass_config
def collect_feeds_command(config: dict, timeout: int) -> None:
    """활성 블로그 피드를 한 번 수집한다."""
    result = collect_all(
        config["DATABASE_PATH"], timeout=timeout, discord_bot_token=config["DISCORD_BOT_TOKEN"]
    )
    click.echo(json.dumps(result, ensure_ascii=False))
    if result["failed"]:
        raise click.ClickException(f"{result['failed']}개 블로그 수집에 실패했습니다.")


@cli.command("prune-auth-tokens")
@pass_config
def prune_auth_tokens_command(config: dict) -> None:
    """만료된 인증 토큰을 삭제한다."""
    now = datetime.now(timezone.utc).isoformat()
    with connect(config["DATABASE_PATH"]) as db:
        cursor = db.execute("DELETE FROM auth_tokens WHERE expires_at <= ?", (now,))
        action_cursor = db.execute(
            "DELETE FROM auth_action_tokens WHERE expires_at <= ? OR used_at IS NOT NULL",
            (now,),
        )
    click.echo(
        f"만료된 인증 토큰 {cursor.rowcount}개와 인증 작업 토큰 "
        f"{action_cursor.rowcount}개를 삭제했습니다."
    )


@cli.command("prune-login-attempts")
@pass_config
def prune_login_attempts_command(config: dict) -> None:
    """오래된 로그인 제한 기록을 삭제한다."""
    cutoff = int(datetime.now(timezone.utc).timestamp()) - config["AUTH_LOGIN_WINDOW_SECONDS"]
    with connect(config["DATABASE_PATH"]) as db:
        cursor = db.execute(
            "DELETE FROM login_attempts WHERE window_started_at <= ?", (cutoff,)
        )
    click.echo(f"오래된 로그인 시도 기록 {cursor.rowcount}개를 삭제했습니다.")


@cli.command("backup-db")
@pass_config
def backup_db_command(config: dict) -> None:
    path = backup_database(config["DATABASE_PATH"], config["BACKUP_DIRECTORY"])
    removed = prune_backups(config["BACKUP_DIRECTORY"], config["BACKUP_RETENTION_DAYS"])
    click.echo(f"백업을 생성했습니다: {path} (오래된 백업 {removed}개 삭제)")


@cli.command("restore-db")
@click.argument("backup_path", type=click.Path(exists=True, dir_okay=False))
@click.option("--yes", is_flag=True, help="복원을 확인합니다.")
@pass_config
def restore_db_command(config: dict, backup_path: str, yes: bool) -> None:
    if not yes:
        raise click.ClickException("복원하려면 --yes 옵션이 필요합니다.")
    restore_database(config["DATABASE_PATH"], backup_path)
    click.echo("데이터베이스를 복원했습니다.")


@cli.command("run-scheduler")
@pass_config
def run_scheduler_command(config: dict) -> None:
    def report(result: dict) -> None:
        logger.info(
            "scheduled_collection_completed",
            extra={"total": result["total"], "failed": result["failed"], "saved": result["saved"]},
        )

    def collect_with_discord(database_path: str, timeout: int) -> dict:
        return collect_all(
            database_path, timeout=timeout, discord_bot_token=config["DISCORD_BOT_TOKEN"]
        )

    run_scheduler(
        collect_with_discord,
        config["DATABASE_PATH"],
        config["BACKUP_DIRECTORY"],
        config["FEED_COLLECTION_INTERVAL_SECONDS"],
        config["FEED_COLLECTION_TIMEOUT_SECONDS"],
        config["BACKUP_RETENTION_DAYS"],
        report,
    )


@cli.command("register-discord-commands")
@pass_config
def register_discord_commands_command(config: dict) -> None:
    application_id = config["DISCORD_APPLICATION_ID"]
    bot_token = config["DISCORD_BOT_TOKEN"]
    if not application_id or not bot_token:
        raise click.ClickException("DISCORD_APPLICATION_ID와 DISCORD_BOT_TOKEN이 필요합니다.")
    guild_id = config["DISCORD_TEST_GUILD_ID"]
    commands = register_commands(application_id, bot_token, guild_id)
    scope = f"서버 {guild_id}" if guild_id else "전역"
    click.echo(f"{scope} Discord 명령 {len(commands)}개를 등록했습니다.")


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()
    cli()
