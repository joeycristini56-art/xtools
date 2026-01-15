security = HTTPBearer()

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title=settings.api_title,
        version=settings.api_version,
        description=settings.api_description,
        routes=app.routes,
    )
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "API Key",
            "description": "Enter your API key as a Bearer token"
        },
        "ApiKeyAuth": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
            "description": "Enter your API key in the X-API-Key header"
        }
    }
    for path in openapi_schema["paths"]:
        if path.startswith("/api/v1/"):
            for method in openapi_schema["paths"][path]:
                if method in ["get", "post", "put", "delete", "patch"]:
                    openapi_schema["paths"][path][method]["security"] = [
                        {"BearerAuth": []},
                        {"ApiKeyAuth": []}
                    ]
    app.openapi_schema = openapi_schema
    return app.openapi_schema
