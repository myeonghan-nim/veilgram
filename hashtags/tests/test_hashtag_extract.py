from hashtags.services import extract_hashtags, normalize_tag


class TestHashtagExtraction:
    def test_extract_korean_english_numbers(self):
        text = "오늘은 #장고 로 #Django #django_2 #장고 를 공부! #장고"
        tags = extract_hashtags(text)
        assert tags == ["장고", "django", "django_2"]

    def test_normalize_nfkc_and_len(self):
        raw = "Ｄｊａｎｇｏ"  # 전각
        assert normalize_tag(raw) == "django"
        long = "#" + "a" * 200
        tags = extract_hashtags(long)
        assert len(tags) == 1 and tags[0] == "a" * 64
