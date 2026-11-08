from uuid import UUID

from fastapi import APIRouter, Depends, Response
from starlette.concurrency import run_in_threadpool

from app.api.auth import DB, Admin, guard
from app.api.errors import ApiError
from app.services.signature_list import render_pdf, snapshot

router = APIRouter(
    tags=["documents"],
    dependencies=[Depends(guard)],
    responses={code: {"model": ApiError} for code in (401, 403, 404, 409, 422, 500)},
)


@router.get(
    "/admin/meetings/{meeting_id}/signature-list",
    response_class=Response,
    responses={
        200: {"content": {"application/pdf": {"schema": {"type": "string", "format": "binary"}}}}
    },
    operation_id="getSignatureList",
)
async def signature_list(meeting_id: UUID, _actor: Admin, db: DB, download: bool = False):
    source = await snapshot(db, meeting_id)
    pdf = await run_in_threadpool(render_pdf, source)
    disposition = "attachment" if download else "inline"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'{disposition}; filename="{source.filename}"',
            "X-Content-Type-Options": "nosniff",
            "X-Attendance-Revision": str(source.attendance_revision),
        },
    )
