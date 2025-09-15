from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiExample
from rest_framework import viewsets, status, serializers
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response


from .models import Asset, AssetStatus
from .serializers import PrepareUploadIn, PrepareUploadOut, CompleteUploadIn, AssetOut
from . import s3
from common.schema import ErrorOut


class AssetUploadViewSet(viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated]
    queryset = Asset.objects.all()
    serializer_class = serializers.Serializer

    @extend_schema(
        tags=["Assets"],
        summary="사전 업로드 준비(Presigned PUT 발급)",
        description=("1) 입력 검증 → 2) storage_key 생성 → 3) Asset(PENDING) 생성 → " "4) S3 Presigned PUT URL 발급 → 5) 업로드 메타 반환"),
        operation_id="assets_prepare_upload",
        request=PrepareUploadIn,
        responses={
            201: OpenApiResponse(response=PrepareUploadOut, description="Presigned URL과 PENDING 자산 메타 반환"),
            400: OpenApiResponse(response=ErrorOut),
            401: OpenApiResponse(response=ErrorOut),
        },
        examples=[
            OpenApiExample("요청 예시", value={"type": "image", "content_type": "image/png", "size_bytes": 123456, "ext": "png"}, request_only=True),
            OpenApiExample(
                "응답 예시",
                value={
                    "asset_id": "11111111-1111-1111-1111-111111111111",
                    "upload_url": "https://minio.local/bucket/...",
                    "method": "PUT",
                    "headers": {"Content-Type": "image/png"},
                    "storage_key": "users/abcd-ef.../images/2025/09/15/....png",
                    "public_url": "https://cdn.local/...",
                },
                response_only=True,
            ),
        ],
    )
    @action(methods=["post"], detail=False, url_path="prepare")
    def prepare(self, request):
        # 1) 입력 검증 → 2) storage_key 생성 → 3) Asset(PENDING) 생성 → 4) presigned PUT URL 발급 → 5) 업로드 메타 반환
        serializer = PrepareUploadIn(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        owner = request.user
        key = s3.build_storage_key(str(owner.id), data["type"], data["ext"])
        url = s3.presign_put_url(key, data["content_type"])
        public = s3.public_url(key)

        asset = Asset.objects.create(
            owner=owner,
            type=data["type"],
            content_type=data["content_type"],
            size_bytes=data["size_bytes"],
            storage_key=key,
            public_url=public,
            status=AssetStatus.PENDING,
        )

        out = PrepareUploadOut(
            {
                "asset_id": asset.id,
                "upload_url": url,
                "method": "PUT",
                "headers": {"Content-Type": data["content_type"]},
                "storage_key": key,
                "public_url": public,
            }
        )
        return Response(out.data, status=status.HTTP_201_CREATED)

    @extend_schema(
        tags=["Assets"],
        summary="업로드 완료 확정(HEAD 검증 → READY 전환)",
        description=("클라이언트가 PUT 업로드를 마친 뒤 호출합니다. " "S3 head_object로 존재/크기를 검증하고 이상 없으면 상태를 READY로 전환합니다."),
        operation_id="assets_complete_upload",
        request=CompleteUploadIn,
        responses={
            200: OpenApiResponse(response=AssetOut, description="READY로 전환된 자산 메타"),
            400: OpenApiResponse(response=ErrorOut, description="크기 불일치 등 검증 오류"),
            401: OpenApiResponse(response=ErrorOut),
            404: OpenApiResponse(response=ErrorOut, description="자산이 없거나 소유자가 아님"),
        },
        examples=[
            OpenApiExample("요청 예시", value={"asset_id": "11111111-1111-1111-1111-111111111111"}, request_only=True),
            OpenApiExample(
                "응답 예시(성공)",
                value={
                    "id": "11111111-1111-1111-1111-111111111111",
                    "owner": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                    "type": "image",
                    "content_type": "image/png",
                    "size_bytes": 123456,
                    "public_url": "https://cdn.local/...",
                    "status": "ready",
                    "created_at": "2025-09-15T08:30:00Z",
                    "updated_at": "2025-09-15T08:31:00Z",
                },
                response_only=True,
            ),
            OpenApiExample("응답 예시(오류)", value={"detail": "Uploaded object size mismatch"}, response_only=True),
        ],
    )
    @action(methods=["post"], detail=False, url_path="complete")
    def complete(self, request):
        """
        클라이언트가 PUT 업로드 완료 후 호출.
        S3 head_object로 존재/크기 확인 후 READY 전환.
        """
        serializer = CompleteUploadIn(data=request.data)
        serializer.is_valid(raise_exception=True)
        asset = Asset.objects.get(pk=serializer.validated_data["asset_id"], owner=request.user)

        meta = s3.head_object(asset.storage_key)
        content_length = meta.get("ContentLength")
        if asset.size_bytes and content_length and int(content_length) != int(asset.size_bytes):
            asset.status = AssetStatus.FAILED
            asset.save(update_fields=["status", "updated_at"])
            return Response({"detail": "Uploaded object size mismatch"}, status=400)

        asset.status = AssetStatus.READY
        asset.updated_at = timezone.now()
        asset.save(update_fields=["status", "updated_at"])

        return Response(AssetOut(asset).data, status=status.HTTP_200_OK)
