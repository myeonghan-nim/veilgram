from rest_framework.pagination import CursorPagination


class PostCursorPagination(CursorPagination):
    page_size = 20
    ordering = "-created_at"  # created_at 역순, tie-break는 모델 기본 ordering에서 id가 뒤에 옴
    page_size_query_param = "page_size"
    max_page_size = 100
