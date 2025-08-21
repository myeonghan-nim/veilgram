import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def forwards(apps, schema_editor):
    """
    owner 백필 로직:
        - Poll에 연결된 Post가 있으면 Post.author를 owner로
        - 없으면 고정 SYSTEM_USER_ID를 owner로 부여
    """
    Poll = apps.get_model("polls", "Poll")
    Post = apps.get_model("posts", "Post")

    user_app, user_model = settings.AUTH_USER_MODEL.split(".")
    User = apps.get_model(user_app, user_model)

    SYSTEM_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
    system_user, _ = User.objects.get_or_create(id=SYSTEM_USER_ID)

    qs = Poll.objects.filter(owner__isnull=True).only("id")
    # created_at이 있다면 가장 이른 Post 기준으로 매핑
    for p in qs.iterator():
        post = Post.objects.filter(poll_id=p.id).only("author_id").order_by("created_at").first()
        owner_id = post.author_id if post and getattr(post, "author_id", None) else system_user.id
        Poll.objects.filter(pk=p.id).update(owner_id=owner_id)


def backwards(apps, schema_editor):
    # 롤백 시 owner를 NULL로 되돌림
    Poll = apps.get_model("polls", "Poll")
    Poll.objects.update(owner=None)


class Migration(migrations.Migration):

    dependencies = [
        ("polls", "0001_initial"),
        ("posts", "0001_initial"),  # Post.author를 읽기 위한 의존
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # 1) owner (nullable로 먼저 추가)
        migrations.AddField(
            model_name="poll",
            name="owner",
            field=models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.CASCADE, related_name="owned_polls", null=True, blank=True, db_index=True),
        ),
        # 2) allow_multiple (기존 행은 False로 채우되, DB default는 남기지 않음)
        migrations.AddField(model_name="poll", name="allow_multiple", field=models.BooleanField(default=False), preserve_default=False),
        # 3) poll_options 테이블 신설
        migrations.CreateModel(
            name="PollOption",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("text", models.CharField(max_length=100)),
                ("position", models.PositiveSmallIntegerField()),
                ("vote_count", models.PositiveIntegerField(default=0)),
                ("poll", models.ForeignKey(to="polls.poll", on_delete=django.db.models.deletion.CASCADE, related_name="options", db_index=True)),
            ],
            options={
                "db_table": "poll_options",
                "ordering": ("position", "id"),
                "constraints": [
                    models.UniqueConstraint(fields=("poll", "position"), name="uq_poll_option_position"),
                    models.UniqueConstraint(fields=("poll", "text"), name="uq_poll_option_text"),
                ],
                "indexes": [],
            },
        ),
        # 4) poll_votes 테이블 신설
        migrations.CreateModel(
            name="Vote",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("option", models.ForeignKey(to="polls.polloption", on_delete=django.db.models.deletion.CASCADE, related_name="votes", db_index=True)),
                ("poll", models.ForeignKey(to="polls.poll", on_delete=django.db.models.deletion.CASCADE, related_name="votes", db_index=True)),
                ("voter", models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.CASCADE, related_name="votes", db_index=True)),
            ],
            options={
                "db_table": "poll_votes",
                "constraints": [
                    models.UniqueConstraint(fields=("voter", "poll"), name="uq_vote_voter_poll"),
                ],
                "indexes": [
                    models.Index(fields=["poll"], name="idx_vote_poll"),
                    models.Index(fields=["option"], name="idx_vote_option"),
                ],
            },
        ),
        # 5) 데이터 백필 (owner 채우기)
        migrations.RunPython(forwards, backwards),
        # 6) owner를 NOT NULL로 전환
        migrations.AlterField(
            model_name="poll",
            name="owner",
            field=models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.CASCADE, related_name="owned_polls", null=False, blank=False, db_index=True),
        ),
    ]
