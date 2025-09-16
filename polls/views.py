from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, OpenApiResponse, OpenApiTypes, extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from common.schema import ErrorOut

from .models import Poll, PollOption
from .serializers import PollCreateIn, PollOut, VoteIn, VoteOut
from .services import cast_vote, create_poll, retract_vote


@extend_schema_view(
    list=extend_schema(
        tags=["Polls"],
        summary="내가 생성한 투표 목록",
        description="현재 로그인 사용자가 생성한 투표를 최신순으로 반환합니다. (현재 뷰는 페이지네이션 없이 전체 반환)",
        operation_id="polls_list",
        responses={200: OpenApiResponse(response=PollOut(many=True), description="투표 목록"), 401: OpenApiResponse(response=ErrorOut)},
    ),
    retrieve=extend_schema(
        tags=["Polls"],
        summary="투표 단건 조회",
        operation_id="polls_retrieve",
        parameters=[OpenApiParameter(name="pk", location=OpenApiParameter.PATH, type=OpenApiTypes.UUID, description="투표 ID (UUID)")],
        responses={200: OpenApiResponse(response=PollOut, description="투표 상세/집계"), 401: OpenApiResponse(response=ErrorOut), 404: OpenApiResponse(response=ErrorOut)},
    ),
    create=extend_schema(
        tags=["Polls"],
        summary="투표 생성",
        description="옵션 2~5개, `allow_multiple`(복수 선택) 여부를 지정해 새 투표를 생성합니다.",
        operation_id="polls_create",
        request=PollCreateIn,
        responses={201: OpenApiResponse(response=PollOut, description="생성된 투표"), 400: OpenApiResponse(response=ErrorOut), 401: OpenApiResponse(response=ErrorOut)},
        examples=[OpenApiExample("요청 예시", value={"options": ["국밥", "비빔밥", "김치찌개"], "allow_multiple": False}, request_only=True)],
    ),
)
class PollViewSet(viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated]
    queryset = Poll.objects.all()
    serializer_class = PollOut

    def retrieve(self, request, pk=None):
        poll = get_object_or_404(self.get_queryset(), pk=pk)
        return Response(PollOut(poll).data)

    def list(self, request):
        # 기본은 내가 만든 Poll만(운영 편의) 보이며 필요시 공개 범위에 따라 확장
        qs = self.get_queryset().filter(owner=request.user).order_by("-created_at")
        return Response(PollOut(qs, many=True).data)

    def create(self, request):
        """
        POST /api/v1/polls/
        body: { "options": ["A","B"], "allow_multiple": false }
        """
        ser = PollCreateIn(data=request.data)
        ser.is_valid(raise_exception=True)

        try:
            created = create_poll(owner=request.user, option_texts=ser.validated_data["options"], allow_multiple=ser.validated_data["allow_multiple"])
        except DjangoValidationError as e:
            detail = getattr(e, "message_dict", None) or getattr(e, "messages", None) or str(e)
            raise DRFValidationError(detail)
        return Response(PollOut(created.poll).data, status=status.HTTP_201_CREATED)

    @extend_schema(
        tags=["Polls"],
        summary="투표 참여",
        description="특정 투표의 옵션 하나(또는 정책상 허용되는 복수 개)에 투표합니다.",
        operation_id="polls_vote",
        parameters=[OpenApiParameter(name="pk", location=OpenApiParameter.PATH, type=OpenApiTypes.UUID, description="투표 ID (UUID)")],
        request=VoteIn,
        responses={
            200: OpenApiResponse(response=VoteOut, description="현재 내 선택 상태와 최신 집계"),
            400: OpenApiResponse(response=ErrorOut, description="잘못된 옵션 ID 등 검증 오류"),
            401: OpenApiResponse(response=ErrorOut),
            404: OpenApiResponse(response=ErrorOut),
        },
        examples=[
            OpenApiExample("요청 예시", value={"option_id": "11111111-1111-1111-1111-111111111111"}, request_only=True),
            OpenApiExample(
                "응답 예시",
                value={"poll": {"id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "options": []}, "my_option_id": "11111111-1111-1111-1111-111111111111"},
                response_only=True,
            ),
        ],
    )
    @action(methods=["post"], detail=True, url_path="vote")
    def vote(self, request, pk=None):
        """
        POST /api/v1/polls/{id}/vote
        body: { "option_id": "<uuid>" }
        """
        poll = get_object_or_404(self.get_queryset(), pk=pk)

        vin = VoteIn(data=request.data)
        vin.is_valid(raise_exception=True)

        # 1) 존재 여부를 400(Validation)로 매핑: 테스트 기대와 일치
        option = PollOption.objects.filter(pk=vin.validated_data["option_id"]).first()
        if option is None:
            raise DRFValidationError({"option_id": "Option not found"})

        # 2) 서비스에 '객체'를 넘겨 FK 할당 시 'UUID.pk' 오류 방지
        try:
            result = cast_vote(poll=poll, voter=request.user, option=option)
        except DjangoValidationError as e:
            detail = getattr(e, "message_dict", None) or getattr(e, "messages", None) or str(e)
            raise DRFValidationError(detail)

        out = VoteOut({"poll": result.poll, "my_option_id": result.my_option_id})
        return Response(out.data, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["Polls"],
        summary="투표 철회",
        description="내가 선택한 옵션을 철회하고, 최신 집계를 반환합니다.",
        operation_id="polls_unvote",
        parameters=[OpenApiParameter(name="pk", location=OpenApiParameter.PATH, type=OpenApiTypes.UUID, description="투표 ID (UUID)")],
        responses={200: OpenApiResponse(response=VoteOut, description="철회 후 최신 집계"), 401: OpenApiResponse(response=ErrorOut), 404: OpenApiResponse(response=ErrorOut)},
        examples=[OpenApiExample("응답 예시", value={"poll": {"id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "options": []}, "my_option_id": None}, response_only=True)],
    )
    @action(methods=["post"], detail=True, url_path="unvote")
    def unvote(self, request, pk=None):
        """
        POST /api/v1/polls/{id}/unvote
        """
        poll = get_object_or_404(self.get_queryset(), pk=pk)
        result = retract_vote(poll=poll, voter=request.user)
        out = VoteOut({"poll": result.poll, "my_option_id": result.my_option_id})
        return Response(out.data, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["Polls"],
        summary="투표 결과 조회",
        description="현재 시점의 투표 집계를 조회합니다.",
        operation_id="polls_results",
        parameters=[OpenApiParameter(name="pk", location=OpenApiParameter.PATH, type=OpenApiTypes.UUID, description="투표 ID (UUID)")],
        responses={200: OpenApiResponse(response=PollOut, description="현재 집계"), 401: OpenApiResponse(response=ErrorOut), 404: OpenApiResponse(response=ErrorOut)},
    )
    @action(methods=["get"], detail=True, url_path="results")
    def results(self, request, pk=None):
        poll = get_object_or_404(self.get_queryset(), pk=pk)
        return Response(PollOut(poll).data, status=status.HTTP_200_OK)
