from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Poll, PollOption
from .serializers import PollOut, PollCreateIn, VoteIn, VoteOut
from .services import create_poll, cast_vote, retract_vote


class PollViewSet(viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated]
    queryset = Poll.objects.all()

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

    @action(methods=["post"], detail=True, url_path="unvote")
    def unvote(self, request, pk=None):
        """
        POST /api/v1/polls/{id}/unvote
        """
        poll = get_object_or_404(self.get_queryset(), pk=pk)
        result = retract_vote(poll=poll, voter=request.user)
        out = VoteOut({"poll": result.poll, "my_option_id": result.my_option_id})
        return Response(out.data, status=status.HTTP_200_OK)

    @action(methods=["get"], detail=True, url_path="results")
    def results(self, request, pk=None):
        poll = get_object_or_404(self.get_queryset(), pk=pk)
        return Response(PollOut(poll).data, status=status.HTTP_200_OK)
