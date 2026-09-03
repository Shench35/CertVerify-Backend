def test_root_endpoint(client):
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "operational"
    assert data["project"] == "CertVerify API"


def test_health_check_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"


def test_openapi_documentation(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert "paths" in schema
    assert len(schema["paths"]) >= 10


def test_admin_routes_use_single_openapi_tag(client):
    schema = client.get("/openapi.json").json()

    admin_operations = [
        operation
        for path, methods in schema["paths"].items()
        if path.startswith("/admin/")
        for method, operation in methods.items()
        if method != "parameters"
    ]

    assert admin_operations
    assert all(operation["tags"] == ["Admin Panel"] for operation in admin_operations)
