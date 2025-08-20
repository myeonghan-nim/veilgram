from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Asset, AssetStatus
from .serializers import PrepareUploadIn, PrepareUploadOut, CompleteUploadIn, AssetOut
from . import s3


class AssetUploadViewSet(viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated]
    queryset = Asset.objects.all()

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
