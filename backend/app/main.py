from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.routes import (
    auth_routes,
    profile_routes,
    course_routes,
    assignment_routes,
    grade_routes,
    message_routes,
    admin_routes,
    utility_routes,
)

app = FastAPI(title="DAT250 SecureApp", debug=True)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
class AvatarFiles(StaticFiles):
    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        # Also neutralize legacy active uploads when accessing the backend directly.
        response.headers["Content-Security-Policy"] = "default-src 'none'; sandbox"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response


app.mount("/uploads", AvatarFiles(directory="app/uploads"), name="uploads")

app.include_router(auth_routes.router)
app.include_router(profile_routes.router)
app.include_router(course_routes.router)
app.include_router(assignment_routes.router)
app.include_router(grade_routes.router)
app.include_router(message_routes.router)
app.include_router(admin_routes.router)
app.include_router(utility_routes.router)
