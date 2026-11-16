import os
from io import BytesIO
from PIL import Image, ImageOps, UnidentifiedImageError
from uuid import uuid4
from fastapi import APIRouter, Request, Form, UploadFile, File, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from app.database import run_query
from app.auth import get_user_from_session

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
UPLOAD_DIR = "app/uploads"


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    user = get_user_from_session(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    courses = run_query(
        """
        SELECT c.* FROM courses c
        JOIN course_registrations cr ON cr.course_id = c.id
        WHERE cr.user_id = %s
        """,
        (user["id"],),
        fetchall=True,
    )
    messages = run_query(
        "SELECT * FROM messages WHERE recipient_id=%s ORDER BY created_at DESC LIMIT 5",
        (user["id"],),
        fetchall=True,
    )
    grades = run_query(
        "SELECT * FROM grades WHERE student_id=%s ORDER BY updated_at DESC LIMIT 5",
        (user["id"],),
        fetchall=True,
    )
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "user": user, "courses": courses, "messages": messages, "grades": grades},
    )


@router.get("/profile", response_class=HTMLResponse)
def my_profile(request: Request):
    user = get_user_from_session(request)
    if not user:
        return RedirectResponse("/login", status_code=302)
    return templates.TemplateResponse("profile.html", {"request": request, "user": user, "profile": user})


@router.get("/profile/{user_id}", response_class=HTMLResponse)
def profile_by_id(request: Request, user_id: int):
    user = get_user_from_session(request)
    if not user:
        return RedirectResponse("/login", status_code=302)
    profile = run_query("SELECT * FROM users WHERE id=%s", (user_id,), fetchone=True)
    return templates.TemplateResponse("profile.html", {"request": request, "user": user, "profile": profile})


@router.post("/profile/update")
def update_profile(
    request: Request,
    full_name: str = Form(""),
    phone: str = Form(""),
    address: str = Form(""),
    bio: str = Form(""),
):
    user = get_user_from_session(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    run_query(
        """
        UPDATE users SET full_name=%s, phone=%s, address=%s, bio=%s
        WHERE id=%s
        """,
        (full_name, phone, address, bio, user["id"]),
        commit=True,
    )
    return RedirectResponse(f"/profile/{user['id']}", status_code=302)


@router.post("/profile/avatar")
def upload_avatar(request: Request, avatar: UploadFile = File(...)):
    user = get_user_from_session(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    max_size = 2 * 1024 * 1024  # Restrict source upload to 2 MiB.
    data = avatar.file.read(max_size + 1)
    if len(data) > max_size:
        raise HTTPException(status_code=413, detail="Avatar must be <= 2 MiB")

    try:
        with Image.open(BytesIO(data)) as image:
            if image.format not in {"JPEG", "PNG", "WEBP"}:
                raise ValueError("Unsupported image format")
            if image.width * image.height > 4_000_000:
                raise ValueError("Image dimensions are too large")
            image.load()  # Actually decode the bytes; extensions and MIME types are not trusted.
            normalized = ImageOps.exif_transpose(image)
            mode = "RGBA" if "A" in normalized.getbands() else "RGB"
            output = BytesIO()
            normalized.convert(mode).save(output, format="PNG")
            safe_content = output.getvalue()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        raise HTTPException(status_code=400, detail="Invalid avatar image") from exc

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    filename = f"avatar_{user['id']}_{uuid4().hex}.png"  # Ignore user-supplied filename.
    path = os.path.join(UPLOAD_DIR, filename)
    with open(path, "wb") as handle:
        handle.write(safe_content)
    run_query("UPDATE users SET avatar_path=%s WHERE id=%s", (filename, user["id"]), commit=True)
    return RedirectResponse(f"/profile/{user['id']}", status_code=302)
