import pytest
from django.db import IntegrityError

from hashtags.models import Hashtag


@pytest.mark.django_db
class TestHashtagModels:
    def test_unique_case_insensitive(self):
        Hashtag.objects.create(name="django")
        with pytest.raises(IntegrityError):
            Hashtag.objects.create(name="Django")
